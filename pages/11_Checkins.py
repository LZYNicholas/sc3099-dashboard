"""SAIV Instructor Dashboard - Check-ins View

Dedicated check-ins explorer with filters, near-real-time refresh, and exports.
"""

import json
from datetime import date, datetime, time, timezone

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components
try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

from lib.auth_state import API_BASE_URL, get_auth_headers, require_auth
from lib.response_utils import bool_query, fetch_all_items

st.set_page_config(page_title="Check-ins - SAIV Dashboard", layout="wide")


def get_headers():
    return get_auth_headers()


def response_error(response: requests.Response | None, fallback: str = "Unknown error") -> str:
    if response is None:
        return "Connection error"
    try:
        payload = response.json()
    except Exception:
        payload = None
    if isinstance(payload, dict):
        detail = payload.get("detail") or payload.get("message") or payload.get("error")
        if detail:
            return str(detail)
    text = (response.text or "").strip()
    return text or fallback


def _iso_range_start(d: date | None) -> str | None:
    if d is None:
        return None
    return datetime.combine(d, time.min, tzinfo=timezone.utc).isoformat()


def _iso_range_end(d: date | None) -> str | None:
    if d is None:
        return None
    return datetime.combine(d, time.max, tzinfo=timezone.utc).isoformat()


def _stringify(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        try:
            return json.dumps(value, ensure_ascii=True)
        except Exception:
            return str(value)
    return str(value)


def _status_color(status: str) -> str:
    status = (status or "").lower()
    if status == "approved":
        return "green"
    if status in {"flagged", "appealed"}:
        return "orange"
    if status == "rejected":
        return "red"
    return "gray"


def _inject_auto_refresh(seconds: int) -> None:
    if seconds <= 0:
        return
    interval_ms = int(seconds * 1000)
    if st_autorefresh is not None:
        st_autorefresh(interval=interval_ms, key=f"checkins_autorefresh_{seconds}")
        return

    components.html(
        f"""
        <script>
          setTimeout(function () {{
            window.parent.location.reload();
          }}, {interval_ms});
        </script>
        """,
        height=0,
        width=0,
    )


def main():
    require_auth()
    current_role = str((st.session_state.get("user") or {}).get("role", "")).strip().lower()
    if current_role not in {"ta", "instructor", "admin"}:
        st.error("Access denied. This page is restricted to TAs, instructors, and admins.")
        st.stop()

    st.title("Check-ins View")
    st.markdown("Filter attendance records, inspect risk signals, and export gradebook-ready datasets.")

    try:
        courses = fetch_all_items(
            f"{API_BASE_URL}/courses/",
            headers=get_headers(),
            params={"is_active": bool_query(True)},
            timeout=10,
            page_size=200,
        )
    except Exception:
        courses = []

    course_options = {"All": "All Courses"}
    for c in courses:
        cid = c.get("id")
        if isinstance(cid, str):
            course_options[cid] = f"{c.get('code', 'N/A')} - {c.get('name', 'Unnamed')}"

    sessions_by_course: dict[str, list[dict]] = {}
    try:
        all_sessions = fetch_all_items(
            f"{API_BASE_URL}/sessions/",
            headers=get_headers(),
            params={"limit": 200},
            timeout=10,
            page_size=200,
        )
        for s in all_sessions:
            sid = s.get("course_id")
            if isinstance(sid, str):
                sessions_by_course.setdefault(sid, []).append(s)
    except Exception:
        pass

    with st.sidebar:
        st.markdown("### Filters")
        selected_course = st.selectbox(
            "Course",
            options=list(course_options.keys()),
            format_func=lambda x: course_options.get(x, x),
        )

        session_choices = ["All"]
        if selected_course != "All":
            for s in sessions_by_course.get(selected_course, []):
                sid = s.get("id")
                if isinstance(sid, str):
                    session_choices.append(sid)
        selected_session = st.selectbox(
            "Session",
            options=session_choices,
            format_func=lambda x: "All Sessions" if x == "All" else x,
        )

        selected_status = st.selectbox(
            "Status",
            options=["All", "pending", "approved", "flagged", "rejected", "appealed"],
        )
        min_risk = st.slider("Min Risk Score", 0.0, 1.0, 0.0, 0.01)
        max_risk = st.slider("Max Risk Score", 0.0, 1.0, 1.0, 0.01)
        use_date_filter = st.checkbox("Use Date Range", value=False)
        start_date = st.date_input("Start Date", value=date.today(), disabled=not use_date_filter)
        end_date = st.date_input("End Date", value=date.today(), disabled=not use_date_filter)
        page_limit = st.selectbox("Page Size", options=[50, 100, 200], index=1)
        auto_refresh_seconds = st.selectbox("Auto Refresh", options=[0, 15, 30, 60], index=2)

    if auto_refresh_seconds > 0:
        _inject_auto_refresh(auto_refresh_seconds)
        st.caption(f"Auto-refresh enabled every {auto_refresh_seconds}s")

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
    start_iso = _iso_range_start(start_date if use_date_filter else None)
    end_iso = _iso_range_end(end_date if use_date_filter else None)
    if start_iso:
        query["start_date"] = start_iso
    if end_iso:
        query["end_date"] = end_iso

    col_a, col_b = st.columns([1, 4])
    with col_a:
        if st.button("Refresh", use_container_width=True):
            st.rerun()

    response = requests.get(
        f"{API_BASE_URL}/checkins/",
        params=query,
        headers=get_headers(),
        timeout=20,
    )

    if response.status_code != 200:
        st.error(f"Failed to load check-ins ({response.status_code}): {response_error(response)}")
        st.stop()

    payload = response.json()
    items = payload.get("items", []) if isinstance(payload, dict) else []
    total = payload.get("total", len(items)) if isinstance(payload, dict) else len(items)

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Total Returned", len(items))
    with m2:
        st.metric("Total Matching", total)
    with m3:
        flagged = sum(1 for row in items if row.get("status") in {"flagged", "appealed"})
        st.metric("Needs Review", flagged)
    with m4:
        avg_risk = pd.to_numeric(pd.Series([row.get("risk_score") for row in items]), errors="coerce").mean()
        st.metric("Avg Risk (Page)", f"{0.0 if pd.isna(avg_risk) else avg_risk:.3f}")

    if not items:
        st.info("No check-ins matched the selected filters.")
        st.stop()

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

    st.markdown("### Check-in Records")
    if "Status" in df.columns:
        st.dataframe(
            df.style.map(
                lambda v: f"color: {_status_color(str(v))}; font-weight: 600;",
                subset=["Status"],
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)

    export_col1, export_col2 = st.columns(2)
    with export_col1:
        csv_data = df.to_csv(index=False)
        st.download_button(
            "Download CSV",
            data=csv_data,
            file_name=f"checkins_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with export_col2:
        json_data = df.to_json(orient="records", indent=2)
        st.download_button(
            "Download JSON",
            data=json_data,
            file_name=f"checkins_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True,
        )


if __name__ == "__main__":
    main()
