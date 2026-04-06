"""SAIV Instructor Dashboard - Sessions Monitoring Page
"""

import streamlit as st
import streamlit.components.v1 as components
import requests
import pandas as pd
import os
import json
from datetime import datetime, timezone
from urllib.parse import quote, urlencode
from zoneinfo import ZoneInfo
from lib.auth_state import API_BASE_URL, get_auth_headers, require_auth
from lib.response_utils import bool_query, extract_items, fetch_all_items, request_with_retry, response_error, parse_json

try:
    from st_keyup import st_keyup
except Exception:
    st_keyup = None
try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

# Page configuration
st.set_page_config(page_title="Sessions - SAIV Dashboard", layout="wide")

SG_TZ = ZoneInfo("Asia/Singapore")
FRONTEND_BASE_URL = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")

def get_headers():
    return get_auth_headers()


def _inject_auto_refresh(seconds: int) -> None:
    if seconds <= 0:
        return
    interval_ms = int(seconds * 1000)
    if st_autorefresh is not None:
        st_autorefresh(interval=interval_ms, key=f"sessions_autorefresh_{seconds}")
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


def get_status_color(status):
    """Get color for status badge"""
    colors = {
        'scheduled': '',
        'active': '',
        'closed': '⚫',
        'completed': '⚫',
        'cancelled': ''
    }
    return colors.get(status, '⚪')


def parse_iso_utc(value):
    if not value:
        return None
    ts = pd.to_datetime(value, errors='coerce')
    if pd.isna(ts):
        return None
    if ts.tzinfo is None:
        return ts.tz_localize(SG_TZ)
    return ts.tz_convert(SG_TZ)


def format_datetime_local(value):
    ts = parse_iso_utc(value)
    if ts is None:
        return 'N/A'
    return ts.strftime('%Y-%m-%d %H:%M SGT')


def get_remaining_qr_ttl(expires_at):
    ts = parse_iso_utc(expires_at)
    if ts is None:
        return 0
    return max(0, int(ts.timestamp() - datetime.now(timezone.utc).timestamp()))


def get_checkin_count(session):
    return session.get('checked_in_count', session.get('checkin_count', 0))


def is_checkin_window_open(session):
    opens_at = parse_iso_utc(session.get('checkin_opens_at'))
    closes_at = parse_iso_utc(session.get('checkin_closes_at'))
    if opens_at is None or closes_at is None:
        return False
    now_sg = pd.Timestamp(datetime.now(SG_TZ))
    return opens_at <= now_sg <= closes_at


def fetch_session_qr(session_id):
    try:
        response, error = request_with_retry(
            "GET",
            f"{API_BASE_URL}/sessions/{session_id}/qr",
            headers=get_headers(),
            timeout=10,
            retries=2,
        )
        if response is None:
            return False, (error or "Failed to fetch QR code")
        if response.status_code == 200:
            payload = parse_json(response)
            if not isinstance(payload, dict):
                return False, 'Failed to fetch QR code'

            qr_payload = payload.get('qr_payload')
            qr_expires_at = payload.get('qr_expires_at') or payload.get('qr_code_expires_at')
            qr_code = payload.get('qr_code')

            if not qr_payload:
                return False, 'QR is not available for this session'

            ttl_seconds = payload.get('qr_ttl_seconds')
            if ttl_seconds is None and qr_expires_at:
                ttl_seconds = get_remaining_qr_ttl(qr_expires_at)

            return True, {
                'qr_payload': qr_payload,
                'qr_expires_at': qr_expires_at,
                'qr_ttl_seconds': ttl_seconds,
                'qr_code': qr_code
            }
        try:
            return False, response.json().get('detail', 'Failed to fetch QR code')
        except Exception:
            return False, 'Failed to fetch QR code'
    except Exception as error:
        return False, str(error)


def parse_qr_session_id(payload: str, fallback_session_id: str) -> str:
    try:
        data = json.loads(payload)
        if isinstance(data, dict) and data.get("sessionId"):
            return str(data["sessionId"])
    except Exception:
        pass
    return fallback_session_id


def build_direct_attendance_link(session_id: str, qr_payload: str | None = None) -> str:
    query_params = {"sessionId": session_id}
    if qr_payload:
        query_params["qr"] = qr_payload
    query = urlencode(query_params)
    return f"{FRONTEND_BASE_URL}/attendance?{query}"


