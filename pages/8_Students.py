"""SAIV Instructor Dashboard - Student Analytics Page
"""

import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from lib.auth_state import API_BASE_URL, get_auth_headers, require_auth
from lib.response_utils import fetch_all_items

st.set_page_config(page_title="Students - SAIV Dashboard", layout="wide", initial_sidebar_state="expanded")


def get_headers():
    return get_auth_headers()


def main():
    require_auth()
    current_role = str((st.session_state.get('user') or {}).get('role', '')).strip().lower()
    if current_role not in {"instructor", "admin"}:
        st.error("Access denied. This page is restricted to instructors and admins.")
        st.stop()

    st.title("Student Analytics")
    st.markdown("View student attendance data and performance metrics.")

    # Course filter
    try:
        courses = fetch_all_items(
            f"{API_BASE_URL}/courses/",
            headers=get_headers(),
            timeout=10,
            page_size=200,
        )
    except Exception:
        courses = []

    course_options = {c["id"]: f"{c['code']} - {c['name']}" for c in courses if isinstance(c, dict) and c.get("id")}

    if not course_options:
        st.info("No courses available.")
        return

    selected_course = st.selectbox(
        "Select Course",
        options=list(course_options.keys()),
        format_func=lambda x: course_options[x],
    )

    # Fetch enrolled students
    try:
        students_resp = requests.get(
            f"{API_BASE_URL}/enrollments/course/{selected_course}",
            headers=get_headers(),
            timeout=10,
        )
        if students_resp.status_code == 200:
            payload = students_resp.json()
            if isinstance(payload, dict):
                students = payload.get("students", [])
            elif isinstance(payload, list):
                students = payload
            else:
                students = []
        else:
            students = []
    except Exception:
        students = []

    if not students:
        st.info("No students enrolled in this course.")
        return

    st.markdown("---")

    # Student selector
    student_options = {
        s.get("student_id", s.get("user_id", s.get("id"))): s.get("student_name", s.get("full_name", s.get("email", "Unknown")))
        for s in students
        if isinstance(s, dict)
    }

    selected_student_id = st.selectbox(
        "Select Student",
        options=list(student_options.keys()),
        format_func=lambda x: student_options[x],
    )

    # Fetch individual student stats
    if selected_student_id:
        try:
            stats_resp = requests.get(
                f"{API_BASE_URL}/stats/students/{selected_student_id}",
                headers=get_headers(),
                timeout=10,
            )
            if stats_resp.status_code == 200:
                stats = stats_resp.json()

                st.subheader(f"{stats.get('student_name', student_options.get(selected_student_id, 'Student'))} - Performance Summary")

                col1, col2, col3, col4 = st.columns(4)
                courses_stats = stats.get("courses", []) if isinstance(stats.get("courses"), list) else []
                total_sessions = sum(int(c.get("total_sessions", 0) or 0) for c in courses_stats)
                attended_sessions = sum(int(c.get("sessions_attended", 0) or 0) for c in courses_stats)
                attendance_rate = (attended_sessions / total_sessions * 100) if total_sessions else 0
                with col1:
                    st.metric("Enrolled Courses", len(courses_stats))
                with col2:
                    st.metric("Total Sessions", total_sessions)
                with col3:
                    st.metric("Attended", attended_sessions)
                with col4:
                    st.metric("Attendance Rate", f"{attendance_rate:.1f}%")

                # Attendance pie chart
                attended = attended_sessions
                missed = max(0, total_sessions - attended_sessions)
                if attended or missed:
                    fig = px.pie(
                        names=["Attended", "Missed"],
                        values=[attended, missed],
                        title="Attendance Breakdown",
                        color_discrete_sequence=["#28a745", "#dc3545"],
                    )
                    st.plotly_chart(fig, use_container_width=True)

                # Recent sessions
                recent = stats.get("recent_checkins", [])
                if recent:
                    st.subheader("Recent Sessions")
                    df = pd.DataFrame(recent)
                    st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.warning("Could not load student statistics.")
        except Exception as e:
            st.error(f"Error loading student stats: {e}")

    st.caption("Course-wide enrollment roster is managed in `Manage` to avoid duplicate list views.")


if __name__ == "__main__":
    main()

