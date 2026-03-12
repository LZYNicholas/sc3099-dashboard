"""
SAIV Instructor Dashboard - Reports & Export Page
"""

import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# Page configuration
st.set_page_config(page_title="Reports - SAIV Dashboard", page_icon="📥", layout="wide")

API_BASE_URL = "http://localhost:8000/api/v1"

def check_auth():
    """Check if user is authenticated"""
    if not st.session_state.get('authenticated', False):
        st.warning("Please login from the main page.")
        st.stop()

def get_headers():
    """Get authorization headers"""
    return {"Authorization": f"Bearer {st.session_state.get('access_token', '')}"}

def main():
    check_auth()

    st.title("📥 Reports & Data Export")
    st.markdown("Generate and download attendance reports in various formats.")

    # Tabs for different report types
    tab1, tab2, tab3 = st.tabs(["📚 Course Reports", "🎯 Session Reports", "📊 Custom Reports"])

    with tab1:
        course_reports()

    with tab2:
        session_reports()

    with tab3:
        custom_reports()


def course_reports():
    """Course attendance reports"""
    st.subheader("Course Attendance Reports")
    st.markdown("Export attendance data for entire courses.")

    # Fetch courses
    try:
        response = requests.get(
            f"{API_BASE_URL}/courses/",
            headers=get_headers(),
            timeout=10
        )

        if response.status_code == 200:
            courses_data = response.json()
            courses = courses_data.get('items', []) if isinstance(courses_data, dict) else courses_data

            if not courses:
                st.info("No courses available. Create a course first.")
                return

            col1, col2 = st.columns(2)

            with col1:
                course_options = {c['id']: f"{c['code']} - {c['name']}" for c in courses}
                selected_course = st.selectbox(
                    "Select Course",
                    options=list(course_options.keys()),
                    format_func=lambda x: course_options[x],
                    key="course_report_select"
                )

            with col2:
                export_format = st.selectbox(
                    "Export Format",
                    options=['csv', 'xlsx', 'json'],
                    format_func=lambda x: {'csv': 'CSV (Comma Separated)', 'xlsx': 'Excel', 'json': 'JSON'}[x],
                    key="course_format"
                )

            st.markdown("---")

            # Report options
            st.markdown("#### Report Options")
            col1, col2 = st.columns(2)

            with col1:
                include_details = st.checkbox("Include check-in details", value=True)
                include_stats = st.checkbox("Include summary statistics", value=True)

            with col2:
                include_risk = st.checkbox("Include risk scores", value=False)
                include_location = st.checkbox("Include location data", value=False)

            st.markdown("---")

            if st.button("📥 Generate Course Report", use_container_width=True, key="gen_course_report"):
                with st.spinner("Generating report..."):
                    try:
                        response = requests.get(
                            f"{API_BASE_URL}/export/attendance/{selected_course}?format={export_format}",
                            headers=get_headers(),
                            timeout=30
                        )

                        if response.status_code == 200:
                            # Get filename
                            course_name = course_options[selected_course].replace(' ', '_').replace('-', '_')
                            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                            filename = f"attendance_{course_name}_{timestamp}.{export_format}"

                            # Determine mime type
                            mime_types = {
                                'csv': 'text/csv',
                                'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                                'json': 'application/json'
                            }

                            st.success("Report generated successfully!")
                            st.download_button(
                                f"📥 Download {export_format.upper()} Report",
                                response.content,
                                filename,
                                mime_types.get(export_format, 'application/octet-stream'),
                                use_container_width=True
                            )
                        else:
                            st.error(f"Failed to generate report. Status: {response.status_code}")

                    except Exception as e:
                        st.error(f"Error generating report: {str(e)}")

        else:
            st.error("Failed to load courses.")

    except Exception as e:
        st.error(f"Connection error: {str(e)}")


