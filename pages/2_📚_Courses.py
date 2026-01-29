"""
Course Analytics Page
Displays course-level attendance analytics and trends
"""

import streamlit as st
from components.charts import (
    create_attendance_trend_chart,
    create_session_comparison_chart
)
from components.tables import display_student_attendance_table, create_summary_metrics
from utils.formatters import format_percentage, format_datetime
import pandas as pd
from datetime import datetime

# Check authentication
if not st.session_state.get('authenticated'):
    st.error("Please login to access this page")
    st.stop()

st.title("📚 Course Analytics")
st.markdown("Detailed attendance analytics and trends by course")

# Get API client
api_client = st.session_state.api_client

# Load courses
with st.spinner("Loading courses..."):
    success, courses = api_client.get_courses()

    if not success:
        st.error(f"Failed to load courses: {courses}")
        st.stop()

    if not courses:
        st.info("No courses available")
        st.stop()

# Course selector
st.markdown("### Select Course")
course_options = {f"{c['code']} - {c['name']}": c['id'] for c in courses}
selected_course = st.selectbox(
    "Choose a course to view analytics",
    options=list(course_options.keys()),
    help="Select a course to view detailed attendance statistics"
)

if selected_course:
    course_id = course_options[selected_course]

    # Refresh button
    col1, col2, col3 = st.columns([1, 1, 4])
    with col1:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()
    with col2:
        if st.button("📥 Export Data", use_container_width=True):
            st.session_state.show_export = True

    st.divider()

    # Load course statistics
    with st.spinner("Loading course statistics..."):
        success, course_stats = api_client.get_course_statistics(course_id)

        if success:
            # Display key metrics
            st.markdown("### Course Overview")
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric(
                    "Total Students",
                    course_stats.get('total_students', 0),
                    help="Number of students enrolled in this course"
                )

            with col2:
                st.metric(
                    "Total Sessions",
                    course_stats.get('total_sessions', 0),
                    help="Total number of sessions scheduled"
                )

            with col3:
                avg_attendance = course_stats.get('average_attendance_rate', 0)
                st.metric(
                    "Average Attendance",
                    format_percentage(avg_attendance),
                    help="Average attendance rate across all sessions"
                )

            with col4:
                st.metric(
                    "Total Check-ins",
                    course_stats.get('total_checkins', 0),
                    help="Total check-ins across all sessions"
                )

            # Additional metrics
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric(
                    "Sessions Completed",
                    course_stats.get('completed_sessions', 0),
                    help="Number of past sessions"
                )

            with col2:
                st.metric(
                    "Upcoming Sessions",
                    course_stats.get('upcoming_sessions', 0),
                    help="Number of future sessions"
                )

            with col3:
                low_attendance = course_stats.get('students_low_attendance', 0)
                st.metric(
                    "Low Attendance Students",
                    low_attendance,
                    delta=f"-{low_attendance}" if low_attendance > 0 else "0",
                    delta_color="inverse",
                    help="Students with < 75% attendance"
                )

            with col4:
                perfect_attendance = course_stats.get('students_perfect_attendance', 0)
                st.metric(
                    "Perfect Attendance",
                    perfect_attendance,
                    delta=f"+{perfect_attendance}" if perfect_attendance > 0 else "0",
                    help="Students with 100% attendance"
                )

        else:
            st.error(f"Failed to load course statistics: {course_stats}")

    st.divider()

    # Attendance trends
    st.markdown("### Attendance Trends")
    with st.spinner("Loading attendance trends..."):
        if success and course_stats.get('session_trends'):
            chart = create_attendance_trend_chart(
                course_stats['session_trends'],
                title="Attendance Rate by Session"
            )
            st.plotly_chart(chart, use_container_width=True)
        else:
            st.info("No trend data available")

    st.divider()

    # Session breakdown
    st.markdown("### Session-by-Session Breakdown")
    with st.spinner("Loading sessions..."):
        success_sessions, sessions = api_client.get_sessions(course_id=course_id)

        if success_sessions and sessions:
            # Create comparison data
            comparison_data = []
            for session in sessions:
                # Get detailed session stats
                success_session, session_stats = api_client.get_session_statistics(session['id'])
                if success_session:
                    comparison_data.append({
                        'session_name': f"{session.get('title', 'N/A')[:20]}...",
                        'expected': session_stats.get('expected_attendance', 0),
                        'actual': session_stats.get('actual_attendance', 0)
                    })

            if comparison_data:
                chart = create_session_comparison_chart(
                    comparison_data,
                    title="Expected vs Actual Attendance by Session"
                )
                st.plotly_chart(chart, use_container_width=True)

            # Detailed session table
            st.markdown("#### Detailed Session List")
            session_data = []
            for session in sessions:
                success_session, session_stats = api_client.get_session_statistics(session['id'])
                attendance_rate = 0
                if success_session:
                    expected = session_stats.get('expected_attendance', 0)
                    actual = session_stats.get('actual_attendance', 0)
                    attendance_rate = (actual / expected * 100) if expected > 0 else 0

                session_data.append({
                    'Title': session.get('title', 'N/A'),
                    'Date': format_datetime(session.get('scheduled_time'), "%Y-%m-%d"),
                    'Time': format_datetime(session.get('scheduled_time'), "%H:%M"),
                    'Location': session.get('location', 'N/A'),
                    'Check-ins': session.get('checkin_count', 0),
                    'Attendance Rate': format_percentage(attendance_rate),
                    'Status': 'Active' if session.get('is_active') else 'Completed'
                })

            if session_data:
                df = pd.DataFrame(session_data)
                st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No sessions found for this course")

    st.divider()

    # Student attendance
    st.markdown("### Student Attendance")

    # Filter options
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        show_all = st.checkbox("Show all students", value=True)
    with col2:
        show_low = st.checkbox("Highlight low attendance", value=True)

    with st.spinner("Loading student attendance..."):
        success_students, enrollments = api_client.get_course_enrollments(course_id)

        if success_students and enrollments:
            # Calculate attendance for each student
            student_attendance = []

            for enrollment in enrollments:
                student = enrollment.get('student', {})
                # In a real implementation, you would fetch actual attendance data
                # For now, we'll use mock data structure
                student_attendance.append({
                    'student_id': student.get('id'),
                    'student_name': student.get('full_name', 'N/A'),
                    'email': student.get('email', 'N/A'),
                    'attended': enrollment.get('sessions_attended', 0),
                    'total': course_stats.get('total_sessions', 0),
                    'attendance_rate': enrollment.get('attendance_rate', 0),
                    'last_checkin': enrollment.get('last_checkin')
                })

            # Filter if needed
            if not show_all:
                student_attendance = [s for s in student_attendance if s['attendance_rate'] < 75]

            # Display table
            display_student_attendance_table(student_attendance, show_low_attendance=show_low)

            # Low attendance alerts
            low_attendance_students = [s for s in student_attendance if s['attendance_rate'] < 75]
            if low_attendance_students:
                st.warning(f"⚠️ **{len(low_attendance_students)} students with low attendance (< 75%)**")

                with st.expander("View students at risk"):
                    for student in low_attendance_students:
                        col1, col2, col3 = st.columns([2, 1, 1])
                        with col1:
                            st.write(f"**{student['student_name']}**")
                            st.caption(student['email'])
                        with col2:
                            st.write(f"{student['attended']}/{student['total']} sessions")
                        with col3:
                            st.write(format_percentage(student['attendance_rate']))

        else:
            st.info("No enrollment data available")

    # Export functionality
    if st.session_state.get('show_export'):
        st.divider()
        st.markdown("### Export Course Data")

        col1, col2 = st.columns(2)

        with col1:
            export_format = st.selectbox(
                "Export Format",
                options=["CSV", "JSON"],
                help="Select the format for exported data"
            )

        with col2:
            if st.button("📥 Download", type="primary", use_container_width=True):
                with st.spinner("Generating export..."):
                    format_lower = export_format.lower()
                    success_export, data = api_client.export_course_attendance(
                        course_id,
                        format=format_lower
                    )

                    if success_export:
                        # Get course info for filename
                        course_info = next((c for c in courses if c['id'] == course_id), {})
                        course_code = course_info.get('code', 'course')
                        filename = f"{course_code}_attendance_{datetime.now().strftime('%Y%m%d')}.{format_lower}"

                        st.download_button(
                            label=f"Download {export_format}",
                            data=data,
                            file_name=filename,
                            mime="text/csv" if format_lower == "csv" else "application/json",
                            use_container_width=True
                        )
                        st.success("Export ready!")
                    else:
                        st.error(f"Export failed: {data}")

        if st.button("Close Export"):
            st.session_state.show_export = False
            st.rerun()

# Tips for improving attendance
with st.expander("💡 Tips for Improving Attendance"):
    st.markdown("""
    **Strategies for Better Attendance:**
    - **Early Intervention**: Contact students with < 75% attendance early
    - **Engagement**: Make sessions interactive and valuable
    - **Reminders**: Send session reminders via email or LMS
    - **Flexibility**: Consider hybrid options when appropriate
    - **Accountability**: Clearly communicate attendance policies

    **Using This Data:**
    - Export attendance data regularly for record-keeping
    - Identify patterns in low attendance (specific days/times)
    - Share attendance statistics with students
    - Use data to inform course improvements
    - Follow up with at-risk students individually
    """)
