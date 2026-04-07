"""SAIV Instructor Dashboard - Global Check-ins Explorer Page
"""

import json
from datetime import date, datetime, time, timezone

import pandas as pd
import streamlit as st

from lib.auth_state import API_BASE_URL, get_auth_headers, require_auth
from lib.response_utils import fetch_all_items, parse_json, request_with_retry, response_error


st.set_page_config(page_title="Check-ins - SAIV Dashboard", layout="wide", initial_sidebar_state="expanded")


def get_headers():
    return get_auth_headers()


def _checkin_status_color(status: str) -> str:
    state = (status or "").lower()
    if state == "approved":
        return "green"
    if state in {"flagged", "appealed"}:
        return "orange"
    if state == "rejected":
        return "red"
    return "gray"


def _stringify(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        try:
            return json.dumps(value, ensure_ascii=True)
        except Exception:
            return str(value)
    return str(value)


def _iso_range_start(d: date | None) -> str | None:
    if d is None:
        return None
    return datetime.combine(d, time.min, tzinfo=timezone.utc).isoformat()


def _iso_range_end(d: date | None) -> str | None:
    if d is None:
        return None
    return datetime.combine(d, time.max, tzinfo=timezone.utc).isoformat()


def _safe_avg_risk(items: list[dict]) -> float:
    if not items:
        return 0.0
    avg_risk = pd.to_numeric(pd.Series([row.get("risk_score") for row in items]), errors="coerce").mean()
    if pd.isna(avg_risk):
        return 0.0
    return float(avg_risk)


def _open_review_queue(*, checkin_id: str | None = None, session_id: str | None = None, course_id: str | None = None) -> None:
    st.session_state["review_queue_checkin_id"] = checkin_id or ""
    st.session_state["review_queue_session_id"] = session_id or ""
    st.session_state["review_queue_course_id"] = course_id or ""
    try:
        st.switch_page("pages/10_Review_Appeals.py")
    except Exception:
        st.info("Open `Review Appeals` from the sidebar to continue.")


def main() -> None:
    require_auth()
    current_role = str((st.session_state.get("user") or {}).get("role", "")).strip().lower()
    if current_role not in {"instructor", "admin"}:
        st.error("Access denied. This page is restricted to instructors and admins.")
        st.stop()

    st.title("Global Check-ins Explorer")
    st.caption("Cross-session filtering, review visibility, and exports.")

    try:
        courses = fetch_all_items(
            f"{API_BASE_URL}/courses/",
            headers=get_headers(),
            timeout=10,
            page_size=200,
        )
    except Exception:
        courses = []

    sessions_url = f"{API_BASE_URL}/sessions/"
    response, error = request_with_retry(
        "GET",
        sessions_url,
        params={"limit": 200},
        headers=get_headers(),
        timeout=12,
        retries=2,
    )
    if response is None:
        st.error(f"Failed to load sessions: {error or 'request failed'}")
        return
    if response.status_code != 200:
        st.error(f"Failed to load sessions ({response.status_code}): {response_error(response)}")
        return

    payload = parse_json(response)
    sessions = payload.get("items", []) if isinstance(payload, dict) else payload
    sessions = sessions if isinstance(sessions, list) else []

    course_options = {"All": "All Courses"}
    for course in courses:
        course_id = course.get("id")
        if isinstance(course_id, str):
            course_options[course_id] = f"{course.get('code', 'N/A')} - {course.get('name', 'Unnamed')}"

    sessions_by_course: dict[str, list[dict]] = {}
    for s in sessions:
        cid = s.get("course_id")
        if isinstance(cid, str):
            sessions_by_course.setdefault(cid, []).append(s)

    f1, f2, f3, f4 = st.columns(4)
    with f1:
        selected_course = st.selectbox(
            "Course",
            options=list(course_options.keys()),
            format_func=lambda x: course_options.get(x, x),
            key="global_checkins_filter_course",
        )
    with f2:
        session_options = ["All"]
        if selected_course != "All":
            for s in sessions_by_course.get(selected_course, []):
                sid = s.get("id")
                if isinstance(sid, str):
                    session_options.append(sid)
        else:
            for s in sessions:
                sid = s.get("id")
                if isinstance(sid, str):
                    session_options.append(sid)

        selected_session = st.selectbox(
            "Session",
            options=session_options,
            format_func=lambda x: "All Sessions" if x == "All" else x,
            key="global_checkins_filter_session",
        )
    with f3:
        selected_status = st.selectbox(
            "Status",
            options=["All", "pending", "approved", "flagged", "rejected", "appealed"],
            key="global_checkins_filter_status",
        )
    with f4:
        page_limit = st.selectbox("Page Size", options=[50, 100, 200], index=1, key="global_checkins_filter_limit")

    f5, f6, f7, f8 = st.columns(4)
    with f5:
        min_risk = st.slider("Min Risk", 0.0, 1.0, 0.0, 0.01, key="global_checkins_filter_min_risk")
    with f6:
        max_risk = st.slider("Max Risk", 0.0, 1.0, 1.0, 0.01, key="global_checkins_filter_max_risk")
    with f7:
        use_date_filter = st.checkbox("Use Date Range", value=False, key="global_checkins_filter_use_dates")
    with f8:
        if st.button("Refresh", key="global_checkins_refresh_btn", use_container_width=True):
            st.rerun()

    d1, d2 = st.columns(2)
    with d1:
        start_date = st.date_input(
            "Start Date",
            value=date.today(),
            disabled=not use_date_filter,
            key="global_checkins_filter_start_date",
        )
    with d2:
        end_date = st.date_input(
            "End Date",
            value=date.today(),
            disabled=not use_date_filter,
            key="global_checkins_filter_end_date",
        )

    query: dict[str, object] = {"limit": page_limit, "offset": 0}
    if selected_course != "All":
        query["course_id"] = selected_course
    if selected_session != "All":
        query["session_id"] = selected_session
    if selected_status != "All":
        query["status"] = selected_status
    if min_risk > 0:
        query["min_risk_score"] = min_risk
    if max_risk < 1:
        query["max_risk_score"] = max_risk
    if use_date_filter:
        query["start_date"] = _iso_range_start(start_date)
        query["end_date"] = _iso_range_end(end_date)

    checkins_response, checkins_error = request_with_retry(
        "GET",
        f"{API_BASE_URL}/checkins/",
        params=query,
        headers=get_headers(),
        timeout=20,
        retries=2,
    )
    if checkins_response is None:
        st.error(f"Failed to load check-ins: {checkins_error or 'request failed'}")
        return
    if checkins_response.status_code != 200:
        st.error(f"Failed to load check-ins ({checkins_response.status_code}): {response_error(checkins_response)}")
        return

    checkins_payload = parse_json(checkins_response) or {}
    items = checkins_payload.get("items", []) if isinstance(checkins_payload, dict) else []
    total = checkins_payload.get("total", len(items)) if isinstance(checkins_payload, dict) else len(items)

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Total Returned", len(items))
    with m2:
        st.metric("Total Matching", total)
    with m3:
        flagged = sum(1 for row in items if str(row.get("status") or "").lower() in {"flagged", "appealed"})
        st.metric("Needs Review", flagged)
    with m4:
        st.metric("Avg Risk (Page)", f"{_safe_avg_risk(items):.3f}")

    if not items:
        st.info("No check-ins matched the selected filters.")
        return

    normalized = []
    for row in items:
        normalized.append(
            {
                "Check-in ID": row.get("id"),
                "Student Name": row.get("student_name"),
                "Student Email": row.get("student_email"),
                "Student ID": row.get("student_id"),
                "Course Code": row.get("course_code"),
                "Session ID": row.get("session_id"),
                "Session Name": row.get("session_name"),
                "Checked In At": row.get("checked_in_at"),
                "Status": row.get("status"),
                "Risk Score": row.get("risk_score"),
                "Liveness Passed": row.get("liveness_passed"),
                "Liveness Score": row.get("liveness_score"),
                "Face Match Score": row.get("face_match_score"),
                "Distance From Venue (m)": row.get("distance_from_venue_meters"),
                "Latitude": row.get("latitude"),
                "Longitude": row.get("longitude"),
                "Risk Factors": _stringify(row.get("risk_factors")),
                "Risk Signals": _stringify(row.get("risk_signals")),
                "Appeal Reason": row.get("appeal_reason"),
                "Appealed At": row.get("appealed_at"),
            }
        )

    df = pd.DataFrame(normalized)
    if "Status" in df.columns:
        st.dataframe(
            df.style.map(
                lambda value: f"color: {_checkin_status_color(str(value))}; font-weight: 600;",
                subset=["Status"],
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)

    ex1, ex2 = st.columns(2)
    with ex1:
        st.download_button(
            "Download CSV",
            data=df.to_csv(index=False),
            file_name=f"checkins_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True,
            key="global_checkins_export_csv",
        )
    with ex2:
        st.download_button(
            "Download JSON",
            data=df.to_json(orient="records", indent=2),
            file_name=f"checkins_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True,
            key="global_checkins_export_json",
        )

    pending_items = [
        row for row in items
        if str(row.get("status") or "").lower() in {"flagged", "appealed"}
    ]
    if pending_items:
        st.markdown("---")
        st.subheader("Needs Review Actions")
        st.caption("Open the selected flagged/appealed check-in directly in `Review Appeals`.")

        for idx, row in enumerate(pending_items[:25]):
            checkin_id = str(row.get("id") or "").strip()
            if not checkin_id:
                continue
            student_name = str(row.get("student_name") or "Unknown Student")
            status_value = str(row.get("status") or "flagged")
            risk_value = float(row.get("risk_score") or 0.0)
            session_id = str(row.get("session_id") or "").strip()
            course_id = str(row.get("course_id") or "").strip()

            c1, c2, c3, c4, c5 = st.columns([2.2, 1, 1, 1.6, 1])
            with c1:
                st.write(f"**{student_name}**")
                st.caption(checkin_id)
            with c2:
                st.write(status_value.upper())
            with c3:
                st.write(f"{risk_value:.2f}")
            with c4:
                st.write(row.get("session_name") or session_id or "N/A")
            with c5:
                if st.button("Review", key=f"open_review_{checkin_id}_{idx}", use_container_width=True):
                    _open_review_queue(checkin_id=checkin_id, session_id=session_id, course_id=course_id)


if __name__ == "__main__":
    main()

