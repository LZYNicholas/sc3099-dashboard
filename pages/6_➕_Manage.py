"""
SAIV Dashboard - Course & Session Management
Create and manage courses and sessions for attendance
"""

import streamlit as st
import requests
from datetime import datetime, timedelta

# Page configuration
st.set_page_config(page_title="Manage - SAIV", page_icon="➕", layout="wide")

# Check authentication
if not st.session_state.get('authenticated', False):
    st.warning("Please login from the main page to access this section.")
    st.stop()

# API Configuration
API_BASE_URL = "http://localhost:8000/api/v1"

def get_headers():
    """Get authorization headers"""
    token = st.session_state.get('token')
    if token:
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    return {"Content-Type": "application/json"}

def api_post(endpoint: str, data: dict):
    """Make POST request to API"""
    try:
        response = requests.post(
            f"{API_BASE_URL}{endpoint}",
            json=data,
            headers=get_headers(),
            timeout=10
        )
        return response
    except Exception as e:
        st.error(f"Connection error: {str(e)}")
        return None

def api_get(endpoint: str, params: dict = None):
    """Make GET request to API"""
    try:
        response = requests.get(
            f"{API_BASE_URL}{endpoint}",
            params=params,
            headers=get_headers(),
            timeout=10
        )
        return response
    except Exception as e:
        st.error(f"Connection error: {str(e)}")
        return None

def api_patch(endpoint: str, data: dict):
    """Make PATCH request to API"""
    try:
        response = requests.patch(
            f"{API_BASE_URL}{endpoint}",
            json=data,
            headers=get_headers(),
            timeout=10
        )
        return response
    except Exception as e:
        st.error(f"Connection error: {str(e)}")
        return None

st.title("➕ Course & Session Management")
st.markdown("Create and manage courses and sessions for student attendance.")

st.markdown("---")

# Tabs for different management functions
tab1, tab2, tab3, tab4 = st.tabs(["📚 Create Course", "🎯 Create Session", "👥 Manage Enrollments", "⚙️ Session Status"])

# ============================================================================
# TAB 1: CREATE COURSE
# ============================================================================
with tab1:
    st.subheader("📚 Create New Course")
    st.markdown("Create a new course for attendance tracking.")

    with st.form("create_course_form"):
        col1, col2 = st.columns(2)

        with col1:
            course_code = st.text_input(
                "Course Code *",
                placeholder="CS3099",
                help="Unique course code (e.g., CS3099)"
            )
            course_name = st.text_input(
                "Course Name *",
                placeholder="Capstone Project",
                help="Full name of the course"
            )
            semester = st.text_input(
                "Semester *",
                placeholder="AY2024-25 Sem 2",
                help="Academic semester"
            )

        with col2:
            venue_name = st.text_input(
                "Default Venue",
                placeholder="COM1-0212",
                help="Default venue for sessions"
            )
            venue_lat = st.number_input(
                "Venue Latitude",
                value=1.2950,
                format="%.6f",
                help="GPS latitude of venue"
            )
            venue_lon = st.number_input(
                "Venue Longitude",
                value=103.7737,
                format="%.6f",
                help="GPS longitude of venue"
            )

        col1, col2 = st.columns(2)
        with col1:
            geofence_radius = st.number_input(
                "Geofence Radius (meters)",
                value=100,
                min_value=10,
                max_value=1000,
                help="How far from venue students can check in"
            )
        with col2:
            risk_threshold = st.slider(
                "Risk Threshold",
                min_value=0.0,
                max_value=1.0,
                value=0.5,
                step=0.1,
                help="Check-ins above this score will be flagged"
            )

        submit_course = st.form_submit_button("Create Course", type="primary", use_container_width=True)

        if submit_course:
            if not course_code or not course_name or not semester:
                st.error("Please fill in all required fields (Course Code, Name, Semester)")
            else:
                course_data = {
                    "code": course_code,
                    "name": course_name,
                    "semester": semester,
                    "venue_name": venue_name or None,
                    "venue_latitude": venue_lat,
                    "venue_longitude": venue_lon,
                    "geofence_radius_meters": geofence_radius,
                    "risk_threshold": risk_threshold
                }

                with st.spinner("Creating course..."):
                    response = api_post("/courses/", course_data)

                    if response and response.status_code == 201:
                        result = response.json()
                        st.success(f"✅ Course created successfully!")
                        st.json(result)
                    elif response:
                        try:
                            error = response.json().get('detail', 'Unknown error')
                        except:
                            error = response.text
                        st.error(f"Failed to create course: {error}")
                    else:
                        st.error("Failed to connect to server")

    # List existing courses
    st.markdown("---")
    st.subheader("📋 Existing Courses")

    if st.button("🔄 Refresh Courses"):
        st.rerun()

    response = api_get("/courses/", {"limit": 50})
    if response and response.status_code == 200:
        courses = response.json().get('items', [])
        if courses:
            for course in courses:
                with st.expander(f"📚 {course.get('code')} - {course.get('name')}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**ID:** `{course.get('id')}`")
                        st.write(f"**Semester:** {course.get('semester')}")
                        st.write(f"**Venue:** {course.get('venue_name', 'Not set')}")
                    with col2:
                        st.write(f"**Geofence:** {course.get('geofence_radius_meters', 100)}m")
                        st.write(f"**Risk Threshold:** {course.get('risk_threshold', 0.5)}")
                        st.write(f"**Active:** {'Yes' if course.get('is_active') else 'No'}")
        else:
            st.info("No courses found. Create one above!")
    else:
        st.warning("Could not load courses")