def render_qr_block(qr_data, session_id):
    payload = qr_data.get('qr_payload', '')
    expires_at = qr_data.get('qr_expires_at')
    qr_code_image = qr_data.get('qr_code')

    if expires_at:
        st.caption(f"Available until {format_datetime_local(expires_at)}")

    if qr_code_image:
        st.image(qr_code_image, caption=f"Session QR - {session_id}", width=280)
    else:
        # Try local QR image generation first; fallback to a hosted QR renderer.
        try:
            import qrcode # type: ignore
            qr_img = qrcode.make(payload)
            st.image(qr_img, caption=f"Session QR - {session_id}", width=280)
        except Exception:
            qr_url = f"https://quickchart.io/qr?size=300&text={quote(payload)}"
            st.image(qr_url, caption=f"Session QR - {session_id}", width=280)

    linked_session_id = parse_qr_session_id(payload, session_id)
    attendance_link = build_direct_attendance_link(linked_session_id, payload)
    st.caption("Direct attendance link (equivalent to scanning this QR)")
    st.code(attendance_link)


def session_requires_qr(session) -> bool:
    return bool(session.get('qr_code_enabled'))


def can_manage_qr(role: str) -> bool:
    return role in {'instructor', 'admin'}


def can_manage_session(role: str) -> bool:
    return role in {'instructor', 'admin'}


def update_session_status(session_id, status):
    try:
        response, error = request_with_retry(
            "PATCH",
            f"{API_BASE_URL}/sessions/{session_id}",
            json={"status": status},
            headers={**get_headers(), "Content-Type": "application/json"},
            timeout=10,
            retries=2,
        )
        if response is None:
            return False, (error or "Failed to update session status")
        if response.status_code == 200:
            return True, None
        try:
            return False, response.json().get('detail', 'Failed to update session status')
        except Exception:
            return False, 'Failed to update session status'
    except Exception as error:
        return False, str(error)

