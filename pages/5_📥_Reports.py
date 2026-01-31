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
    return {"Authorization": f"Bearer {st.session_state.get('token', '')}"}

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
            courses = response.json()

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
            courses = courses_response.json()

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

            sessions = sessions_response.json() if sessions_response.status_code == 200 else []

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
            courses = courses_response.json() if courses_response.status_code == 200 else []
        except:
            courses = []

        if courses:
            course_options = ['All'] + [c['id'] for c in courses]
            selected_courses = st.multiselect(
                "Filter by Courses",
                options=course_options,
                default=['All'],
                format_func=lambda x: 'All Courses' if x == 'All' else next((f"{c['code']} - {c['name']}" for c in courses if c['id'] == x), x)
            )

    with col2:
        st.markdown("#### Data Fields")

        if report_type == 'attendance_summary':
            fields = st.multiselect(
                "Include Fields",
                options=['date', 'course', 'session', 'total_students', 'checked_in', 'attendance_rate', 'on_time', 'late'],
                default=['date', 'course', 'session', 'checked_in', 'attendance_rate']
            )

        elif report_type == 'student_performance':
            fields = st.multiselect(
                "Include Fields",
                options=['student_name', 'student_email', 'course', 'total_sessions', 'attended', 'missed', 'attendance_rate', 'avg_checkin_time'],
                default=['student_name', 'student_email', 'attendance_rate']
            )

        elif report_type == 'risk_analysis':
            fields = st.multiselect(
                "Include Fields",
                options=['student_name', 'session', 'timestamp', 'risk_score', 'flags', 'liveness_score', 'face_match_score', 'location_valid'],
                default=['student_name', 'session', 'risk_score', 'flags']
            )

        else:  # enrollment_status
            fields = st.multiselect(
                "Include Fields",
                options=['student_name', 'student_email', 'course', 'enrolled_date', 'status', 'face_enrolled'],
                default=['student_name', 'course', 'status']
            )

        export_format = st.selectbox(
            "Export Format",
            options=['csv', 'xlsx', 'json'],
            format_func=lambda x: {'csv': 'CSV', 'xlsx': 'Excel', 'json': 'JSON'}[x],
            key="custom_format"
        )

    st.markdown("---")

    # Preview section
    st.markdown("#### Preview")
    st.info("Click 'Generate Report' to preview and download the custom report.")

    if st.button("📥 Generate Custom Report", use_container_width=True, key="gen_custom_report"):
        with st.spinner("Generating custom report..."):
            # Build sample data for demonstration
            # In production, this would call a custom report endpoint
            st.warning("Custom report generation requires a backend endpoint. Showing sample structure.")

            sample_data = []
            if report_type == 'attendance_summary':
                sample_data = [
                    {'date': '2024-01-15', 'course': 'CS101', 'session': 'Week 1 Lecture', 'checked_in': 45, 'attendance_rate': 0.9}
                ]
            elif report_type == 'student_performance':
                sample_data = [
                    {'student_name': 'John Doe', 'student_email': 'john@example.com', 'attendance_rate': 0.85}
                ]
            elif report_type == 'risk_analysis':
                sample_data = [
                    {'student_name': 'Jane Smith', 'session': 'Week 2 Lab', 'risk_score': 0.75, 'flags': ['location_mismatch']}
                ]
            else:
                sample_data = [
                    {'student_name': 'Bob Wilson', 'course': 'CS101', 'status': 'active'}
                ]

            if sample_data:
                df = pd.DataFrame(sample_data)
                st.dataframe(df, use_container_width=True)

                # Provide download
                if export_format == 'csv':
                    csv_data = df.to_csv(index=False)
                    st.download_button(
                        "📥 Download Sample CSV",
                        csv_data,
                        f"custom_report_{report_type}.csv",
                        "text/csv",
                        use_container_width=True
                    )
                elif export_format == 'json':
                    json_data = df.to_json(orient='records', indent=2)
                    st.download_button(
                        "📥 Download Sample JSON",
                        json_data,
                        f"custom_report_{report_type}.json",
                        "application/json",
                        use_container_width=True
                    )


if __name__ == "__main__":
    main()