# ============================================================================
# TAB 2: CREATE SESSION
# ============================================================================
with tab2:
    st.subheader("🎯 Create New Session")
    st.markdown("Create a new attendance session for a course.")

    # Get courses for dropdown
    response = api_get("/courses/", {"limit": 100})
    courses = []
    if response and response.status_code == 200:
        courses = response.json().get('items', [])

    if not courses:
        st.warning("No courses found. Please create a course first.")
    else:
        with st.form("create_session_form"):
            # Course selection
            course_options = {f"{c['code']} - {c['name']}": c for c in courses}
            selected_course_name = st.selectbox(
                "Select Course *",
                options=list(course_options.keys())
            )
            selected_course = course_options[selected_course_name]

            col1, col2 = st.columns(2)

            with col1:
                session_name = st.text_input(
                    "Session Name *",
                    placeholder="Lecture 1: Introduction",
                    help="Name/title of the session"
                )
                session_type = st.selectbox(
                    "Session Type *",
                    options=["lecture", "tutorial", "lab", "exam"],
                    help="Type of session"
                )

            with col2:
                # Date and time inputs
                session_date = st.date_input(
                    "Session Date *",
                    value=datetime.now().date()
                )
                start_time = st.time_input(
                    "Start Time *",
                    value=datetime.now().replace(hour=10, minute=0).time()
                )
                end_time = st.time_input(
                    "End Time *",
                    value=datetime.now().replace(hour=12, minute=0).time()
                )

            st.markdown("##### Check-in Window")
            col1, col2 = st.columns(2)
            with col1:
                checkin_opens_minutes = st.number_input(
                    "Opens (minutes before start)",
                    value=15,
                    min_value=0,
                    max_value=60,
                    help="How many minutes before session start check-in opens"
                )
            with col2:
                checkin_closes_minutes = st.number_input(
                    "Closes (minutes after start)",
                    value=30,
                    min_value=0,
                    max_value=120,
                    help="How many minutes after session start check-in closes"
                )

            st.markdown("##### Venue (Optional - uses course default if empty)")
            col1, col2, col3 = st.columns(3)
            with col1:
                session_venue = st.text_input(
                    "Venue Name",
                    value=selected_course.get('venue_name', ''),
                    help="Leave empty to use course default"
                )
            with col2:
                session_lat = st.number_input(
                    "Latitude",
                    value=float(selected_course.get('venue_latitude', 1.2950)),
                    format="%.6f"
                )
            with col3:
                session_lon = st.number_input(
                    "Longitude",
                    value=float(selected_course.get('venue_longitude', 103.7737)),
                    format="%.6f"
                )

            st.markdown("##### Security Settings")
            col1, col2 = st.columns(2)
            with col1:
                require_liveness = st.checkbox("Require Liveness Check", value=True)
                require_face_match = st.checkbox("Require Face Match", value=False)
            with col2:
                session_geofence = st.number_input(
                    "Geofence Radius (m)",
                    value=int(selected_course.get('geofence_radius_meters', 100)),
                    min_value=10,
                    max_value=1000
                )
                session_risk_threshold = st.slider(
                    "Risk Threshold",
                    min_value=0.0,
                    max_value=1.0,
                    value=float(selected_course.get('risk_threshold', 0.5)),
                    step=0.1
                )

            submit_session = st.form_submit_button("Create Session", type="primary", use_container_width=True)

            if submit_session:
                if not session_name:
                    st.error("Please enter a session name")
                else:
                    # Build datetime objects
                    scheduled_start = datetime.combine(session_date, start_time)
                    scheduled_end = datetime.combine(session_date, end_time)
                    checkin_opens = scheduled_start - timedelta(minutes=checkin_opens_minutes)
                    checkin_closes = scheduled_start + timedelta(minutes=checkin_closes_minutes)

                    session_data = {
                        "course_id": selected_course['id'],
                        "name": session_name,
                        "session_type": session_type,
                        "scheduled_start": scheduled_start.isoformat(),
                        "scheduled_end": scheduled_end.isoformat(),
                        "checkin_opens_at": checkin_opens.isoformat(),
                        "checkin_closes_at": checkin_closes.isoformat(),
                        "venue_name": session_venue or None,
                        "venue_latitude": session_lat,
                        "venue_longitude": session_lon,
                        "geofence_radius_meters": session_geofence,
                        "require_liveness_check": require_liveness,
                        "require_face_match": require_face_match,
                        "risk_threshold": session_risk_threshold
                    }

                    with st.spinner("Creating session..."):
                        response = api_post("/sessions/", session_data)

                        if response and response.status_code == 201:
                            result = response.json()
                            st.success(f"✅ Session created successfully!")
                            st.json(result)
                        elif response:
                            try:
                                error = response.json().get('detail', 'Unknown error')
                            except:
                                error = response.text
                            st.error(f"Failed to create session: {error}")
                        else:
                            st.error("Failed to connect to server")

    # List existing sessions
    st.markdown("---")
    st.subheader("📋 Existing Sessions")

    if st.button("🔄 Refresh Sessions"):
        st.rerun()

    response = api_get("/sessions/", {"limit": 50})
    if response and response.status_code == 200:
        sessions = response.json().get('items', [])
        if sessions:
            for session in sessions:
                status_emoji = {
                    'scheduled': '📅',
                    'active': '🟢',
                    'closed': '⚫',
                    'cancelled': '🔴'
                }.get(session.get('status'), '❓')

                with st.expander(f"{status_emoji} {session.get('course_code', 'N/A')} - {session.get('name')} ({session.get('status')})"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**ID:** `{session.get('id')}`")
                        st.write(f"**Type:** {session.get('session_type', 'N/A')}")
                        st.write(f"**Venue:** {session.get('venue_name', 'Not set')}")
                    with col2:
                        st.write(f"**Start:** {session.get('scheduled_start', 'N/A')[:16] if session.get('scheduled_start') else 'N/A'}")
                        st.write(f"**End:** {session.get('scheduled_end', 'N/A')[:16] if session.get('scheduled_end') else 'N/A'}")
                        st.write(f"**Check-in:** {session.get('checkin_opens_at', 'N/A')[:16] if session.get('checkin_opens_at') else 'N/A'} - {session.get('checkin_closes_at', 'N/A')[:16] if session.get('checkin_closes_at') else 'N/A'}")
        else:
            st.info("No sessions found. Create one above!")
    else:
        st.warning("Could not load sessions")


# ============================================================================
# TAB 3: MANAGE ENROLLMENTS
# ============================================================================
with tab3:
    st.subheader("👥 Manage Student Enrollments")
    st.markdown("Enroll students in courses.")

    # Get courses for dropdown
    response = api_get("/courses/", {"limit": 100})
    courses = []
    if response and response.status_code == 200:
        courses = response.json().get('items', [])

    if not courses:
        st.warning("No courses found. Please create a course first.")
    else:
        course_options = {f"{c['code']} - {c['name']}": c for c in courses}
        selected_course_name = st.selectbox(
            "Select Course",
            options=list(course_options.keys()),
            key="enroll_course"
        )
        selected_course = course_options[selected_course_name]

        st.markdown("---")

        # Single enrollment
        st.markdown("##### Enroll Single Student")
        with st.form("enroll_single_form"):
            student_id = st.text_input(
                "Student ID (UUID)",
                placeholder="Enter student's user ID",
                help="The UUID of the student user"
            )

            submit_enroll = st.form_submit_button("Enroll Student", use_container_width=True)

            if submit_enroll:
                if not student_id:
                    st.error("Please enter a student ID")
                else:
                    enroll_data = {
                        "student_id": student_id,
                        "course_id": selected_course['id']
                    }

                    with st.spinner("Enrolling student..."):
                        response = api_post("/admin/enrollments/", enroll_data)

                        if response and response.status_code == 201:
                            st.success("✅ Student enrolled successfully!")
                        elif response:
                            try:
                                error = response.json().get('detail', 'Unknown error')
                            except:
                                error = response.text
                            st.error(f"Failed to enroll: {error}")
                        else:
                            st.error("Failed to connect to server")

        st.markdown("---")

        # Bulk enrollment
        st.markdown("##### Bulk Enroll by Email")
        with st.form("enroll_bulk_form"):
            student_emails = st.text_area(
                "Student Emails (one per line)",
                placeholder="student1@example.com\nstudent2@example.com",
                help="Enter student emails, one per line"
            )
            create_accounts = st.checkbox(
                "Create accounts for unknown emails",
                value=False,
                help="If checked, will create accounts for emails not found in the system"
            )

            submit_bulk = st.form_submit_button("Bulk Enroll", use_container_width=True)

            if submit_bulk:
                emails = [e.strip() for e in student_emails.split('\n') if e.strip()]
                if not emails:
                    st.error("Please enter at least one email")
                else:
                    bulk_data = {
                        "course_id": selected_course['id'],
                        "student_emails": emails,
                        "create_accounts": create_accounts
                    }

                    with st.spinner(f"Enrolling {len(emails)} students..."):
                        response = api_post("/enrollments/bulk", bulk_data)

                        if response and response.status_code == 200:
                            result = response.json()
                            st.success(f"✅ Enrolled: {result.get('enrolled', 0)}, Already enrolled: {result.get('already_enrolled', 0)}, Not found: {result.get('not_found', 0)}")
                            if result.get('details'):
                                st.json(result['details'])
                        elif response:
                            try:
                                error = response.json().get('detail', 'Unknown error')
                            except:
                                error = response.text
                            st.error(f"Failed: {error}")
                        else:
                            st.error("Failed to connect to server")

        # Show current enrollments
        st.markdown("---")
        st.markdown("##### Current Enrollments")

        response = api_get(f"/enrollments/course/{selected_course['id']}")
        if response and response.status_code == 200:
            data = response.json()
            students = data.get('students', [])
            st.write(f"**Total enrolled:** {data.get('total_enrolled', len(students))}")

            if students:
                import pandas as pd
                df = pd.DataFrame(students)
                display_cols = ['student_name', 'student_email', 'enrolled_at', 'face_enrolled']
                available_cols = [c for c in display_cols if c in df.columns]
                if available_cols:
                    st.dataframe(df[available_cols], use_container_width=True)
            else:
                st.info("No students enrolled yet")
        else:
            st.info("Could not load enrollments")


# ============================================================================
# TAB 4: SESSION STATUS
# ============================================================================
with tab4:
    st.subheader("⚙️ Change Session Status")
    st.markdown("Activate, close, or cancel sessions.")

    # Get sessions
    response = api_get("/sessions/", {"limit": 100})
    sessions = []
    if response and response.status_code == 200:
        sessions = response.json().get('items', [])

    if not sessions:
        st.warning("No sessions found. Please create a session first.")
    else:
        session_options = {
            f"{s.get('course_code', 'N/A')} - {s.get('name')} ({s.get('status')})": s
            for s in sessions
        }

        selected_session_name = st.selectbox(
            "Select Session",
            options=list(session_options.keys())
        )
        selected_session = session_options[selected_session_name]

        st.markdown("---")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Current Status:**")
            status = selected_session.get('status', 'unknown')
            status_colors = {
                'scheduled': '🔵 Scheduled',
                'active': '🟢 Active',
                'closed': '⚫ Closed',
                'cancelled': '🔴 Cancelled'
            }
            st.write(status_colors.get(status, f'❓ {status}'))

        with col2:
            st.markdown("**Session Details:**")
            st.write(f"ID: `{selected_session.get('id')}`")

        st.markdown("---")
        st.markdown("##### Change Status")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            if st.button("🟢 Activate", use_container_width=True, type="primary"):
                response = api_patch(
                    f"/admin/sessions/{selected_session['id']}/status",
                    {"status": "active"}
                )
                if response and response.status_code == 200:
                    st.success("✅ Session activated!")
                    st.rerun()
                else:
                    st.error("Failed to activate session")

        with col2:
            if st.button("⚫ Close", use_container_width=True):
                response = api_patch(
                    f"/admin/sessions/{selected_session['id']}/status",
                    {"status": "closed"}
                )
                if response and response.status_code == 200:
                    st.success("✅ Session closed!")
                    st.rerun()
                else:
                    st.error("Failed to close session")

        with col3:
            if st.button("🔴 Cancel", use_container_width=True):
                response = api_patch(
                    f"/admin/sessions/{selected_session['id']}/status",
                    {"status": "cancelled"}
                )
                if response and response.status_code == 200:
                    st.success("✅ Session cancelled!")
                    st.rerun()
                else:
                    st.error("Failed to cancel session")

        with col4:
            if st.button("📅 Schedule", use_container_width=True):
                response = api_patch(
                    f"/admin/sessions/{selected_session['id']}/status",
                    {"status": "scheduled"}
                )
                if response and response.status_code == 200:
                    st.success("✅ Session set to scheduled!")
                    st.rerun()
                else:
                    st.error("Failed to update session")

        st.markdown("---")
        st.info("""
        **Status Guide:**
        - **Scheduled**: Session is planned but check-in not yet open
        - **Active**: Check-in is open, students can check in
        - **Closed**: Check-in has ended, attendance finalized
        - **Cancelled**: Session was cancelled, no attendance recorded
        """)