def main():
    require_auth()
    current_role = str((st.session_state.get('user') or {}).get('role', '')).strip().lower()
    if current_role not in {"ta", "instructor", "admin"}:
        st.error("Access denied. This page is restricted to TAs, instructors, and admins.")
        st.stop()

    st.title("Session Monitoring")
    st.markdown("Monitor active sessions and view check-in details.")
    auto_refresh_seconds = st.sidebar.selectbox("Auto Refresh", [0, 15, 30, 60], index=2)
    if auto_refresh_seconds > 0:
        _inject_auto_refresh(auto_refresh_seconds)
        st.caption(f"Auto-refresh enabled every {auto_refresh_seconds}s")

    # Fetch active courses for filter (only show active courses)
    try:
        courses = fetch_all_items(
            f"{API_BASE_URL}/courses/",
            headers=get_headers(),
            params={"is_active": bool_query(True)},
            timeout=10,
            page_size=200,
        )
    except:
        courses = []

    # Track active course IDs for later use
    active_course_ids = {c['id'] for c in courses}

    # Filters row
    col1, col2, col3 = st.columns([3, 2, 1])
    with col1:
        course_filter = st.selectbox(
            "Filter by Course",
            options=['All'] + [c['id'] for c in courses],
            format_func=lambda x: 'All Courses' if x == 'All' else next((f"{c['code']} - {c['name']}" for c in courses if c['id'] == x), x)
        )
    with col2:
        status_filter = st.selectbox(
            "Filter by Status",
            options=['All', 'active', 'scheduled', 'closed', 'cancelled']
        )
    with col3:
        st.markdown("<div style='margin-top:28px'>", unsafe_allow_html=True)
        if st.button("Refresh", use_container_width=True, type="secondary"):
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("---")

    # Fetch sessions
    try:
        is_ta = current_role == 'ta'
        url = f"{API_BASE_URL}/sessions/my-sessions" if is_ta else f"{API_BASE_URL}/sessions/"
        params = {"limit": 100}
        if course_filter != 'All':
            params['course_id'] = course_filter

        response, error = request_with_retry(
            "GET",
            url,
            params=params,
            headers=get_headers(),
            timeout=10,
            retries=2,
        )
        if response is None:
            st.error(f"Failed to load sessions: {error or 'request failed'}")
            return

        if response.status_code == 200:
            sessions_data = parse_json(response)
            sessions = sessions_data.get('items', []) if isinstance(sessions_data, dict) else sessions_data

            # Apply status filter
            if status_filter != 'All':
                sessions = [s for s in sessions if s.get('status') == status_filter]

            if not sessions:
                st.info("No sessions found matching the filters.")
                return

            # Check for sessions with deleted courses
            sessions_with_deleted_courses = [s for s in sessions if s.get('course_id') not in active_course_ids]
            if sessions_with_deleted_courses:
                st.warning(f"⚠️ {len(sessions_with_deleted_courses)} session(s) belong to deleted courses and cannot accept check-ins.")

            # Scheduled Sessions Section
            scheduled_sessions = [s for s in sessions if s.get('status') == 'scheduled']
            if scheduled_sessions:
                sched_col1, sched_col2 = st.columns([3, 1])
                with sched_col1:
                    st.subheader(f"Scheduled Sessions ({len(scheduled_sessions)})")
                with sched_col2:
                    st.markdown("<div style='margin-top:8px'>", unsafe_allow_html=True)
                    if st_keyup is not None:
                        sched_search = st_keyup(
                            "Search scheduled",
                            placeholder="Filter by name or course...",
                            key="sched_search_live"
                        )
                    else:
                        sched_search = st.text_input(
                            "Search scheduled",
                            placeholder="Filter by name or course...",
                            label_visibility="collapsed",
                            key="sched_search"
                        )
                    st.markdown("</div>", unsafe_allow_html=True)

                filtered_scheduled = scheduled_sessions
                if sched_search:
                    q = sched_search.lower()
                    filtered_scheduled = [
                        s for s in scheduled_sessions
                        if q in s.get('name', '').lower() or q in s.get('course_name', '').lower()
                    ]

                if not filtered_scheduled:
                    st.info("No scheduled sessions match your search.")
                else:
                    for session in filtered_scheduled:
                        course_deleted = session.get('course_id') not in active_course_ids
                        title_suffix = " ⚠️ [COURSE DELETED]" if course_deleted else ""
                        with st.expander(f"**{session.get('name', 'Session')}** - {session.get('course_name', 'Course')}{title_suffix}", expanded=False):
                            if course_deleted:
                                st.error("⚠️ This session's course has been deleted.")

                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.write(f"**Type:** {session.get('session_type', 'N/A')}")
                                st.write(f"**Start:** {format_datetime_local(session.get('scheduled_start'))}")
                            with col2:
                                st.write(f"**End:** {format_datetime_local(session.get('scheduled_end'))}")
                                st.write(f"**Location:** {session.get('venue_name', session.get('location', 'N/A'))}")
                            with col3:
                                st.metric("Check-ins", get_checkin_count(session))

                            if can_manage_session(current_role):
                                action_col1, action_col2 = st.columns(2)
                                with action_col1:
                                    can_activate = not course_deleted
                                    if st.button("▶ Activate", key=f"activate_{session['id']}", disabled=not can_activate, use_container_width=True, type="primary"):
                                        ok, error = update_session_status(session['id'], 'active')
                                        if ok:
                                            st.success("Session activated.")
                                            st.rerun()
                                        else:
                                            st.error(error or "Failed to activate session.")
                                with action_col2:
                                    if st.button("Cancel", key=f"cancel_{session['id']}", use_container_width=True):
                                        ok, error = update_session_status(session['id'], 'cancelled')
                                        if ok:
                                            st.success("Session cancelled.")
                                            st.rerun()
                                        else:
                                            st.error(error or "Failed to cancel session.")
                            else:
                                st.caption("Session status controls are restricted to instructors and admins.")

                st.markdown("---")

            # Active Sessions Section
            active_sessions = [s for s in sessions if s.get('status') == 'active']
            if active_sessions:
                open_now_sessions = [s for s in active_sessions if is_checkin_window_open(s)]
                stale_active_sessions = [s for s in active_sessions if not is_checkin_window_open(s)]

                st.subheader(f"Active Sessions ({len(open_now_sessions)} open now / {len(active_sessions)} status-active)")

                if stale_active_sessions:
                    st.warning(
                        f"{len(stale_active_sessions)} session(s) are marked active but their check-in window is closed. "
                        "Close them to keep this list clean."
                    )

                for session in active_sessions:
                    course_deleted = session.get('course_id') not in active_course_ids
                    title_suffix = " ⚠️ [COURSE DELETED]" if course_deleted else ""
                    window_open = is_checkin_window_open(session)
                    window_suffix = " (Open Now)" if window_open else " (Window Closed)"

                    with st.expander(f"**{session.get('name', 'Session')}** - {session.get('course_name', 'Course')}{title_suffix}{window_suffix}", expanded=window_open):
                        if course_deleted:
                            st.error("⚠️ This session's course has been deleted. Check-ins may not work properly.")
                        elif not window_open:
                            st.warning("Check-in window is currently closed for this active session.")

                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.write(f"**Type:** {session.get('session_type', 'N/A')}")
                            st.write(f"**Start:** {format_datetime_local(session.get('scheduled_start'))}")
                        with col2:
                            st.write(f"**End:** {format_datetime_local(session.get('scheduled_end'))}")
                            st.write(f"**Location:** {session.get('venue_name', session.get('location', 'N/A'))}")
                        with col3:
                            # Quick stats for this session
                            st.metric("Check-ins", get_checkin_count(session))

                        next_actions = {
                            'scheduled': ['active', 'cancelled'],
                            'active': ['closed', 'cancelled'],
                            'closed': [],
                            'cancelled': []
                        }.get(session.get('status'), [])

                        if can_manage_session(current_role):
                            action_col1, action_col2, action_col3 = st.columns(3)
                            with action_col1:
                                can_activate = 'active' in next_actions and not course_deleted
                                if st.button("Activate", key=f"activate_{session['id']}", disabled=not can_activate, use_container_width=True):
                                    ok, error = update_session_status(session['id'], 'active')
                                    if ok:
                                        st.success("Session activated.")
                                        st.rerun()
                                    else:
                                        st.error(error or "Failed to activate session.")
                            with action_col2:
                                can_close = 'closed' in next_actions
                                if st.button("Close", key=f"close_{session['id']}", disabled=not can_close, use_container_width=True):
                                    ok, error = update_session_status(session['id'], 'closed')
                                    if ok:
                                        st.success("Session closed.")
                                        st.rerun()
                                    else:
                                        st.error(error or "Failed to close session.")
                            with action_col3:
                                can_cancel = 'cancelled' in next_actions
                                if st.button("Cancel", key=f"cancel_{session['id']}", disabled=not can_cancel, use_container_width=True):
                                    ok, error = update_session_status(session['id'], 'cancelled')
                                    if ok:
                                        st.success("Session cancelled.")
                                        st.rerun()
                                    else:
                                        st.error(error or "Failed to cancel session.")
                        else:
                            st.caption("Session status controls are restricted to instructors and admins.")

                        if window_open:
                            st.markdown("#### Session QR")
                            if not can_manage_qr(current_role):
                                st.info("QR display is restricted to instructor and admin roles.")
                            elif not session_requires_qr(session):
                                st.caption("QR check-in is disabled for this session. Students can submit attendance directly from the attendance page.")
                                direct_link = build_direct_attendance_link(session['id'])
                                st.caption("Direct attendance link (for testing)")
                                st.code(direct_link)
                            else:
                                state_key = f"session_qr_{session['id']}"
                                qr_payload = st.session_state.get(state_key)

                                btn_col1, btn_col2 = st.columns([1, 3])
                                with btn_col1:
                                    button_label = "Show QR" if qr_payload else "Generate QR"
                                    if st.button(
                                        button_label,
                                        key=f"qr_btn_{session['id']}",
                                        use_container_width=True
                                    ):
                                        ok, result = fetch_session_qr(session['id'])
                                        if ok:
                                            qr_payload = result
                                            st.session_state[state_key] = result
                                        else:
                                            st.error(result or "Could not generate QR")
                                with btn_col2:
                                    st.caption("Display the session QR while the check-in window is open.")

                                if qr_payload:
                                    render_qr_block(qr_payload, session['id'])
                                else:
                                    st.caption("No QR has been issued for this session yet.")

                        # Show check-ins for active session
                        if st.button(f"View Check-ins", key=f"view_{session['id']}"):
                            st.session_state[f"show_checkins_{session['id']}"] = True

                        if st.session_state.get(f"show_checkins_{session['id']}", False):
                            show_session_checkins(session['id'])

                st.markdown("---")

            # All Sessions Table
            st.subheader("All Sessions")

            # Prepare data for display
            display_data = []
            for s in sessions:
                course_deleted = s.get('course_id') not in active_course_ids
                course_display = s.get('course_name', s.get('course_code', 'N/A'))
                if course_deleted:
                    course_display = f"⚠️ {course_display} [DELETED]"

                display_data.append({
                    'Status': f"{get_status_color(s.get('status', ''))} {s.get('status', 'unknown').title()}",
                    'Name': s.get('name', 'N/A'),
                    'Course': course_display,
                    'Type': s.get('session_type', 'N/A'),
                    'Scheduled Start': format_datetime_local(s.get('scheduled_start')),
                    'Check-ins': get_checkin_count(s),
                    'ID': s.get('id', '')
                })

            df = pd.DataFrame(display_data)
            st.dataframe(df.drop(columns=['ID']), use_container_width=True, hide_index=True)

            # Export all sessions as CSV
            sessions_csv = df.drop(columns=['ID']).to_csv(index=False)
            st.download_button(
                "Download Sessions CSV",
                sessions_csv,
                "all_sessions.csv",
                "text/csv",
                use_container_width=True,
                key="csv_export_all_sessions",
            )

            # Session Details
            st.markdown("---")
            st.subheader("Session Details")

            session_options = {}
            for s in sessions:
                course_deleted = s.get('course_id') not in active_course_ids
                label = f"{s.get('name', 'Session')} ({s.get('course_name', 'Course')})"
                if course_deleted:
                    label = f"⚠️ {label}"
                session_options[s['id']] = label

            selected_session_id = st.selectbox(
                "Select a session to view details",
                options=list(session_options.keys()),
                format_func=lambda x: session_options[x]
            )

            if selected_session_id:
                show_session_details(selected_session_id, sessions, active_course_ids)

        else:
            st.error(f"Failed to load sessions ({response.status_code}): {response_error(response)}")

    except Exception as e:
        st.error(f"Connection error: {str(e)}")


