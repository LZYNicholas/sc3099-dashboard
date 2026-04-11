"""SAIV Instructor Dashboard - Unified Statistics
"""

import streamlit as st
import requests
import pandas as pd
import plotly.express as px

from lib.auth_state import API_BASE_URL, get_auth_headers, require_auth
from lib.response_utils import fetch_all_items, friendly_error
from lib.time_utils import format_sgt
from lib.ui_theme import apply_theme
from lib import stat_courses

st.set_page_config(page_title="Course and Student Monitoring - SAIV Dashboard", layout="wide", initial_sidebar_state="expanded")
apply_theme()

def _headers():
    return get_auth_headers()


def _render_students_tab() -> None:
    st.subheader("Student Performance")
    st.caption("Monitor individual student attendance and risk performance in one place.")

    try:
        courses = fetch_all_items(
            f"{API_BASE_URL}/courses/",
            headers=_headers(),
            timeout=10,
            page_size=200,
        )
    except Exception:
        courses = []

    if not courses:
        st.info("No courses available.")
        return

    student_options: dict[str, str] = {}
    student_course_codes: dict[str, set[str]] = {}
    for course in courses:
        if not isinstance(course, dict):
            continue
        course_id = str(course.get("id") or "").strip()
        if not course_id:
            continue
        course_code = str(course.get("code") or course.get("name") or "Unknown Course")
        try:
            enr_resp = requests.get(
                f"{API_BASE_URL}/enrollments/course/{course_id}",
                headers=_headers(),
                timeout=10,
            )
        except Exception:
            continue
        if enr_resp.status_code != 200:
            continue
        payload = enr_resp.json()
        if isinstance(payload, dict):
            enrolled_students = payload.get("students", [])
        elif isinstance(payload, list):
            enrolled_students = payload
        else:
            enrolled_students = []

        for student in enrolled_students:
            if not isinstance(student, dict):
                continue
            student_id = str(student.get("student_id") or student.get("user_id") or student.get("id") or "").strip()
            if not student_id:
                continue
            full_name = str(student.get("student_name") or student.get("full_name") or "").strip()
            email = str(student.get("student_email") or student.get("email") or "").strip()
            if full_name and email:
                label = f"{full_name} ({email})"
            elif full_name:
                label = full_name
            elif email:
                label = email
            else:
                label = f"Student {student_id}"
            student_options[student_id] = label
            student_course_codes.setdefault(student_id, set()).add(course_code)

    if not student_options:
        st.info("No students available.")
        return

    selected_student_id = st.selectbox(
        "Select Student",
        options=list(student_options.keys()),
        format_func=lambda x: student_options[x],
        key="csm_students_student",
    )

    try:
        stats_resp = requests.get(
            f"{API_BASE_URL}/stats/students/{selected_student_id}",
            headers=_headers(),
            timeout=10,
        )
    except Exception as e:
        st.error(friendly_error(e, "Couldn't load student statistics right now."))
        return

    if stats_resp.status_code != 200:
        st.warning("Could not load student statistics.")
        return

    stats = stats_resp.json() if stats_resp is not None else {}
    courses_stats = stats.get("courses", []) if isinstance(stats.get("courses"), list) else []
    all_courses_stats = list(courses_stats)
    course_filter_options = ["All Courses"] + sorted({
        str(c.get("course_code") or c.get("course_name") or c.get("course_id") or "Unknown Course")
        for c in courses_stats
    })
    course_filter_key = f"csm_students_optional_course_filter_{selected_student_id}"
    if course_filter_key not in st.session_state or st.session_state.get(course_filter_key) not in course_filter_options:
        st.session_state[course_filter_key] = "All Courses"

    selected_course_filter = st.selectbox(
        "Filter by Course (Optional)",
        options=course_filter_options,
        key=course_filter_key,
    )

    if selected_course_filter != "All Courses":
        st.caption(f"Currently filtered to: {selected_course_filter}")
        courses_stats = [
            c
            for c in courses_stats
            if str(c.get("course_code") or c.get("course_name") or c.get("course_id") or "Unknown Course")
            == selected_course_filter
        ]

    recent = stats.get("recent_checkins", []) if isinstance(stats.get("recent_checkins"), list) else []
    if selected_course_filter != "All Courses":
        recent = [
            r for r in recent
            if str((r or {}).get("course_code") or (r or {}).get("course_name") or (r or {}).get("course_id") or "Unknown Course")
            == selected_course_filter
        ]

    total_sessions = sum(int(c.get("total_sessions", 0) or 0) for c in courses_stats)
    attended_sessions = sum(int(c.get("sessions_attended", 0) or 0) for c in courses_stats)
    attendance_rate = (attended_sessions / total_sessions * 100) if total_sessions else 0.0

    risk_vals = pd.to_numeric(
        pd.Series([c.get("average_risk_score") for c in courses_stats]), errors="coerce"
    ).dropna()
    avg_risk = float(risk_vals.mean()) if not risk_vals.empty else None

    flagged_count = sum(
        1 for r in recent if str((r or {}).get("status", "")).strip().lower() in {"flagged", "rejected", "appealed"}
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Enrolled Courses", len(courses_stats))
    c2.metric("Total Sessions", total_sessions)
    c3.metric("Attended Sessions", attended_sessions)
    c4.metric("Attendance Rate", f"{attendance_rate:.1f}%")
    c5.metric("Avg Risk Score", f"{avg_risk:.3f}" if avg_risk is not None else "N/A")
    st.caption(f"Recent flagged/rejected/appealed check-ins: {flagged_count}")

    if all_courses_stats:
        trend_df = pd.DataFrame(all_courses_stats)
        if "course_code" in trend_df.columns and "attendance_rate" in trend_df.columns:
            # Force categorical course labels even when course codes are numeric-like (e.g. "123").
            trend_df["course_label"] = trend_df["course_code"].astype(str).str.strip()
            trend_df["attendance_rate_pct"] = pd.to_numeric(trend_df["attendance_rate"], errors="coerce") * 100
            trend_df = trend_df.dropna(subset=["attendance_rate_pct"])
            trend_df = (
                trend_df.sort_values("course_label")
                .drop_duplicates(subset=["course_label"], keep="last")
            )
            if not trend_df.empty:
                st.markdown("##### Attendance Rate by Course")
                st.bar_chart(
                    trend_df.set_index("course_label")["attendance_rate_pct"],
                    use_container_width=True,
                )
                st.caption(f"Showing {len(trend_df)} enrolled course(s) for this student.")
                st.dataframe(
                    trend_df[["course_label", "attendance_rate_pct"]].rename(
                        columns={"course_label": "course", "attendance_rate_pct": "attendance_rate_%"}
                    ),
                    use_container_width=True,
                    hide_index=True,
                )

    st.markdown("##### Recent Check-ins")
    if recent:
        recent_df = pd.DataFrame(recent)
        if "checked_in_at" in recent_df.columns:
            recent_df["checked_in_at"] = recent_df["checked_in_at"].apply(lambda v: format_sgt(v, "%Y-%m-%d %H:%M SGT"))
        preferred_cols = ["course_code", "session_name", "checked_in_at", "status", "risk_score"]
        available_cols = [col for col in preferred_cols if col in recent_df.columns]
        display_df = recent_df[available_cols] if available_cols else recent_df
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info("No recent check-ins available for this student.")


def main():
    require_auth()

    st.title("Course and Student Monitoring")
    st.markdown("Course and student performance details are consolidated here.")

    tab_courses, tab_students = st.tabs(["Courses", "Students"])

    with tab_courses:
        stat_courses.main(embedded=True)

    with tab_students:
        _render_students_tab()


if __name__ == "__main__":
    main()
