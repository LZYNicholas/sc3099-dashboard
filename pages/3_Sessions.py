"""SAIV Instructor Dashboard - Sessions Monitoring Page
"""

import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timezone
from urllib.parse import quote
from zoneinfo import ZoneInfo
from lib.auth_state import API_BASE_URL, get_auth_headers, require_auth
from lib.response_utils import bool_query, extract_items

try:
    from st_keyup import st_keyup
except Exception:
    st_keyup = None

# Page configuration
st.set_page_config(page_title="Sessions - SAIV Dashboard", layout="wide")

SG_TZ = ZoneInfo("Asia/Singapore")

def get_headers():
    return get_auth_headers()

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
        response = requests.get(
            f"{API_BASE_URL}/admin/sessions/{session_id}/qr",
            headers=get_headers(),
            timeout=10
        )
        if response.status_code == 200:
            return True, response.json()
        try:
            return False, response.json().get('detail', 'Failed to fetch QR code')
        except Exception:
            return False, 'Failed to fetch QR code'
    except Exception as error:
        return False, str(error)


def render_qr_block(qr_data, session_id):
    payload = qr_data.get('qr_payload', '')
    expires_at = qr_data.get('qr_expires_at')
    ttl = qr_data.get('qr_ttl_seconds', 0)

    st.info(f"QR expires at {format_datetime_local(expires_at)} (in {ttl}s)")
    st.code(payload, language='json')

    # Try local QR image generation first; fallback to a hosted QR renderer.
    try:
        import qrcode # type: ignore
        qr_img = qrcode.make(payload)
        st.image(qr_img, caption=f"Session QR - {session_id}", width=280)
    except Exception:
        qr_url = f"https://quickchart.io/qr?size=300&text={quote(payload)}"
        st.image(qr_url, caption=f"Session QR - {session_id}", width=280)


def update_session_status(session_id, status):
    try:
        response = requests.patch(
            f"{API_BASE_URL}/admin/sessions/{session_id}/status",
            json={"status": status},
            headers={**get_headers(), "Content-Type": "application/json"},
            timeout=10
        )
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

    st.title("Session Monitoring")
    st.markdown("Monitor active sessions and view check-in details.")

    # Fetch active courses for filter (only show active courses)
    try:
        courses_response = requests.get(
            f"{API_BASE_URL}/courses/",
            params={"is_active": bool_query(True), "limit": 100},
            headers=get_headers(),
            timeout=10
        )
        courses = extract_items(courses_response.json()) if courses_response.status_code == 200 else []
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
        url = f"{API_BASE_URL}/sessions/"
        params = {"limit": 100}
        if course_filter != 'All':
            params['course_id'] = course_filter

        response = requests.get(url, params=params, headers=get_headers(), timeout=10)

        if response.status_code == 200:
            sessions_data = response.json()
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

                        if window_open:
                            st.markdown("#### Session QR")
                            if current_role != 'instructor':
                                st.info("QR display is restricted to instructor role. Please log in as an instructor account.")
                            else:
                                state_key = f"session_qr_{session['id']}"
                                qr_payload = st.session_state.get(state_key)

                                # Auto-load QR for instructors so they can project it immediately.
                                ttl = int(qr_payload.get('qr_ttl_seconds', 0)) if isinstance(qr_payload, dict) else 0
                                if not qr_payload or ttl <= 0:
                                    ok, result = fetch_session_qr(session['id'])
                                    if ok:
                                        qr_payload = result
                                        st.session_state[state_key] = result
                                    else:
                                        st.error(result or "Could not generate QR")

                                btn_col1, btn_col2 = st.columns([1, 3])
                                with btn_col1:
                                    if st.button("Regenerate QR", key=f"qr_btn_{session['id']}", use_container_width=True):
                                        ok, result = fetch_session_qr(session['id'])
                                        if ok:
                                            qr_payload = result
                                            st.session_state[state_key] = result
                                        else:
                                            st.error(result or "Could not generate QR")
                                with btn_col2:
                                    st.caption("Show this QR on projector for students to scan during attendance taking.")

                                if qr_payload:
                                    render_qr_block(qr_payload, session['id'])

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
            st.error("Failed to load sessions.")

    except Exception as e:
        st.error(f"Connection error: {str(e)}")


def show_session_checkins(session_id):
    """Display check-ins for a session"""
    try:
        response = requests.get(
            f"{API_BASE_URL}/checkins/session/{session_id}",
            headers=get_headers(),
            timeout=10
        )

        if response.status_code == 200:
            checkins = response.json()
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
        stats_response = requests.get(
            f"{API_BASE_URL}/stats/sessions/{session_id}",
            headers=get_headers(),
            timeout=10
        )

        if stats_response.status_code == 200:
            stats = stats_response.json()

            st.markdown("---")
            st.markdown("#### Statistics")

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Check-ins", stats.get('total_checkins', 0))
            with col2:
                st.metric("On Time", stats.get('on_time_count', 0))
            with col3:
                st.metric("Late", stats.get('late_count', 0))
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
