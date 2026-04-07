"""
SAIV Dashboard - Review Appeals
Allows instructors/TAs to review flagged and appealed check-ins.
"""

import time
from datetime import datetime

import requests
import streamlit as st
import streamlit.components.v1 as components

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

from lib.auth_state import API_BASE_URL, get_auth_headers, require_auth

st.set_page_config(page_title="Review Appeals - SAIV", layout="wide", initial_sidebar_state="expanded")


def _inject_auto_refresh(seconds: int) -> None:
    if seconds <= 0:
        return
    interval_ms = int(seconds * 1000)
    if st_autorefresh is not None:
        st_autorefresh(interval=interval_ms, key=f"review_autorefresh_{seconds}")
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


def _format_dt(value):
    if not value:
        return "-"
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y, %I:%M %p")
    except Exception:
        return str(value)


def _risk_label(score):
    if score is None:
        return "N/A"
    if score < 0.3:
        return "LOW"
    if score < 0.5:
        return "MEDIUM"
    if score < 0.7:
        return "HIGH"
    return "CRITICAL"


def fetch_flagged_checkins(limit: int = 100):
    try:
        response = requests.get(
            f"{API_BASE_URL}/checkins/flagged",
            params={"limit": limit},
            headers=get_auth_headers(),
            timeout=10,
        )
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                return True, data
            if isinstance(data, dict) and "items" in data:
                return True, data["items"]
            return True, data
        return False, f"Error {response.status_code}: {response.text}"
    except Exception as e:
        return False, f"Connection error: {e}"


def review_checkin(checkin_id: str, status: str, review_notes: str):
    try:
        headers = get_auth_headers()
        headers["Content-Type"] = "application/json"
        response = requests.post(
            f"{API_BASE_URL}/checkins/{checkin_id}/review",
            json={"status": status, "review_notes": review_notes},
            headers=headers,
            timeout=10,
        )
        if response.status_code == 200:
            return True, response.json()
        try:
            err = response.json().get("detail", response.text)
        except Exception:
            err = response.text
        return False, f"Error {response.status_code}: {err}"
    except Exception as e:
        return False, f"Connection error: {e}"


def render_checkin_card(checkin: dict, index: int):
    checkin_id = checkin.get("id", "")
    status = checkin.get("status", "unknown")
    student_name = checkin.get("student_name", "Unknown Student")
    student_email = checkin.get("student_email", "")
    session_name = checkin.get("session_name", "Unknown Session")
    course_code = checkin.get("course_code", "")
    risk_score = checkin.get("risk_score")
    risk_factors = checkin.get("risk_factors", [])
    appeal_reason = checkin.get("appeal_reason", "")
    appealed_at = checkin.get("appealed_at", "")
    checked_in_at = checkin.get("checked_in_at", "")
    distance = checkin.get("distance_from_venue_meters")
    liveness = checkin.get("liveness_passed")

    risk_lbl = _risk_label(risk_score)

    with st.container():
        st.markdown("---")

        col_main, col_status = st.columns([5, 1])
        with col_main:
            st.markdown(
                f"### {student_name}" + (f"  \n`{student_email}`" if student_email else "")
            )
        with col_status:
            st.markdown(f"**Status:** `{str(status).upper()}`")

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Session", session_name)
        with c2:
            st.metric("Course", f"{course_code}" if course_code else "-")
        with c3:
            score_txt = f"{float(risk_score):.2f}" if risk_score is not None else "N/A"
            st.metric("Risk Score", score_txt)
        with c4:
            st.metric("Risk Level", risk_lbl)

        d1, d2, d3 = st.columns(3)
        with d1:
            st.caption(f"Checked in: {_format_dt(checked_in_at)}")
        with d2:
            if distance is not None:
                st.caption(f"Distance: {float(distance):.0f}m from venue")
            else:
                st.caption("Distance: N/A")
        with d3:
            if liveness is not None:
                st.caption(f"Liveness: {'Passed' if liveness else 'Failed'}")
            else:
                st.caption("Liveness: N/A")

        if risk_factors:
            with st.expander("Risk Factors", expanded=False):
                for rf in risk_factors:
                    if isinstance(rf, dict):
                        rf_type = rf.get("type", rf.get("signal_type", "unknown"))
                        rf_severity = rf.get("severity", "")
                        rf_weight = rf.get("weight", "")
                        details = []
                        if rf_severity:
                            details.append(f"severity: {rf_severity}")
                        if rf_weight:
                            details.append(f"weight: {rf_weight}")
                        detail_str = f" ({', '.join(details)})" if details else ""
                        st.markdown(f"- `{rf_type}`{detail_str}")
                    else:
                        st.markdown(f"- {rf}")

        if status == "appealed" or appeal_reason:
            st.info(
                f"**Student's Appeal Reason:**\n\n{appeal_reason or '(no reason provided)'}"
                + (f"\n\n*Appealed on: {_format_dt(appealed_at)}*" if appealed_at else "")
            )

        if status in ("flagged", "appealed"):
            st.markdown("#### Take Action")

            review_notes = st.text_area(
                "Review Notes (optional)",
                key=f"review_notes_{checkin_id}_{index}",
                placeholder="e.g. Verified student was in class via WiFi logs; GPS inaccuracy confirmed.",
                height=80,
            )

            action_col1, action_col2, _ = st.columns([1, 1, 2])
            with action_col1:
                if st.button("Approve", key=f"approve_{checkin_id}_{index}", type="primary", use_container_width=True):
                    with st.spinner("Approving..."):
                        success, result = review_checkin(checkin_id, "approved", review_notes)
                    if success:
                        st.success(f"Check-in approved for {student_name}!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"Failed to approve: {result}")

            with action_col2:
                if st.button("Reject", key=f"reject_{checkin_id}_{index}", use_container_width=True):
                    with st.spinner("Rejecting..."):
                        success, result = review_checkin(checkin_id, "rejected", review_notes)
                    if success:
                        st.warning(f"Check-in rejected for {student_name}.")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"Failed to reject: {result}")