def session_reports():
    """Session-specific reports"""
    st.subheader("Session Reports")
    st.markdown("Export attendance data for individual sessions.")

    # Fetch courses and sessions
    try:
        courses_response = requests.get(
            f"{API_BASE_URL}/courses/",
            headers=get_headers(),
            timeout=10
        )

        if courses_response.status_code == 200:
            courses_data = courses_response.json()
            courses = courses_data.get('items', []) if isinstance(courses_data, dict) else courses_data

            if not courses:
                st.info("No courses available.")
                return

            col1, col2 = st.columns(2)

            with col1:
                course_options = {c['id']: f"{c['code']} - {c['name']}" for c in courses}
                selected_course = st.selectbox(
                    "Select Course",
                    options=list(course_options.keys()),
                    format_func=lambda x: course_options[x],
                    key="session_course_select"
                )

            # Fetch sessions for selected course
            sessions_response = requests.get(
                f"{API_BASE_URL}/sessions/?course_id={selected_course}",
                headers=get_headers(),
                timeout=10
            )

            sessions_data = sessions_response.json() if sessions_response.status_code == 200 else {}
            sessions = sessions_data.get('items', []) if isinstance(sessions_data, dict) else sessions_data

            with col2:
                if sessions:
                    session_options = {s['id']: f"{s['name']} ({s.get('status', 'unknown')})" for s in sessions}
                    selected_session = st.selectbox(
                        "Select Session",
                        options=list(session_options.keys()),
                        format_func=lambda x: session_options[x],
                        key="session_report_select"
                    )
                else:
                    st.info("No sessions available for this course.")
                    return

            col1, col2 = st.columns(2)

            with col1:
                export_format = st.selectbox(
                    "Export Format",
                    options=['csv', 'xlsx', 'json'],
                    format_func=lambda x: {'csv': 'CSV', 'xlsx': 'Excel', 'json': 'JSON'}[x],
                    key="session_format"
                )

            with col2:
                include_photos = st.checkbox("Include photo references", value=False)

            st.markdown("---")

            if st.button("📥 Generate Session Report", use_container_width=True, key="gen_session_report"):
                with st.spinner("Generating report..."):
                    try:
                        response = requests.get(
                            f"{API_BASE_URL}/export/session/{selected_session}?format={export_format}",
                            headers=get_headers(),
                            timeout=30
                        )

                        if response.status_code == 200:
                            session_name = session_options[selected_session].split('(')[0].strip().replace(' ', '_')
                            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                            filename = f"session_{session_name}_{timestamp}.{export_format}"

                            mime_types = {
                                'csv': 'text/csv',
                                'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                                'json': 'application/json'
                            }

                            st.success("Report generated successfully!")
                            st.download_button(
                                f"📥 Download {export_format.upper()} Report",
                                response.content,
                                filename,
                                mime_types.get(export_format, 'application/octet-stream'),
                                use_container_width=True
                            )
                        else:
                            st.error(f"Failed to generate report. Status: {response.status_code}")

                    except Exception as e:
                        st.error(f"Error generating report: {str(e)}")

        else:
            st.error("Failed to load courses.")

    except Exception as e:
        st.error(f"Connection error: {str(e)}")


