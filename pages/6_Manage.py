"""SAIV Dashboard - Course & Session Management
Create and manage courses and sessions for attendance
"""

import streamlit as st
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from lib.auth_state import API_BASE_URL, get_auth_headers, require_auth
from lib.response_utils import bool_query, extract_items

# Page configuration
st.set_page_config(page_title="Manage - SAIV", layout="wide")

require_auth()

# API Configuration
SG_TZ = ZoneInfo("Asia/Singapore")
_API_GET_CACHE: dict[tuple[str, tuple[tuple[str, str], ...]], requests.Response | None] = {}


def to_api_datetime(value: datetime) -> str:
    # Always send timezone-aware Singapore timestamps to backend.
    if value.tzinfo is None:
        value = value.replace(tzinfo=SG_TZ)
    else:
        value = value.astimezone(SG_TZ)
    return value.isoformat()

def get_headers():
    headers = get_auth_headers()
    headers["Content-Type"] = "application/json"
    return headers

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
    cache_key: tuple[str, tuple[tuple[str, str], ...]] | None = None
    try:
        query_params = None
        if params is not None:
            query_params = {
                k: bool_query(v) if isinstance(v, bool) else v
                for k, v in params.items()
            }
        cache_key = (
            endpoint,
            tuple(sorted((str(k), str(v)) for k, v in (query_params or {}).items()))
        )
        if cache_key in _API_GET_CACHE:
            return _API_GET_CACHE[cache_key]

        response = requests.get(
            f"{API_BASE_URL}{endpoint}",
            params=query_params,
            headers=get_headers(),
            timeout=10
        )
        _API_GET_CACHE[cache_key] = response
        return response
    except Exception as e:
        st.error(f"Connection error: {str(e)}")
        if cache_key is not None:
            _API_GET_CACHE[cache_key] = None
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

def api_put(endpoint: str, data: dict):
    """Make PUT request to API"""
    try:
        response = requests.put(
            f"{API_BASE_URL}{endpoint}",
            json=data,
            headers=get_headers(),
            timeout=10
        )
        return response
    except Exception as e:
        st.error(f"Connection error: {str(e)}")
        return None


def response_items(response: requests.Response):
    try:
        return extract_items(response.json())
    except Exception:
        return []