def main():
    require_auth()

    st.title("Review Appeals & Flagged Check-ins")
    st.markdown(
        "Review check-ins that have been **flagged** by the risk system or **appealed** by students. "
        "You can approve or reject each one with optional review notes."
    )

    auto_refresh_seconds = st.sidebar.selectbox("Auto Refresh", [0, 15, 30, 60], index=2)
    if auto_refresh_seconds > 0:
        _inject_auto_refresh(auto_refresh_seconds)
        st.caption(f"Auto-refresh enabled every {auto_refresh_seconds}s")

    with st.spinner("Loading flagged check-ins..."):
        success, data = fetch_flagged_checkins(limit=100)

    if not success:
        st.error(f"Failed to load check-ins: {data}")
        return

    checkins = data if isinstance(data, list) else []

    prefill_checkin_id = str(st.session_state.pop("review_queue_checkin_id", "") or "").strip()
    prefill_session_id = str(st.session_state.pop("review_queue_session_id", "") or "").strip()
    prefill_course_id = str(st.session_state.pop("review_queue_course_id", "") or "").strip()

    course_options = {"All": "All Courses"}
    for item in checkins:
        course_id = str(item.get("course_id") or "").strip()
        course_code = str(item.get("course_code") or "").strip()
        if course_id:
            course_options[course_id] = course_code or course_id

    session_labels: dict[str, str] = {}
    for item in checkins:
        session_id = str(item.get("session_id") or "").strip()
        session_name = str(item.get("session_name") or "Unknown Session").strip()
        course_code = str(item.get("course_code") or "").strip()
        if session_id:
            session_labels[session_id] = f"{session_name} ({course_code or 'N/A'})"

    course_keys = list(course_options.keys())
    selected_course_index = 0
    if prefill_course_id and prefill_course_id in course_options:
        selected_course_index = course_keys.index(prefill_course_id)

    filter_col1, filter_col2, filter_col3, filter_col4 = st.columns([1.5, 1.5, 1.5, 1])
    with filter_col1:
        status_filter = st.selectbox("Filter by status", ["All", "Flagged", "Appealed"], index=0)
    with filter_col2:
        selected_course = st.selectbox(
            "Course",
            options=course_keys,
            index=selected_course_index,
            format_func=lambda x: course_options.get(x, x),
        )
    with filter_col3:
        session_option_ids = ["All"]
        for session_id in sorted(session_labels.keys()):
            if selected_course == "All":
                session_option_ids.append(session_id)
            else:
                match = any(
                    str(item.get("session_id") or "") == session_id
                    and str(item.get("course_id") or "") == selected_course
                    for item in checkins
                )
                if match:
                    session_option_ids.append(session_id)

        selected_session_index = 0
        if prefill_session_id and prefill_session_id in session_option_ids:
            selected_session_index = session_option_ids.index(prefill_session_id)

        selected_session = st.selectbox(
            "Session",
            options=session_option_ids,
            index=selected_session_index,
            format_func=lambda x: "All Sessions" if x == "All" else session_labels.get(x, x),
        )
    with filter_col4:
        if st.button("Refresh", use_container_width=True):
            st.rerun()

    if prefill_session_id:
        st.info("Focused on the session selected from Session Monitoring.")
    if prefill_checkin_id:
        st.info("Focused on the check-in selected from Global Check-ins.")

    if status_filter == "Flagged":
        checkins = [c for c in checkins if c.get("status") == "flagged"]
    elif status_filter == "Appealed":
        checkins = [c for c in checkins if c.get("status") == "appealed"]

    if selected_course != "All":
        checkins = [c for c in checkins if str(c.get("course_id") or "") == selected_course]
    if selected_session != "All":
        checkins = [c for c in checkins if str(c.get("session_id") or "") == selected_session]
    if prefill_checkin_id:
        exact = [c for c in checkins if str(c.get("id") or "") == prefill_checkin_id]
        if exact:
            checkins = exact

    total = len(checkins)
    flagged_count = sum(1 for c in checkins if c.get("status") == "flagged")
    appealed_count = sum(1 for c in checkins if c.get("status") == "appealed")

    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Total Pending Review", total)
    with m2:
        st.metric("Flagged", flagged_count)
    with m3:
        st.metric("Appealed", appealed_count)

    if total == 0:
        st.success("No check-ins pending review. All caught up!")
        return

    def sort_key(c):
        status_order = {"appealed": 0, "flagged": 1}
        return (status_order.get(c.get("status", ""), 2), -(c.get("risk_score") or 0))

    checkins.sort(key=sort_key)

    for i, checkin in enumerate(checkins):
        render_checkin_card(checkin, i)


if __name__ == "__main__":
    main()
else:
    main()