def show_session_checkins(session_id):
    """Display check-ins for a session"""
    try:
        response, error = request_with_retry(
            "GET",
            f"{API_BASE_URL}/checkins/session/{session_id}",
            headers=get_headers(),
            timeout=10,
            retries=2,
        )
        if response is None:
            st.warning(f"Could not load check-ins: {error or 'request failed'}")
            return

        if response.status_code == 200:
            checkins = parse_json(response)
            if isinstance(checkins, dict):
                checkins = checkins.get('items', checkins.get('records', []))
            if checkins:
                st.markdown("#### Check-ins")
                for ci in checkins:
                    col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
                    with col1:
                        st.write(f"**{ci.get('student_name', 'Unknown')}**")
                    with col2:
                        st.write(format_datetime_local(ci.get('checked_in_at', ci.get('timestamp'))))
                    with col3:
                        st.write(f"Risk: {ci.get('risk_score', 0):.2f}")
                    with col4:
                        st.write(ci.get('status', ''))

                # CSV export for gradebook
                export_rows = []
                for ci in checkins:
                    export_rows.append({
                        'Check-in ID': ci.get('id', ''),
                        'Student ID': ci.get('student_id', ''),
                        'Student Name': ci.get('student_name', ''),
                        'Student Email': ci.get('student_email', ''),
                        'Session ID': ci.get('session_id', session_id),
                        'Timestamp': ci.get('checked_in_at', ci.get('timestamp', '')),
                        'Status': ci.get('status', ''),
                        'Risk Score': ci.get('risk_score', ''),
                        'Liveness Score': ci.get('liveness_score', ''),
                        'Face Match Score': ci.get('face_match_score', ''),
                        'Latitude': ci.get('latitude', ''),
                        'Longitude': ci.get('longitude', ''),
                    })
                csv_data = pd.DataFrame(export_rows).to_csv(index=False)
                st.download_button(
                    "Download Check-ins CSV (Gradebook)",
                    csv_data,
                    f"session_{session_id}_checkins.csv",
                    "text/csv",
                    use_container_width=True,
                    key=f"csv_export_{session_id}",
                )

                st.markdown("#### Check-in Detail")
                checkin_options = {
                    f"{ci.get('student_name', 'Unknown')} - {ci.get('id', 'N/A')}": ci.get('id')
                    for ci in checkins
                    if ci.get('id')
                }
                if checkin_options:
                    selected_checkin_label = st.selectbox(
                        "Select check-in",
                        options=list(checkin_options.keys()),
                        key=f"checkin_detail_select_{session_id}"
                    )
                    selected_checkin_id = checkin_options[selected_checkin_label]
                    if st.button("Load Check-in Detail", key=f"load_checkin_detail_{session_id}"):
                        detail_response, detail_error = request_with_retry(
                            "GET",
                            f"{API_BASE_URL}/checkins/{selected_checkin_id}",
                            headers=get_headers(),
                            timeout=10,
                            retries=2,
                        )
                        if detail_response is None:
                            st.warning(f"Could not load check-in detail: {detail_error or 'request failed'}")
                            return
                        if detail_response.status_code == 200:
                            detail = parse_json(detail_response)
                            st.json(detail)
                            # ...existing code...
                        else:
                            st.warning(f"Could not load check-in detail ({detail_response.status_code}): {response_error(detail_response)}")
            else:
                st.info("No check-ins yet.")
        else:
            st.warning("Could not load check-ins.")

    except Exception as e:
        st.warning(f"Error loading check-ins: {str(e)}")


