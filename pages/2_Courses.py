"""SAIV Instructor Dashboard - Courses Analytics Page
"""

import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from lib.auth_state import API_BASE_URL, get_auth_headers, require_auth
from lib.response_utils import bool_query, extract_items

# Page configuration
st.set_page_config(page_title="Courses - SAIV Dashboard", layout="wide")

def get_headers():
    return get_auth_headers()


def response_error(response: requests.Response | None, fallback: str = "Unknown error") -> str:
    if response is None:
        return "Connection error"
    try:
        payload = response.json()
    except Exception:
        payload = None
    if isinstance(payload, dict):
        detail = payload.get('detail') or payload.get('message') or payload.get('error')
        if detail:
            return str(detail)
    return fallback

def main():
    require_auth()

    st.title("Course Analytics")
    st.markdown("View detailed statistics and analytics for your courses.")

    # Fetch only active courses (no analytics for deleted courses)
    try:
        response = requests.get(
            f"{API_BASE_URL}/courses/",
            params={"is_active": bool_query(True), "limit": 100},
            headers=get_headers(),
            timeout=10
        )

        if response.status_code == 200:
            courses = extract_items(response.json())

            if not courses:
                st.info("No active courses found. Create a course in the Manage page.")
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
                    venue_lat = selected_course.get('venue_latitude')
                    venue_lon = selected_course.get('venue_longitude')
                    risk_threshold = selected_course.get('risk_threshold')

                    # Course Info Card
                    st.markdown("---")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.markdown("### Course Details")
                        st.write(f"**Code:** {selected_course.get('code', 'N/A')}")
                        st.write(f"**Name:** {selected_course.get('name', 'N/A')}")
                        st.write(f"**Semester:** {selected_course.get('semester', 'N/A')}")
                    with col2:
                        st.markdown("### Location")
                        st.write(f"**Latitude:** {venue_lat if venue_lat is not None else 'Not set'}")
                        st.write(f"**Longitude:** {venue_lon if venue_lon is not None else 'Not set'}")
                        st.write(f"**Radius:** {selected_course.get('geofence_radius_meters', 'Not set')}m")
                    with col3:
                        st.markdown("### Security")
                        st.write(f"**Risk Threshold:** {risk_threshold if risk_threshold is not None else 'Not set'}")
                        st.write(f"**Face Recognition:** {'On' if selected_course.get('require_face_recognition') else 'Off'}")
                        st.write(f"**Device Binding:** {'On' if selected_course.get('require_device_binding') else 'Off'}")
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
                        st.subheader("Course Statistics")

                        # Metrics row
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Total Sessions", stats.get('total_sessions', 0))
                        with col2:
                            st.metric("Total Enrollments", stats.get('total_enrollments', 0))
                        with col3:
                            total_checkins = stats.get('total_checkins', stats.get('total_checked_in', 0))
                            st.metric("Total Check-ins", total_checkins)
                        with col4:
                            rate = stats.get('attendance_rate', 0) * 100
                            st.metric("Attendance Rate", f"{rate:.1f}%")

                        st.markdown("---")

                        # Charts
                        col1, col2 = st.columns(2)

                        with col1:
                            st.subheader("Attendance Trend")
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
                            st.subheader("Session Breakdown")
                            session_data = stats.get('sessions', [])
                            if session_data:
                                df = pd.DataFrame(session_data)
                                # Accept multiple backend payload variants for session check-in count.
                                y_col = None
                                for candidate in ['checkin_count', 'checked_in', 'checked_in_count', 'total_checkins']:
                                    if candidate in df.columns:
                                        y_col = candidate
                                        break

                                x_col = 'name' if 'name' in df.columns else ('session_name' if 'session_name' in df.columns else None)

                                if y_col is None or x_col is None:
                                    st.info("Session breakdown data is available but missing expected fields.")
                                    st.dataframe(df, use_container_width=True, hide_index=True)
                                else:
                                    if 'status' not in df.columns:
                                        df['status'] = 'unknown'
                                    fig = px.bar(
                                        df, x=x_col, y=y_col,
                                        labels={x_col: 'Session', y_col: 'Check-ins'},
                                        color='status',
                                        color_discrete_map={
                                            'scheduled': '#6c757d',
                                            'active': '#28a745',
                                            'completed': '#1f77b4',
                                            'cancelled': '#dc3545',
                                            'unknown': '#9ca3af'
                                        }
                                    )
                                    st.plotly_chart(fig, use_container_width=True)
                            else:
                                st.info("No session data available.")

                        # Student Performance Table
                        st.markdown("---")
                        st.subheader("Student Attendance")
                        student_data = stats.get('student_attendance', [])
                        if student_data:
                            df = pd.DataFrame(student_data)
                            df['attendance_rate'] = (df['attendance_rate'] * 100).round(1).astype(str) + '%'
                            st.dataframe(df, use_container_width=True, hide_index=True)
                        else:
                            st.info("No student attendance data available.")

                    else:
                        if stats_response.status_code == 404:
                            st.info("Course statistics endpoint is not available on this backend branch yet.")
                        else:
                            st.warning(f"Could not load course statistics ({stats_response.status_code}): {response_error(stats_response)}")

                except Exception as e:
                    st.warning(f"Could not load course statistics: {str(e)}")

                # Enrolled Students Section
                st.markdown("---")
                st.subheader("Enrolled Students")
                try:
                    enroll_response = requests.get(
                        f"{API_BASE_URL}/enrollments/course/{selected_course_id}",
                        headers=get_headers(),
                        timeout=10
                    )

                    if enroll_response.status_code == 200:
                        enroll_data = enroll_response.json()
                        enrollments = enroll_data.get('students', enroll_data) if isinstance(enroll_data, dict) else enroll_data
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
                        st.warning(f"Could not load enrollment data ({enroll_response.status_code}): {response_error(enroll_response)}")

                except Exception as e:
                    st.warning(f"Could not load enrollments: {str(e)}")

        else:
            st.error(f"Failed to load courses ({response.status_code}): {response_error(response)}")

    except Exception as e:
        st.error(f"Connection error: {str(e)}")


if __name__ == "__main__":
    main()