def custom_reports():
    """Custom report builder"""
    st.subheader("Custom Report Builder")
    st.markdown("Build custom reports with specific data fields and filters.")

    # Report type selection
    report_type = st.selectbox(
        "Report Type",
        options=['attendance_summary', 'student_performance', 'risk_analysis', 'enrollment_status'],
        format_func=lambda x: {
            'attendance_summary': '📊 Attendance Summary',
            'student_performance': '👥 Student Performance',
            'risk_analysis': '🚨 Risk Analysis',
            'enrollment_status': '📝 Enrollment Status'
        }[x]
    )

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Filters")

        # Date range
        date_col1, date_col2 = st.columns(2)
        with date_col1:
            start_date = st.date_input("Start Date", key="custom_start")
        with date_col2:
            end_date = st.date_input("End Date", key="custom_end")

        # Course filter
        try:
            courses_response = requests.get(
                f"{API_BASE_URL}/courses/",
                headers=get_headers(),
                timeout=10
            )
            courses_data = courses_response.json() if courses_response.status_code == 200 else {}
            courses = courses_data.get('items', []) if isinstance(courses_data, dict) else courses_data
        except:
            courses = []

        selected_course = None
        if courses:
            course_options = {c['id']: f"{c['code']} - {c['name']}" for c in courses}
            selected_course = st.selectbox(
                "Select Course",
                options=list(course_options.keys()),
                format_func=lambda x: course_options[x],
                key="custom_course_select"
            )

    with col2:
        st.markdown("#### Data Fields")

        if report_type == 'attendance_summary':
            fields = st.multiselect(
                "Include Fields",
                options=['date', 'course', 'session', 'attendance_rate', 'checked_in'],
                default=['date', 'course', 'session', 'checked_in', 'attendance_rate']
            )
        elif report_type == 'student_performance':
            fields = st.multiselect(
                "Include Fields",
                options=['student_name', 'sessions_attended', 'attendance_rate', 'average_risk_score'],
                default=['student_name', 'attendance_rate']
            )
        elif report_type == 'risk_analysis':
            fields = st.multiselect(
                "Include Fields",
                options=['student_name', 'session_name', 'checked_in_at', 'risk_score', 'status', 'liveness_passed', 'distance_from_venue_meters'],
                default=['student_name', 'session_name', 'risk_score', 'status']
            )
        else:  # enrollment_status
            fields = st.multiselect(
                "Include Fields",
                options=['student_name', 'student_email', 'enrolled_at', 'is_active', 'face_enrolled'],
                default=['student_name', 'student_email', 'is_active']
            )

        export_format = st.selectbox(
            "Export Format",
            options=['csv', 'json'],
            format_func=lambda x: {'csv': 'CSV', 'json': 'JSON'}[x],
            key="custom_format"
        )

    st.markdown("---")

    # Generate section
    st.markdown("#### Results")

    if st.button("📥 Generate Custom Report", use_container_width=True, key="gen_custom_report"):
        with st.spinner("Generating custom report..."):
            df = None

            try:
                if report_type == 'attendance_summary' and selected_course:
                    response = requests.get(
                        f"{API_BASE_URL}/stats/courses/{selected_course}",
                        params={
                            "start_date": f"{start_date.isoformat()}T00:00:00Z",
                            "end_date": f"{end_date.isoformat()}T23:59:59Z"
                        },
                        headers=get_headers(),
                        timeout=15
                    )
                    if response.status_code == 200:
                        data = response.json()
                        sessions = data.get('sessions', [])
                        if sessions:
                            for s in sessions:
                                s['course'] = f"{data.get('course_code', '')} - {data.get('course_name', '')}"
                            df = pd.DataFrame(sessions)
                            available = [f for f in fields if f in df.columns]
                            if available:
                                df = df[available]
                        else:
                            st.info("No session data available for this course in the selected date range.")
                    else:
                        st.error(f"Failed to fetch course statistics (HTTP {response.status_code}).")

                elif report_type == 'student_performance' and selected_course:
                    response = requests.get(
                        f"{API_BASE_URL}/stats/courses/{selected_course}",
                        headers=get_headers(),
                        timeout=15
                    )
                    if response.status_code == 200:
                        data = response.json()
                        students = data.get('student_attendance', [])
                        if students:
                            df = pd.DataFrame(students)
                            available = [f for f in fields if f in df.columns]
                            if available:
                                df = df[available]
                        else:
                            st.info("No student attendance data available for this course.")
                    else:
                        st.error(f"Failed to fetch student data (HTTP {response.status_code}).")

                elif report_type == 'risk_analysis':
                    params = {
                        "min_risk_score": 0.3,
                        "start_date": f"{start_date.isoformat()}T00:00:00Z",
                        "end_date": f"{end_date.isoformat()}T23:59:59Z",
                        "limit": 500
                    }
                    if selected_course:
                        params["course_id"] = selected_course
                    response = requests.get(
                        f"{API_BASE_URL}/checkins/",
                        params=params,
                        headers=get_headers(),
                        timeout=15
                    )
                    if response.status_code == 200:
                        data = response.json()
                        checkins = data.get('items', []) if isinstance(data, dict) else data
                        if checkins:
                            df = pd.DataFrame(checkins)
                            available = [f for f in fields if f in df.columns]
                            if available:
                                df = df[available]
                        else:
                            st.info("No elevated-risk check-ins found for the selected period.")
                    else:
                        st.error(f"Failed to fetch check-in data (HTTP {response.status_code}).")

                elif report_type == 'enrollment_status' and selected_course:
                    response = requests.get(
                        f"{API_BASE_URL}/enrollments/course/{selected_course}",
                        headers=get_headers(),
                        timeout=15
                    )
                    if response.status_code == 200:
                        data = response.json()
                        students = data.get('students', []) if isinstance(data, dict) else data
                        if students:
                            df = pd.DataFrame(students)
                            available = [f for f in fields if f in df.columns]
                            if available:
                                df = df[available]
                        else:
                            st.info("No enrolled students found for this course.")
                    else:
                        st.error(f"Failed to fetch enrollment data (HTTP {response.status_code}).")

                else:
                    if not selected_course and report_type != 'risk_analysis':
                        st.warning("Please select a course to generate this report.")

            except Exception as e:
                st.error(f"Error generating report: {str(e)}")

            # Display and export
            if df is not None and not df.empty:
                st.success(f"Generated report with {len(df)} records.")
                st.dataframe(df, use_container_width=True, hide_index=True)

                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                if export_format == 'csv':
                    csv_data = df.to_csv(index=False)
                    st.download_button(
                        "📥 Download CSV",
                        csv_data,
                        f"custom_report_{report_type}_{timestamp}.csv",
                        "text/csv",
                        use_container_width=True
                    )
                elif export_format == 'json':
                    json_data = df.to_json(orient='records', indent=2)
                    st.download_button(
                        "📥 Download JSON",
                        json_data,
                        f"custom_report_{report_type}_{timestamp}.json",
                        "application/json",
                        use_container_width=True
                    )


if __name__ == "__main__":
    main()