def show_session_details(session_id, sessions, active_course_ids=None):
    """Display detailed session information"""
    session = next((s for s in sessions if s['id'] == session_id), None)
    if not session:
        return

    try:
        session_detail_response, _error = request_with_retry(
            "GET",
            f"{API_BASE_URL}/sessions/{session_id}",
            headers=get_headers(),
            timeout=10,
            retries=2,
        )
        if session_detail_response is not None and session_detail_response.status_code == 200:
            session_detail = parse_json(session_detail_response)
            if isinstance(session_detail, dict):
                session = {**session, **session_detail}
    except Exception:
        pass

    # Check if course is deleted
    if active_course_ids is None:
        active_course_ids = set()
    course_deleted = session.get('course_id') not in active_course_ids

    if course_deleted:
        st.error("⚠️ This session's course has been deleted. The session cannot accept new check-ins.")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Session Information")
        st.write(f"**Name:** {session.get('name', 'N/A')}")
        st.write(f"**Type:** {session.get('session_type', 'N/A')}")
        st.write(f"**Status:** {get_status_color(session.get('status', ''))} {session.get('status', 'unknown').title()}")
        st.write(f"**Location:** {session.get('venue_name', session.get('location', 'Not specified'))}")

    with col2:
        st.markdown("#### Timing")
        st.write(f"**Scheduled Start:** {format_datetime_local(session.get('scheduled_start'))}")
        st.write(f"**Scheduled End:** {format_datetime_local(session.get('scheduled_end'))}")
        st.write(f"**Check-in Opens:** {format_datetime_local(session.get('checkin_opens_at'))}")
        st.write(f"**Check-in Closes:** {format_datetime_local(session.get('checkin_closes_at'))}")
        if session.get('actual_start'):
            st.write(f"**Actual Start:** {format_datetime_local(session.get('actual_start'))}")
        if session.get('actual_end'):
            st.write(f"**Actual End:** {format_datetime_local(session.get('actual_end'))}")

    # Fetch session statistics
    try:
        stats_response, stats_error = request_with_retry(
            "GET",
            f"{API_BASE_URL}/stats/sessions/{session_id}",
            headers=get_headers(),
            timeout=10,
            retries=2,
        )
        if stats_response is None:
            st.warning(f"Could not load session statistics: {stats_error or 'request failed'}")
            return

        if stats_response.status_code == 200:
            stats = parse_json(stats_response) or {}

            st.markdown("---")
            st.markdown("#### Statistics")

            col1, col2, col3, col4 = st.columns(4)
            by_status = stats.get('by_status', {}) if isinstance(stats.get('by_status'), dict) else {}
            with col1:
                st.metric("Total Check-ins", stats.get('total_checkins', stats.get('checked_in_count', stats.get('checked_in', 0))))
            with col2:
                st.metric("Approved", stats.get('approved_count', by_status.get('approved', 0)))
            with col3:
                st.metric("Rejected", by_status.get('rejected', 0))
            with col4:
                st.metric("Flagged", stats.get('flagged_count', 0))

    except Exception as e:
        st.warning(f"Could not load session statistics: {str(e)}")

    # Check-ins Table
    st.markdown("---")
    st.markdown("#### Check-in Records")
    show_session_checkins(session_id)


if __name__ == "__main__":
    main()
