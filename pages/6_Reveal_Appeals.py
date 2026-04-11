"""
SAIV Dashboard - Review Appeals
Allows instructors/TAs to review flagged and appealed check-ins.
"""

import requests
import streamlit as st
import streamlit.components.v1 as components

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

from lib.auth_state import API_BASE_URL, get_auth_headers, require_auth
from lib.response_utils import friendly_error
from lib.time_utils import format_sgt
from lib.ui_theme import apply_theme

st.set_page_config(page_title="Review Appeals - SAIV", layout="wide", initial_sidebar_state="expanded")
apply_theme()
AUTO_REFRESH_SECONDS = 30


def _inject_auto_refresh(seconds: int) -> None:
    if seconds <= 0:
        return
    interval_ms = int(seconds * 1000)
    if st_autorefresh is not None:
        st_autorefresh(interval=interval_ms, key=f"review_autorefresh_{seconds}")
        return
    st.caption("Auto-refresh dependency missing; polling is temporarily disabled on this page.")


def _format_dt(value):
    if not value:
        return "-"
    try:
        return format_sgt(value, "%d %b %Y, %I:%M %p SGT")
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


def _pass_fail_na(value):
    if value is True:
        return "Passed"
    if value is False:
        return "Failed"
    return "N/A"


def fetch_flagged_checkins(limit: int = 100):
    try:
        page_size = max(1, min(int(limit), 200))
        offset = 0
        items: list[dict] = []

        while True:
            response = requests.get(
                f"{API_BASE_URL}/checkins/flagged",
                params={"limit": page_size, "offset": offset},
                headers=get_auth_headers(),
                timeout=10,
            )
            if response.status_code != 200:
                return False, f"Error {response.status_code}: {response.text}"

            data = response.json()
            if isinstance(data, list):
                # Fallback for non-paginated payloads.
                return True, data
            if not isinstance(data, dict):
                return True, items

            page_items = data.get("items", [])
            if not isinstance(page_items, list) or not page_items:
                break

            items.extend(page_items)

            total = data.get("total")
            if isinstance(total, int) and len(items) >= total:
                break
            if len(page_items) < page_size:
                break
            offset += page_size

        return True, items
    except Exception as e:
        return False, friendly_error(e, "Couldn't load check-ins right now.")