def response_error(response: requests.Response | None, fallback: str = "Unknown error") -> str:
    if response is None:
        return "Connection error"

    try:
        payload = response.json()
        if isinstance(payload, dict):
            for key in ("detail", "message", "error"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value

            detail = payload.get("detail")
            if isinstance(detail, list) and detail:
                first = detail[0]
                if isinstance(first, dict):
                    msg = first.get("msg")
                    if isinstance(msg, str) and msg.strip():
                        return msg
    except Exception:
        pass

    text = (response.text or "").strip()
    if text:
        return text
    return fallback

st.title("Course & Session Management")
st.markdown("Create and manage courses and sessions for student attendance.")

st.markdown("---")

# Tabs for different management functions
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Create Course", "Create Session", "Manage Enrollments", "Session Status", "Recovery", "Manage Devices"])

# ============================================================================
# TAB 1: CREATE COURSE
# ============================================================================
with tab1:
    st.subheader("Create New Course")
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
                normalized_code = course_code.strip().upper()
                normalized_semester = semester.strip()

                course_data = {
                    "code": normalized_code,
                    "name": course_name.strip(),
                    "semester": normalized_semester,
                    "venue_name": venue_name or None,
                    "venue_latitude": venue_lat,
                    "venue_longitude": venue_lon,
                    "geofence_radius_meters": geofence_radius,
                    "risk_threshold": risk_threshold
                }

                with st.spinner("Creating course..."):
                    response = api_post("/courses/", course_data)

                    if response is not None and response.status_code == 201:
                        result = response.json()
                        st.success("Course created successfully!")
                        st.json(result)
                    elif response is not None:
                        error = response_error(response)
                        st.error(f"Failed to create course: {error}")
                    else:
                        st.error("Failed to connect to server")

    # List existing courses
    st.markdown("---")
    st.subheader("Existing Courses")

    if st.button("Refresh Courses"):
        st.rerun()

    response = api_get("/courses/", {"limit": 50, "is_active": True})
    if response is not None and response.status_code == 200:
        courses = response_items(response)
        sessions_by_course: dict[str, list[dict]] = {}
        sessions_response = api_get("/sessions/", {"limit": 500})
        if sessions_response is not None and sessions_response.status_code == 200:
            for session in response_items(sessions_response):
                course_id = session.get('course_id')
                if isinstance(course_id, str):
                    sessions_by_course.setdefault(course_id, []).append(session)
        if courses:
            for course in courses:
                with st.expander(f"{course.get('code')} - {course.get('name')}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**ID:** `{course.get('id')}`")
                        st.write(f"**Semester:** {course.get('semester')}")
                        st.write(f"**Venue:** {course.get('venue_name', 'Not set')}")
                    with col2:
                        st.write(f"**Geofence:** {course.get('geofence_radius_meters', 100)}m")
                        st.write(f"**Risk Threshold:** {course.get('risk_threshold', 0.5)}")
                        st.write(f"**Active:** {'Yes' if course.get('is_active') else 'No'}")
                    
                    # Delete button - only for active courses
                    if course.get('is_active'):
                        # Check if course has any sessions (from preloaded sessions map)
                        course_sessions = sessions_by_course.get(course.get('id'), [])

                        # Show warning if course has sessions
                        if course_sessions:
                            active_sessions = [s for s in course_sessions if s.get('status') in ['scheduled', 'active']]
                            if active_sessions:
                                st.warning(f"This course has {len(active_sessions)} scheduled/active session(s). Deleting will prevent new check-ins.")
                            else:
                                st.caption(f"This course has {len(course_sessions)} session(s).")

                        if st.button("Delete Course", key=f"delete_course_{course.get('id')}"):
                            try:
                                headers = {}
                                token = st.session_state.get('access_token')
                                if token:
                                    headers["Authorization"] = f"Bearer {token}"

                                response = requests.delete(
                                    f"{API_BASE_URL}/courses/{course.get('id')}",
                                    headers=headers,
                                    timeout=10
                                )

                                if response.status_code == 204:
                                    st.success("Course deleted (deactivated)!")
                                    st.rerun()
                                else:
                                    error = response_error(response)
                                    st.error(f"Failed to delete: {error}")
                            except Exception as e:
                                st.error(f"Connection error: {str(e)}")
        else:
            st.info("No courses found. Create one above!")
    else:
        st.warning("Could not load courses")


# ============================================================================
# TAB 2: CREATE SESSION
# ============================================================================
with tab2:
    st.subheader("Create New Session")
    st.markdown("Create a new attendance session for a course.")

    # Get only ACTIVE courses for dropdown - cannot create sessions for deleted courses
    response = api_get("/courses/", {"limit": 100, "is_active": True})
    courses = []
    if response is not None and response.status_code == 200:
        courses = response_items(response)

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
                # Date and time inputs - default to 10 minutes from now
                default_start = datetime.now(SG_TZ) + timedelta(minutes=10)
                # Round up to next 5-minute interval
                minutes = default_start.minute
                rounded_minutes = ((minutes // 5) + 1) * 5
                if rounded_minutes >= 60:
                    default_start = default_start.replace(hour=default_start.hour + 1, minute=0, second=0, microsecond=0)
                else:
                    default_start = default_start.replace(minute=rounded_minutes, second=0, microsecond=0)
                default_end = default_start + timedelta(hours=2)
                
                session_date = st.date_input(
                    "Session Date *",
                    value=default_start.date()
                )
                start_time = st.time_input(
                    "Start Time *",
                    value=default_start.replace(tzinfo=None).time()
                )
                end_time = st.time_input(
                    "End Time *",
                    value=default_end.replace(tzinfo=None).time()
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
                default_lat = selected_course.get('venue_latitude')
                if default_lat is None:
                    default_lat = 1.2950
                default_lon = selected_course.get('venue_longitude')
                if default_lon is None:
                    default_lon = 103.7737
                default_geofence = selected_course.get('geofence_radius_meters')
                if default_geofence is None:
                    default_geofence = 100
                default_risk_threshold = selected_course.get('risk_threshold')
                if default_risk_threshold is None:
                    default_risk_threshold = 0.5

                session_lat = st.number_input(
                    "Latitude",
                    value=float(default_lat),
                    format="%.6f"
                )
            with col3:
                session_lon = st.number_input(
                    "Longitude",
                    value=float(default_lon),
                    format="%.6f"
                )

            st.markdown("##### Security Settings")
            col1, col2, col3 = st.columns(3)
            with col1:
                require_liveness = st.checkbox("Require Liveness Check", value=True)
                require_face_match = st.checkbox("Require Face Match", value=False)
            with col2:
                session_geofence = st.number_input(
                    "Geofence Radius (m)",
                    value=int(default_geofence),
                    min_value=10,
                    max_value=1000
                )
            with col3:
                qr_code_enabled = st.checkbox(
                    "Require QR Code",
                    value=False,
                    help="Students must scan the instructor QR before submitting attendance"
                )
                session_risk_threshold = st.slider(
                    "Risk Threshold",
                    min_value=0.0,
                    max_value=1.0,
                    value=float(default_risk_threshold),
                    step=0.1
                )

            submit_session = st.form_submit_button("Create Session", type="primary", use_container_width=True)

            if submit_session:
                # Build datetime objects first for validation
                scheduled_start = datetime.combine(session_date, start_time).replace(tzinfo=SG_TZ)
                scheduled_end = datetime.combine(session_date, end_time).replace(tzinfo=SG_TZ)
                # Allow overnight sessions: if end clock time is earlier than start,
                # treat end as next day.
                if scheduled_end <= scheduled_start:
                    scheduled_end = scheduled_end + timedelta(days=1)
                checkin_opens = scheduled_start - timedelta(minutes=checkin_opens_minutes)
                checkin_closes = scheduled_start + timedelta(minutes=checkin_closes_minutes)

                # Validation checks
                validation_errors = []

                if not session_name:
                    validation_errors.append("Please enter a session name")

                if checkin_closes <= checkin_opens:
                    validation_errors.append("Check-in close time must be after open time")

                # Warn if session is in the past (but allow it - instructor might be backfilling)
                if scheduled_start < datetime.now(SG_TZ):
                    st.warning("Note: This session is scheduled in the past.")

                if validation_errors:
                    for error in validation_errors:
                        st.error(error)
                else:
                    session_data = {
                        "course_id": selected_course['id'],
                        "name": session_name,
                        "session_type": session_type,
                        "scheduled_start": to_api_datetime(scheduled_start),
                        "scheduled_end": to_api_datetime(scheduled_end),
                        "checkin_opens_at": to_api_datetime(checkin_opens),
                        "checkin_closes_at": to_api_datetime(checkin_closes),
                        "venue_name": session_venue or None,
                        "venue_latitude": session_lat,
                        "venue_longitude": session_lon,
                        "geofence_radius_meters": session_geofence,
                        "require_liveness_check": require_liveness,
                        "require_face_match": require_face_match,
                        "risk_threshold": session_risk_threshold,
                        "qr_code_enabled": qr_code_enabled
                    }

                    with st.spinner("Creating session..."):
                        response = api_post("/sessions/", session_data)

                        if response is not None and response.status_code == 201:
                            result = response.json()
                            st.success("Session created successfully!")
                            st.json(result)
                        elif response is not None:
                            error = response_error(response)
                            st.error(f"Failed to create session: {error}")
                        else:
                            st.error("Failed to connect to server")

    # List existing sessions
    st.markdown("---")
    st.subheader("Existing Sessions")

    if st.button("Refresh Sessions"):
        st.rerun()

    # Get all sessions and active courses to check status
    response = api_get("/sessions/", {"limit": 50})
    active_courses_resp = api_get("/courses/", {"limit": 100, "is_active": True})
    active_course_ids_list = set()
    if active_courses_resp is not None and active_courses_resp.status_code == 200:
        active_course_ids_list = {c['id'] for c in response_items(active_courses_resp)}

    if response is not None and response.status_code == 200:
        sessions = response_items(response)
        if sessions:
            for session in sessions:
                status_emoji = {
                    'scheduled': 'Scheduled',
                    'active': 'Active',
                    'closed': 'Closed',
                    'cancelled': 'Cancelled'
                }.get(session.get('status'), 'Unknown')

                # Check if course is deleted
                course_deleted = session.get('course_id') not in active_course_ids_list
                deleted_indicator = " [COURSE DELETED]" if course_deleted else ""

                with st.expander(f"{status_emoji} {session.get('course_code', 'N/A')} - {session.get('name')} ({session.get('status')}){deleted_indicator}"):
                    if course_deleted:
                        st.error("The course for this session has been deleted. This session cannot be activated.")

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
    st.subheader("Manage Student Enrollments")
    st.markdown("Enroll students in courses.")

    # Get only ACTIVE courses for dropdown - cannot enroll in deleted courses
    response = api_get("/courses/", {"limit": 100, "is_active": True})
    courses = []
    if response is not None and response.status_code == 200:
        courses = response_items(response)

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

                        if response is not None and response.status_code == 201:
                            st.success("Student enrolled successfully!")
                        elif response is not None:
                            error = response_error(response)
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

                        if response is not None and response.status_code == 200:
                            result = response.json()
                            st.success(f"Enrolled: {result.get('enrolled', 0)}, Already enrolled: {result.get('already_enrolled', 0)}, Not found: {result.get('not_found', 0)}")
                            if result.get('details'):
                                st.json(result['details'])
                        elif response is not None:
                            error = response_error(response)
                            st.error(f"Failed: {error}")
                        else:
                            st.error("Failed to connect to server")

        # Show current enrollments
        st.markdown("---")
        st.markdown("##### Current Enrollments")

        response = api_get(f"/enrollments/course/{selected_course['id']}")
        if response is not None and response.status_code == 200:
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
    st.subheader("Change Session Status")
    st.markdown("Activate, close, or cancel sessions.")

    # Get sessions
    response = api_get("/sessions/", {"limit": 100})
    sessions = []
    if response is not None and response.status_code == 200:
        sessions = response_items(response)

    # Also get active courses to check if session's course is still active
    active_courses_response = api_get("/courses/", {"limit": 100, "is_active": True})
    active_course_ids = set()
    if active_courses_response is not None and active_courses_response.status_code == 200:
        active_courses = response_items(active_courses_response)
        active_course_ids = {c['id'] for c in active_courses}

    if not sessions:
        st.warning("No sessions found. Please create a session first.")
    else:
        session_sort_order = {
            'scheduled': 0,
            'active': 1,
            'closed': 2,
            'cancelled': 3
        }
        sessions = sorted(
            sessions,
            key=lambda session: (
                session_sort_order.get(session.get('status', ''), 99),
                session.get('scheduled_start', '')
            )
        )
        session_options = {
            f"{s.get('course_code', 'N/A')} - {s.get('name')} ({s.get('status')})": s
            for s in sessions
        }

        session_option_keys = list(session_options.keys())
        default_session_index = 0
        for index, key in enumerate(session_option_keys):
            if session_options[key].get('status') == 'scheduled':
                default_session_index = index
                break

        selected_session_name = st.selectbox(
            "Select Session",
            options=session_option_keys,
            index=default_session_index,
            help="Activate is only available for sessions that are currently scheduled and whose course is still active."
        )
        selected_session = session_options[selected_session_name]

        st.markdown("---")

        # Check if the course is still active
        course_id = selected_session.get('course_id')
        course_is_active = course_id in active_course_ids

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Current Status:**")
            status = selected_session.get('status', 'unknown')
            status_colors = {
                'scheduled': 'Scheduled',
                'active': 'Active',
                'closed': 'Closed',
                'cancelled': 'Cancelled'
            }
            st.write(status_colors.get(status, f'Unknown: {status}'))

        with col2:
            st.markdown("**Session Details:**")
            st.write(f"ID: `{selected_session.get('id')}`")
            if not course_is_active:
                st.error("Course has been deleted!")

        st.markdown("---")

        # Show warning if course is deleted
        if not course_is_active:
            st.warning("This session belongs to a deleted course. You cannot activate it. Restore the course first or cancel/close this session.")

        st.markdown("##### Change Status")

        # Define valid state transitions
        # scheduled -> active, cancelled
        # active -> closed, cancelled
        # closed -> (none - finalized)
        # cancelled -> (none - terminal state)

        valid_transitions = {
            'scheduled': ['active', 'cancelled'],
            'active': ['closed', 'cancelled'],
            'closed': [], # Finalized - no transitions allowed
            'cancelled': [] # Terminal state - no transitions allowed
        }

        allowed_next_states = valid_transitions.get(status, [])

        # Additional restriction: cannot activate if course is deleted
        if not course_is_active and 'active' in allowed_next_states:
            allowed_next_states = [s for s in allowed_next_states if s != 'active']

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            can_activate = 'active' in allowed_next_states
            if st.button("Activate", use_container_width=True, type="primary", disabled=not can_activate):
                if can_activate:
                    response = api_patch(
                        f"/admin/sessions/{selected_session['id']}/status",
                        {"status": "active"}
                    )
                    if response is not None and response.status_code == 200:
                        st.success("Session activated!")
                        st.rerun()
                    else:
                        error_msg = response_error(response, "Failed to activate session")
                        st.error(error_msg)

        with col2:
            can_close = 'closed' in allowed_next_states
            if st.button("Close", use_container_width=True, disabled=not can_close):
                if can_close:
                    response = api_patch(
                        f"/admin/sessions/{selected_session['id']}/status",
                        {"status": "closed"}
                    )
                    if response is not None and response.status_code == 200:
                        st.success("Session closed!")
                        st.rerun()
                    else:
                        error_msg = response_error(response, "Failed to close session")
                        st.error(error_msg)

        with col3:
            can_cancel = 'cancelled' in allowed_next_states
            if st.button("Cancel", use_container_width=True, disabled=not can_cancel):
                if can_cancel:
                    response = api_patch(
                        f"/admin/sessions/{selected_session['id']}/status",
                        {"status": "cancelled"}
                    )
                    if response is not None and response.status_code == 200:
                        st.success("Session cancelled!")
                        st.rerun()
                    else:
                        error_msg = response_error(response, "Failed to cancel session")
                        st.error(error_msg)

        with col4:
            # Schedule button is not typically allowed - sessions don't go backward
            # Only show if we want to allow re-scheduling (uncomment if needed)
            st.button("Schedule", use_container_width=True, disabled=True,
                     help="Sessions cannot be moved back to scheduled status")

        # Show explanation of current state
        st.markdown("---")
        if status == 'closed':
            st.info("This session is **closed**. Attendance has been finalized and cannot be changed.")
        elif status == 'cancelled':
            st.info("This session is **cancelled**. No further changes are allowed.")
        elif status == 'active':
            st.info("This session is **active**. Students can currently check in. Close it when the check-in period ends.")
        elif status == 'scheduled':
            st.info("This session is **scheduled**. Activate it to open check-in for students.")

        st.markdown("---")
        st.markdown("""
        **Status Transition Rules:**
        - **Scheduled** -> Active (open check-in) or Cancelled
        - **Active** -> Closed (finalize attendance) or Cancelled
        - **Closed** -> No changes (attendance is finalized)
        - **Cancelled** -> No changes (terminal state)
        """)

        # Delete button - only for scheduled or cancelled sessions (no check-ins recorded)
        if status in ['scheduled', 'cancelled']:
            st.warning("""
            **Warning:** Deleting a session is permanent. 
            Only sessions with status `scheduled` can be deleted. Active or closed sessions must be `cancelled` instead.
            """)
            if st.button("Delete Session", use_container_width=True, type="secondary"):
                try:
                    # DELETE request without Content-Type header
                    headers = {}
                    token = st.session_state.get('access_token')
                    if token:
                        headers["Authorization"] = f"Bearer {token}"

                    response = requests.delete(
                        f"{API_BASE_URL}/sessions/{selected_session['id']}",
                        headers=headers,
                        timeout=10
                    )

                    if response.status_code == 204:
                        st.success("Session deleted!")
                        st.rerun()
                    else:
                        error = response_error(response)
                        st.error(f"Failed to delete: {error}")
                except Exception as e:
                    st.error(f"Connection error: {str(e)}")
        elif status in ['active', 'closed']:
            st.markdown("---")
            st.markdown("##### Danger Zone")
            st.warning("This session cannot be deleted because it has/had active check-ins. Close or cancel it instead.")


# ============================================================================
# TAB 5: RECOVERY
# ============================================================================
with tab5:
    st.subheader("Recover Deleted Courses")
    st.markdown("Reactivate courses that were previously deleted (soft-deleted).")

    if st.button("Refresh Deleted Courses"):
        st.rerun()

    # Get inactive courses
    response = api_get("/courses/", {"limit": 100, "is_active": False})
    if response is not None and response.status_code == 200:
        deleted_courses = response_items(response)
        if deleted_courses:
            st.write(f"Found **{len(deleted_courses)}** deleted courses:")
            
            for course in deleted_courses:
                with st.expander(f"{course.get('code')} - {course.get('name')}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**ID:** `{course.get('id')}`")
                        st.write(f"**Semester:** {course.get('semester')}")
                    with col2:
                        st.write(f"**Venue:** {course.get('venue_name', 'Not set')}")
                        st.write(f"**Active:** {'Yes' if course.get('is_active') else 'No'}")
                    
                    # Restore button
                    if st.button("Restore Course", key=f"restore_course_{course.get('id')}"):
                        restore_response = api_put(
                            f"/courses/{course.get('id')}",
                            {"is_active": True}
                        )
                        if restore_response is not None and restore_response.status_code == 200:
                            st.success("Course restored!")
                            st.rerun()
                        else:
                            error = response_error(restore_response)
                            st.error(f"Failed to restore: {error}")
        else:
            st.info("No deleted courses found.")
    else:
        st.warning("Could not load deleted courses")


# ============================================================================
# TAB 6: MANAGE DEVICES (ADMIN)
# ============================================================================
with tab6:
    st.subheader("Admin Device Management")
    st.markdown("View, revoke, and set trust for all registered devices.")

    def fetch_all_devices(headers):
        try:
            resp = requests.get(f"{API_BASE_URL}/devices/?limit=500", headers=headers, timeout=10)
            if resp.status_code == 200:
                return resp.json().get("items", [])
        except Exception:
            pass
        return []

    def revoke_device(device_id, headers):
        try:
            resp = requests.delete(f"{API_BASE_URL}/devices/{device_id}", headers=headers, timeout=10)
            return resp.status_code == 204
        except Exception:
            return False

    def set_device_trust(device_id, is_trusted, headers):
        try:
            resp = requests.patch(
                f"{API_BASE_URL}/devices/{device_id}",
                json={"is_trusted": is_trusted},
                headers=headers,
                timeout=10
            )
            return resp.status_code == 200
        except Exception:
            return False

    headers = get_headers()
    devices = fetch_all_devices(headers)
    if not devices:
        st.info("No devices found.")
    else:
        for device in devices:
            with st.expander(f"{device.get('device_name', 'Unknown Device')} ({device.get('platform', 'unknown')}) - Trusted: {device.get('is_trusted', False)}"):
                st.write(f"**ID:** `{device.get('id')}`")
                st.write(f"**User ID:** `{device.get('user_id', 'N/A')}`")
                st.write(f"**Platform:** {device.get('platform', 'unknown')}")
                st.write(f"**First Seen:** {device.get('first_seen_at', 'N/A')}")
                st.write(f"**Last Seen:** {device.get('last_seen_at', 'N/A')}")
                st.write(f"**Active:** {'Yes' if device.get('is_active', True) else 'No'}")
                st.write(f"**Trust Score:** {device.get('trust_score', 'N/A')}")
                st.write(f"**Trusted:** {'Yes' if device.get('is_trusted', False) else 'No'}")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Revoke Device", key=f"revoke_{device['id']}"):
                        if revoke_device(device['id'], headers):
                            st.success("Device revoked.")
                            st.experimental_rerun()
                        else:
                            st.error("Failed to revoke device.")
                with col2:
                    new_trust = not device.get('is_trusted', False)
                    trust_label = "Set Trusted" if not device.get('is_trusted', False) else "Set Untrusted"
                    if st.button(trust_label, key=f"trust_{device['id']}"):
                        if set_device_trust(device['id'], new_trust, headers):
                            st.success("Trust updated.")
                            st.experimental_rerun()
                        else:
                            st.error("Failed to update trust.")


