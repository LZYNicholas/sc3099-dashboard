"""
SAIV Dashboard - Reports & Export Page
Export data for grading and record-keeping
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# Page configuration
st.set_page_config(page_title="Reports - SAIV", page_icon="📥", layout="wide")

# Check authentication
if not st.session_state.get('authenticated', False):
    st.warning("Please login from the main page to access this section.")
    st.stop()

api_client = st.session_state.api_client

st.title("📥 Reports & Data Export")
st.markdown("Export attendance data, session records, and audit logs for grading and compliance.")

st.markdown("---")

# Course Attendance Export
st.subheader("📚 Course Attendance Export")
st.markdown("Export complete attendance records for a course, suitable for gradebook import.")

with st.spinner("Loading courses..."):
    success, courses_data = api_client.get_courses()

if success:
    courses = courses_data.get('items', [])

    if courses:
        col1, col2, col3 = st.columns([2, 1, 1])

        with col1:
            course_options = {
                f"{c.get('code', 'N/A')} - {c.get('name', 'Unnamed')}": c.get('id')
                for c in courses
            }
            selected_course = st.selectbox(
                "Select Course",
                options=list(course_options.keys()),
                key="course_export"
            )
            course_id = course_options[selected_course]

        with col2:
            export_format = st.selectbox(
                "Format",
                options=["csv", "json"],
                key="course_format"
            )

        with col3:
            st.markdown("&nbsp;")  # Spacing
            if st.button("📥 Export Course Attendance", type="primary"):
                with st.spinner("Generating export..."):
                    success, data = api_client.export_course_attendance(course_id, export_format)

                    if success:
                        file_ext = export_format
                        mime_type = "text/csv" if export_format == "csv" else "application/json"
                        filename = f"attendance_{course_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{file_ext}"

                        st.download_button(
                            label=f"⬇️ Download {export_format.upper()}",
                            data=data,
                            file_name=filename,
                            mime=mime_type
                        )
                        st.success(f"Export ready: {filename}")
                    else:
                        st.error(f"Export failed: {data}")

        # Preview course statistics
        with st.expander("Preview Course Statistics"):
            with st.spinner("Loading statistics..."):
                success, stats = api_client.get_course_statistics(course_id)

                if success:
                    col1, col2, col3 = st.columns(3)

                    with col1:
                        st.metric("Total Sessions", stats.get('total_sessions', 0))
                    with col2:
                        st.metric("Total Enrolled", stats.get('total_enrolled', 0))
                    with col3:
                        rate = stats.get('overall_attendance_rate', 0) * 100
                        st.metric("Overall Attendance", f"{rate:.1f}%")

                    # Session list
                    sessions = stats.get('sessions', [])
                    if sessions:
                        st.markdown("**Sessions included in export:**")
                        df = pd.DataFrame(sessions)
                        st.dataframe(df[['name', 'date', 'attendance_rate', 'checked_in']], use_container_width=True)
                else:
                    st.warning("Could not load preview")
    else:
        st.info("No courses found.")
else:
    st.error(f"Failed to load courses: {courses_data}")

st.markdown("---")

# Session Data Export
st.subheader("🎯 Session Data Export")
st.markdown("Export detailed check-in data for a specific session.")

with st.spinner("Loading sessions..."):
    success, sessions_data = api_client.get_sessions()

if success:
    sessions = sessions_data.get('items', [])

    if sessions:
        col1, col2, col3 = st.columns([2, 1, 1])

        with col1:
            session_options = {
                f"{s.get('course_code', 'N/A')} - {s.get('name', 'Unnamed')} ({s.get('status', 'unknown')})": s.get('id')
                for s in sessions
            }
            selected_session = st.selectbox(
                "Select Session",
                options=list(session_options.keys()),
                key="session_export"
            )
            session_id = session_options[selected_session]

        with col2:
            session_format = st.selectbox(
                "Format",
                options=["csv", "json"],
                key="session_format"
            )

        with col3:
            st.markdown("&nbsp;")
            if st.button("📥 Export Session Data", type="primary"):
                with st.spinner("Generating export..."):
                    success, data = api_client.export_session_data(session_id, session_format)

                    if success:
                        file_ext = session_format
                        mime_type = "text/csv" if session_format == "csv" else "application/json"
                        filename = f"session_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{file_ext}"

                        st.download_button(
                            label=f"⬇️ Download {session_format.upper()}",
                            data=data,
                            file_name=filename,
                            mime=mime_type
                        )
                        st.success(f"Export ready: {filename}")
                    else:
                        st.error(f"Export failed: {data}")

        # Preview session check-ins
        with st.expander("Preview Session Check-ins"):
            with st.spinner("Loading check-ins..."):
                success, checkins = api_client.get_session_checkins(session_id)

                if success and checkins:
                    df = pd.DataFrame(checkins)
                    display_cols = ['student_name', 'student_email', 'status', 'checked_in_at', 'risk_score']
                    available_cols = [col for col in display_cols if col in df.columns]
                    st.dataframe(df[available_cols], use_container_width=True)
                    st.write(f"Total check-ins: {len(checkins)}")
                else:
                    st.info("No check-ins for this session")
    else:
        st.info("No sessions found.")
else:
    st.error(f"Failed to load sessions: {sessions_data}")

st.markdown("---")

# Bulk Export Section
st.subheader("📦 Bulk Data Export")
st.markdown("Export data across multiple courses or date ranges.")

col1, col2 = st.columns(2)

with col1:
    st.markdown("#### Date Range")
    bulk_start = st.date_input(
        "Start Date",
        value=datetime.now() - timedelta(days=30),
        key="bulk_start"
    )
    bulk_end = st.date_input(
        "End Date",
        value=datetime.now(),
        key="bulk_end"
    )

with col2:
    st.markdown("#### Export Options")
    include_checkins = st.checkbox("Include Check-in Details", value=True)
    include_risk = st.checkbox("Include Risk Factors", value=True)
    include_devices = st.checkbox("Include Device Information", value=False)

st.info("Bulk export generates a comprehensive report with all selected data for the specified date range.")

if st.button("📦 Generate Bulk Report", type="primary"):
    st.warning("Bulk export functionality requires additional backend endpoints. Please use individual course/session exports above.")

st.markdown("---")

# Report Templates
st.subheader("📋 Report Templates")
st.markdown("Quick access to common report types.")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("#### 📊 Attendance Summary")
    st.markdown("""
    - Overall attendance rates
    - Per-session breakdown
    - Student rankings
    - Trend analysis
    """)
    if st.button("Generate Summary Report"):
        st.info("Use Course Attendance Export for comprehensive attendance data")

with col2:
    st.markdown("#### ⚠️ Risk Report")
    st.markdown("""
    - High-risk check-ins
    - Flagged students
    - Anomaly detection
    - Security concerns
    """)
    if st.button("Generate Risk Report"):
        st.info("Use Session Data Export and filter by risk score")

with col3:
    st.markdown("#### 📈 Analytics Report")
    st.markdown("""
    - Check-in patterns
    - Peak times analysis
    - Device statistics
    - Geographic distribution
    """)
    if st.button("Generate Analytics Report"):
        st.info("Use Audit Logs page for detailed analytics data")

st.markdown("---")

# Export History (placeholder)
st.subheader("📜 Recent Exports")
st.info("Export history tracking is available in the audit logs. All export operations are logged for compliance.")

# Help section
with st.expander("❓ Export Help"):
    st.markdown("""
    ### CSV Format
    - Compatible with Excel, Google Sheets, and gradebook systems
    - UTF-8 encoding for international characters
    - Headers included in first row

    ### JSON Format
    - Structured data for programmatic access
    - Includes nested risk factors and device information
    - Suitable for data analysis tools

    ### Gradebook Integration
    1. Export course attendance in CSV format
    2. Open in Excel or Google Sheets
    3. Map student IDs to your gradebook system
    4. Import attendance scores

    ### Compliance Requirements
    - All exports are logged in the audit trail
    - Data includes timestamps and user attribution
    - Export files should be handled according to data protection policies
    """)