def fetch_reviewed_checkins(
    *,
    course_id: str | None = None,
    session_id: str | None = None,
    limit: int = 100,
) -> tuple[bool, list[dict] | str]:
    try:
        status_targets = ["approved", "rejected"]
        per_status_limit = max(1, min(limit // max(1, len(status_targets)), 100))
        collected: list[dict] = []

        for status in status_targets:
            offset = 0
            while True:
                params: dict[str, object] = {
                    "status": status,
                    "limit": per_status_limit,
                    "offset": offset,
                }
                if course_id and course_id != "All":
                    params["course_id"] = course_id
                if session_id and session_id != "All":
                    params["session_id"] = session_id

                response = requests.get(
                    f"{API_BASE_URL}/checkins/",
                    params=params,
                    headers=get_auth_headers(),
                    timeout=10,
                )
                if response.status_code != 200:
                    return False, f"Error {response.status_code}: {response.text}"

                payload = response.json()
                if not isinstance(payload, dict):
                    break

                items = payload.get("items", [])
                if not isinstance(items, list) or not items:
                    break

                collected.extend(items)
                if len(items) < per_status_limit:
                    break
                offset += per_status_limit
                if offset >= per_status_limit * 2:
                    break

        reviewed_only: list[dict] = []
        for item in collected:
            reviewed_at = item.get("reviewed_at")
            reviewed_by_id = item.get("reviewed_by_id")
            review_notes = item.get("review_notes")
            if reviewed_at or reviewed_by_id or (isinstance(review_notes, str) and review_notes.strip()):
                reviewed_only.append(item)

        def sort_key(item: dict):
            ts = item.get("reviewed_at") or item.get("checked_in_at") or ""
            return str(ts)

        reviewed_only.sort(key=sort_key, reverse=True)
        return True, reviewed_only[:limit]
    except Exception as e:
        return False, friendly_error(e, "Couldn't update this review right now.")


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
        return False, friendly_error(e, "Couldn't update this review right now.")


def _render_review_modal_content(checkin: dict):
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
    liveness_score = checkin.get("liveness_score")
    face_match_score = checkin.get("face_match_score")
    face_match_passed = checkin.get("face_match_passed")

    risk_lbl = _risk_label(risk_score)

    st.markdown(f"### {student_name}" + (f"  \n`{student_email}`" if student_email else ""))
    st.caption(f"Status: {str(status).upper()} | Check-in ID: `{checkin_id}`")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Session", session_name)
    c2.metric("Course", f"{course_code}" if course_code else "-")
    score_txt = f"{float(risk_score):.2f}" if risk_score is not None else "N/A"
    c3.metric("Risk Score", score_txt)
    c4.metric("Risk Level", risk_lbl)

    st.markdown("#### Verification Factors")
    vf1, vf2, vf3 = st.columns(3)
    with vf1:
        st.metric("Liveness", _pass_fail_na(liveness))
    with vf2:
        st.metric("Face Match", _pass_fail_na(face_match_passed))
    with vf3:
        if distance is not None:
            try:
                dist_text = f"{float(distance):.0f}m"
            except Exception:
                dist_text = str(distance)
            st.metric("Location Signal", "Available")
            st.caption(f"Distance from venue: {dist_text}")
        else:
            st.metric("Location Signal", "N/A")
            st.caption("Distance from venue unavailable.")

    d1, d2 = st.columns(2)
    d1.caption(f"Checked in: {_format_dt(checked_in_at)}")
    d2.caption(f"Appealed at: {_format_dt(appealed_at)}" if appealed_at else "Appealed at: -")

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

    if status not in ("flagged", "appealed"):
        st.warning("This check-in is not reviewable from this modal.")
        return

    review_notes = st.text_area(
        "Review Notes (optional)",
        key=f"review_notes_modal_{checkin_id}",
        placeholder="e.g. Verified student was in class via WiFi logs; GPS inaccuracy confirmed.",
        height=90,
    )
    a1, a2 = st.columns(2)
    if a1.button("Approve", key=f"approve_modal_{checkin_id}", type="primary", use_container_width=True):
        with st.spinner("Approving..."):
            success, result = review_checkin(checkin_id, "approved", review_notes)
        if success:
            st.session_state.pop("review_modal_id", None)
            st.rerun()
        else:
            st.error(friendly_error(result, "Couldn't approve this check-in right now."))
    if a2.button("Reject", key=f"reject_modal_{checkin_id}", use_container_width=True):
        with st.spinner("Rejecting..."):
            success, result = review_checkin(checkin_id, "rejected", review_notes)
        if success:
            st.session_state.pop("review_modal_id", None)
            st.rerun()
        else:
            st.error(friendly_error(result, "Couldn't reject this check-in right now."))


if hasattr(st, "dialog"):
    @st.dialog("Review Check-in", width="large")
    def _review_modal(checkin: dict):
        _render_review_modal_content(checkin)
else:
    def _review_modal(checkin: dict):
        st.markdown("### Review Check-in")
        _render_review_modal_content(checkin)


def _render_collapsed_item(checkin: dict, index: int) -> None:
    checkin_id = str(checkin.get("id") or "")
    student_name = checkin.get("student_name", "Unknown Student")
    session_name = checkin.get("session_name", "Unknown Session")
    course_code = checkin.get("course_code", "N/A")
    status = str(checkin.get("status", "unknown")).upper()
    risk_score = checkin.get("risk_score")
    score_txt = f"{float(risk_score):.2f}" if risk_score is not None else "N/A"
    checked_in_at = _format_dt(checkin.get("checked_in_at"))

    header = f"{student_name} | {course_code} | {session_name} | {status} | Risk {score_txt}"
    with st.expander(header, expanded=False):
        r1, r2 = st.columns([3, 1])
        with r1:
            st.caption(f"Checked in: {checked_in_at}")
            st.caption(f"Check-in ID: `{checkin_id}`")
        with r2:
            if st.button("Review", key=f"open_review_modal_{checkin_id}_{index}", use_container_width=True):
                st.session_state["review_modal_id"] = checkin_id
                st.rerun()


def main():
    require_auth()

    st.title("Review Appeals & Flagged Check-ins")
    st.markdown(
        "Review check-ins that have been **flagged** by the risk system or **appealed** by students. "
        "You can approve or reject each one with optional review notes."
    )

    _inject_auto_refresh(AUTO_REFRESH_SECONDS)
    st.caption(f"Auto-refresh enabled every {AUTO_REFRESH_SECONDS}s")

    with st.spinner("Loading flagged check-ins..."):
        success, data = fetch_flagged_checkins(limit=100)

    if not success:
        st.error(friendly_error(data, "Couldn't load check-ins right now."))
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
    else:
        def sort_key(c):
            status_order = {"appealed": 0, "flagged": 1}
            return (status_order.get(c.get("status", ""), 2), -(c.get("risk_score") or 0))

        checkins.sort(key=sort_key)

        st.markdown("##### Pending Items")
        for i, checkin in enumerate(checkins):
            _render_collapsed_item(checkin, i)

        modal_id = str(st.session_state.get("review_modal_id") or "").strip()
        if modal_id:
            selected = next((c for c in checkins if str(c.get("id") or "") == modal_id), None)
            if selected is not None:
                _review_modal(selected)
            else:
                st.session_state.pop("review_modal_id", None)

    st.markdown("---")
    if "show_review_history" not in st.session_state:
        st.session_state["show_review_history"] = False

    if st.button(
        "Review History" if not st.session_state["show_review_history"] else "Hide Review History",
        key="toggle_review_history",
        use_container_width=True,
    ):
        st.session_state["show_review_history"] = not st.session_state["show_review_history"]
        st.rerun()

    if st.session_state["show_review_history"]:
        st.subheader("Reviewed History")
        st.caption("Approved and rejected check-ins, including recorded review notes.")

        reviewed_ok, reviewed_payload = fetch_reviewed_checkins(
            course_id=selected_course,
            session_id=selected_session,
            limit=100,
        )
        if not reviewed_ok:
            st.warning(friendly_error(reviewed_payload, "Couldn't load reviewed history right now."))
        else:
            reviewed_items = reviewed_payload if isinstance(reviewed_payload, list) else []
            if not reviewed_items:
                st.info("No reviewed check-ins found for the current filters.")
            else:
                rows = []
                for row in reviewed_items:
                    rows.append(
                        {
                            "Reviewed At": _format_dt(row.get("reviewed_at")),
                            "Status": str(row.get("status") or "").upper(),
                            "Student": row.get("student_name") or "-",
                            "Course": row.get("course_code") or "-",
                            "Session": row.get("session_name") or "-",
                            "Risk Score": row.get("risk_score"),
                            "Reviewer ID": row.get("reviewed_by_id") or "-",
                            "Review Notes": row.get("review_notes") or "",
                        }
                    )

                st.dataframe(rows, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
else:
    main()
