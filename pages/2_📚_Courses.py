"""
SAIV Instructor Dashboard - Courses Analytics Page
"""

import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Page configuration
st.set_page_config(page_title="Courses - SAIV Dashboard", page_icon="📚", layout="wide")

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

    st.title("📚 Course Analytics")
    st.markdown("View detailed statistics and analytics for your courses.")

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
                st.info("No courses found. Create a course in the Manage page.")
                return

            # Course selector
            course_options = {c['id']: f"{c['code']} - {c['name']}" for c in courses}
            selected_course_id = st.selectbox(
                "Select Course",
                options=list(course_options.keys()),
                format_func=lambda x: course_options[x]
            )

            if selected_course_id:
                # Get course details
                selected_course = next((c for c in courses if c['id'] == selected_course_id), None)

                if selected_course:
                    # Course Info Card
                    st.markdown("---")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.markdown("### 📖 Course Details")
                        st.write(f"**Code:** {selected_course.get('code', 'N/A')}")
                        st.write(f"**Name:** {selected_course.get('name', 'N/A')}")
                        st.write(f"**Semester:** {selected_course.get('semester', 'N/A')}")
                    with col2:
                        st.markdown("### 📍 Location")
                        st.write(f"**Latitude:** {selected_course.get('geofence_latitude', 'Not set')}")
                        st.write(f"**Longitude:** {selected_course.get('geofence_longitude', 'Not set')}")
                        st.write(f"**Radius:** {selected_course.get('geofence_radius_meters', 'Not set')}m")
                    with col3:
                        st.markdown("### ⏰ Timing")
                        st.write(f"**Late Threshold:** {selected_course.get('late_threshold_minutes', 15)} min")
                        st.write(f"**Created:** {selected_course.get('created_at', 'Unknown')[:10] if selected_course.get('created_at') else 'Unknown'}")

                # Fetch course statistics
                try:
                    stats_response = requests.get(
                        f"{API_BASE_URL}/stats/courses/{selected_course_id}",
                        headers=get_headers(),
                        timeout=10
                    )

                    if stats_response.status_code == 200:
                        stats = stats_response.json()

                        st.markdown("---")
                        st.subheader("📊 Course Statistics")

                        # Metrics row
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Total Sessions", stats.get('total_sessions', 0))
                        with col2:
                            st.metric("Total Enrollments", stats.get('total_enrollments', 0))
                        with col3:
                            st.metric("Total Check-ins", stats.get('total_checkins', 0))
                        with col4:
                            rate = stats.get('attendance_rate', 0) * 100
                            st.metric("Attendance Rate", f"{rate:.1f}%")

                        st.markdown("---")

                        # Charts
                        col1, col2 = st.columns(2)

                        with col1:
                            st.subheader("📈 Attendance Trend")
                            trend_data = stats.get('attendance_trend', [])
                            if trend_data:
                                df = pd.DataFrame(trend_data)
                                fig = px.line(
                                    df, x='date', y='attendance_rate',
                                    labels={'date': 'Date', 'attendance_rate': 'Rate (%)'},
                                    markers=True
                                )
                                fig.update_layout(yaxis_range=[0, 100])
                                st.plotly_chart(fig, use_container_width=True)
                            else:
                                st.info("No attendance trend data available.")

                        with col2:
                            st.subheader("🎯 Session Breakdown")
                            session_data = stats.get('sessions', [])
                            if session_data:
                                df = pd.DataFrame(session_data)
                                fig = px.bar(
                                    df, x='name', y='checkin_count',
                                    labels={'name': 'Session', 'checkin_count': 'Check-ins'},
                                    color='status',
                                    color_discrete_map={
                                        'scheduled': '#6c757d',
                                        'active': '#28a745',
                                        'completed': '#1f77b4',
                                        'cancelled': '#dc3545'
                                    }
                                )
                                st.plotly_chart(fig, use_container_width=True)
                            else:
                                st.info("No session data available.")

                        # Student Performance Table
                        st.markdown("---")
                        st.subheader("👥 Student Attendance")
                        student_data = stats.get('student_attendance', [])
                        if student_data:
                            df = pd.DataFrame(student_data)
                            df['attendance_rate'] = (df['attendance_rate'] * 100).round(1).astype(str) + '%'
                            st.dataframe(df, use_container_width=True, hide_index=True)
                        else:
                            st.info("No student attendance data available.")

                    else:
                        st.warning("Could not load course statistics.")

                except Exception as e:
                    st.warning(f"Could not load course statistics: {str(e)}")

                # Enrolled Students Section
                st.markdown("---")
                st.subheader("📋 Enrolled Students")
                try:
                    enroll_response = requests.get(
                        f"{API_BASE_URL}/enrollments/course/{selected_course_id}",
                        headers=get_headers(),
                        timeout=10
                    )

                    if enroll_response.status_code == 200:
                        enrollments = enroll_response.json()
                        if enrollments:
                            df = pd.DataFrame(enrollments)
                            display_cols = ['student_name', 'student_email', 'enrolled_at', 'status']
                            available_cols = [c for c in display_cols if c in df.columns]
                            if available_cols:
                                st.dataframe(df[available_cols], use_container_width=True, hide_index=True)
                            else:
                                st.dataframe(df, use_container_width=True, hide_index=True)
                        else:
                            st.info("No students enrolled in this course.")
                    else:
                        st.warning("Could not load enrollment data.")

                except Exception as e:
                    st.warning(f"Could not load enrollments: {str(e)}")

        else:
            st.error("Failed to load courses.")

    except Exception as e:
        st.error(f"Connection error: {str(e)}")


if __name__ == "__main__":
    main()
