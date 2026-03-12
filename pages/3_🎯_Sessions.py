"""
SAIV Instructor Dashboard - Sessions Monitoring Page
"""

import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import time

# Page configuration
st.set_page_config(page_title="Sessions - SAIV Dashboard", page_icon="🎯", layout="wide")

API_BASE_URL = "http://localhost:8000/api/v1"

def check_auth():
    """Check if user is authenticated"""
    if not st.session_state.get('authenticated', False):
        st.warning("Please login from the main page.")
        st.stop()

def get_headers():
    """Get authorization headers"""
    return {"Authorization": f"Bearer {st.session_state.get('access_token', '')}"}

def get_status_color(status):
    """Get color for status badge"""
    colors = {
        'scheduled': '🔵',
        'active': '🟢',
        'completed': '⚫',
        'cancelled': '🔴'
    }
    return colors.get(status, '⚪')

def main():
    check_auth()

    st.title("🎯 Session Monitoring")
    st.markdown("Monitor active sessions and view check-in details.")

    # Fetch active courses for filter (only show active courses)
    try:
        courses_response = requests.get(
            f"{API_BASE_URL}/courses/",
            params={"is_active": True, "limit": 100},
            headers=get_headers(),
            timeout=10
        )
        courses_data = courses_response.json() if courses_response.status_code == 200 else {}
        courses = courses_data.get('items', []) if isinstance(courses_data, dict) else courses_data
    except:
        courses = []

    # Track active course IDs for later use
    active_course_ids = {c['id'] for c in courses}

    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        course_filter = st.selectbox(
            "Filter by Course",
            options=['All'] + [c['id'] for c in courses],
            format_func=lambda x: 'All Courses' if x == 'All' else next((f"{c['code']} - {c['name']}" for c in courses if c['id'] == x), x)
        )
    with col2:
        # Fixed status options to match actual backend status values
        status_filter = st.selectbox(
            "Filter by Status",
            options=['All', 'active', 'scheduled', 'closed', 'cancelled']
        )
    with col3:
        col_btn, col_auto = st.columns(2)
        with col_btn:
            if st.button("🔄 Refresh", use_container_width=True):
                st.rerun()
        with col_auto:
            auto_refresh = st.toggle("Auto-refresh", value=False, help="Refresh every 30 seconds")

    if auto_refresh:
        time.sleep(30)
        st.rerun()

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

            # Active Sessions Section
            active_sessions = [s for s in sessions if s.get('status') == 'active']
            if active_sessions:
                st.subheader(f"🟢 Active Sessions ({len(active_sessions)})")
                for session in active_sessions:
                    course_deleted = session.get('course_id') not in active_course_ids
                    title_suffix = " ⚠️ [COURSE DELETED]" if course_deleted else ""

                    with st.expander(f"**{session.get('name', 'Session')}** - {session.get('course_name', 'Course')}{title_suffix}", expanded=True):
                        if course_deleted:
                            st.error("⚠️ This session's course has been deleted. Check-ins may not work properly.")

                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.write(f"**Type:** {session.get('session_type', 'N/A')}")
                            st.write(f"**Start:** {session.get('scheduled_start', 'N/A')[:16] if session.get('scheduled_start') else 'N/A'}")
                        with col2:
                            st.write(f"**End:** {session.get('scheduled_end', 'N/A')[:16] if session.get('scheduled_end') else 'N/A'}")
                            st.write(f"**Location:** {session.get('venue_name', session.get('location', 'N/A'))}")
                        with col3:
                            # Quick stats for this session
                            st.metric("Check-ins", session.get('checkin_count', 0))

                        # Show check-ins for active session
                        if st.button(f"View Check-ins", key=f"view_{session['id']}"):
                            st.session_state[f"show_checkins_{session['id']}"] = True

                        if st.session_state.get(f"show_checkins_{session['id']}", False):
                            show_session_checkins(session['id'])

                st.markdown("---")

            # All Sessions Table
            st.subheader("📋 All Sessions")

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
                    'Scheduled Start': s.get('scheduled_start', 'N/A')[:16] if s.get('scheduled_start') else 'N/A',
                    'Check-ins': s.get('checkin_count', 0),
                    'ID': s.get('id', '')
                })

            df = pd.DataFrame(display_data)
            st.dataframe(df.drop(columns=['ID']), use_container_width=True, hide_index=True)

            # Session Details
            st.markdown("---")
            st.subheader("🔍 Session Details")

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


def show_session_checkins(session_id, show_export=True):
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
                checkins = checkins.get('items', [])
            if checkins:
                st.markdown("#### Check-ins")
                for ci in checkins:
                    risk_color = "🟢" if ci.get('risk_score', 0) < 0.3 else "🟡" if ci.get('risk_score', 0) < 0.7 else "🔴"
                    status_icon = "✅" if ci.get('status') in ('verified', 'approved') else "⏳" if ci.get('status') == 'pending' else "❌"

                    col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
                    with col1:
                        st.write(f"**{ci.get('student_name', 'Unknown')}**")
                    with col2:
                        timestamp = ci.get('checked_in_at', ci.get('timestamp', 'N/A'))
                        st.write(f"{timestamp[:16] if timestamp and timestamp != 'N/A' else 'N/A'}")
                    with col3:
                        st.write(f"{risk_color} Risk: {ci.get('risk_score', 0):.2f}")
                    with col4:
                        st.write(f"{status_icon}")

                # CSV Export
                if show_export:
                    st.markdown("---")
                    export_data = []
                    for ci in checkins:
                        export_data.append({
                            'Check-in ID': ci.get('id', ''),
                            'Student ID': ci.get('student_id', ''),
                            'Session ID': session_id,
                            'Timestamp': ci.get('checked_in_at', ci.get('timestamp', '')),
                            'Verification Status': ci.get('status', ''),
                            'Risk Score': ci.get('risk_score', ''),
                            'Liveness Score': ci.get('liveness_score', ci.get('liveness_passed', '')),
                            'Face Match Score': ci.get('face_match_score', ''),
                            'Latitude': ci.get('latitude', ''),
                            'Longitude': ci.get('longitude', '')
                        })
                    df_export = pd.DataFrame(export_data)
                    csv = df_export.to_csv(index=False)
                    st.download_button(
                        "📥 Export Check-ins CSV",
                        csv,
                        f"session_{session_id}_checkins.csv",
                        "text/csv",
                        use_container_width=True,
                        key=f"export_csv_{session_id}"
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
        st.write(f"**Scheduled Start:** {session.get('scheduled_start', 'N/A')}")
        st.write(f"**Scheduled End:** {session.get('scheduled_end', 'N/A')}")
        if session.get('actual_start'):
            st.write(f"**Actual Start:** {session.get('actual_start')}")
        if session.get('actual_end'):
            st.write(f"**Actual End:** {session.get('actual_end')}")

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
