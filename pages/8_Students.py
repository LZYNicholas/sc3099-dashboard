"""SAIV Instructor Dashboard - Student Analytics Page
"""

import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from lib.auth_state import API_BASE_URL, get_auth_headers, require_auth
from lib.response_utils import extract_items

st.set_page_config(page_title="Students - SAIV Dashboard", layout="wide")


def get_headers():
    return get_auth_headers()


def main():
    require_auth()

    st.title("Student Analytics")
    st.markdown("View student attendance data and performance metrics.")

    # Course filter
    try:
        courses_resp = requests.get(
            f"{API_BASE_URL}/courses/",
            headers=get_headers(),
            timeout=10,
        )
        courses = extract_items(courses_resp.json()) if courses_resp.status_code == 200 else []
    except Exception:
        courses = []

    course_options = {c["id"]: f"{c['code']} - {c['name']}" for c in courses if isinstance(c, dict) and c.get("id")}

    if not course_options:
        st.info("No courses available.")
        return

    selected_course = st.selectbox(
        "Select Course",
        options=list(course_options.keys()),
        format_func=lambda x: course_options[x],
    )

    # Fetch enrolled students
    try:
        students_resp = requests.get(
            f"{API_BASE_URL}/courses/{selected_course}/enrollments",
            headers=get_headers(),
            timeout=10,
        )
        students = extract_items(students_resp.json()) if students_resp.status_code == 200 else []
    except Exception:
        students = []

    if not students:
        st.info("No students enrolled in this course.")
        return

    st.markdown("---")

    # Student selector
    student_options = {
        s.get("student_id", s.get("user_id", s.get("id"))): s.get("student_name", s.get("full_name", s.get("email", "Unknown")))
        for s in students
        if isinstance(s, dict)
    }

    selected_student_id = st.selectbox(
        "Select Student",
        options=list(student_options.keys()),
        format_func=lambda x: student_options[x],
    )

    # Fetch individual student stats
    if selected_student_id:
        try:
            stats_resp = requests.get(
                f"{API_BASE_URL}/stats/students/{selected_student_id}",
                headers=get_headers(),
                timeout=10,
            )
            if stats_resp.status_code == 200:
                stats = stats_resp.json()

                st.subheader(f"{stats.get('student_name', student_options.get(selected_student_id, 'Student'))} - Performance Summary")

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Enrolled Courses", stats.get("enrolled_courses", "N/A"))
                with col2:
                    st.metric("Total Sessions", stats.get("total_sessions", 0))
                with col3:
                    st.metric("Attended", stats.get("attended_sessions", 0))
                with col4:
                    rate = stats.get("attendance_rate", 0)
                    if isinstance(rate, (int, float)) and rate <= 1:
                        rate = rate * 100
                    st.metric("Attendance Rate", f"{rate:.1f}%")

                # Attendance pie chart
                attended = stats.get("attended_sessions", 0)
                missed = stats.get("missed_sessions", stats.get("total_sessions", 0) - attended)
                if attended or missed:
                    fig = px.pie(
                        names=["Attended", "Missed"],
                        values=[attended, missed],
                        title="Attendance Breakdown",
                        color_discrete_sequence=["#28a745", "#dc3545"],
                    )
                    st.plotly_chart(fig, use_container_width=True)

                # Recent sessions
                recent = stats.get("recent_sessions", [])
                if recent:
                    st.subheader("Recent Sessions")
                    df = pd.DataFrame(recent)
                    st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.warning("Could not load student statistics.")
        except Exception as e:
            st.error(f"Error loading student stats: {e}")

    # All students overview table
    st.markdown("---")
    st.subheader("All Students Overview")

    display = []
    for s in students:
        if not isinstance(s, dict):
            continue
        display.append({
            "Name": s.get("student_name", s.get("full_name", s.get("email", "N/A"))),
            "Email": s.get("email", s.get("student_email", "N/A")),
            "Status": s.get("status", "active").title(),
            "Face Enrolled": "Yes" if s.get("face_enrolled") else "No",
        })

    if display:
        st.dataframe(pd.DataFrame(display), use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
