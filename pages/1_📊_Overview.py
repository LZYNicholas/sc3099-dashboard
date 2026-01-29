"""
Overview Dashboard Page
Displays system-wide statistics and recent activity
"""

import streamlit as st
from components.charts import (
    create_daily_activity_chart,
    create_status_distribution_chart,
    create_risk_distribution_chart
)
from components.tables import display_flagged_checkins, create_summary_metrics
from utils.formatters import format_datetime_relative, format_percentage
import pandas as pd

# Check authentication
if not st.session_state.get('authenticated'):
    st.error("Please login to access this page")
    st.stop()

st.title("📊 System Overview")
st.markdown("Real-time dashboard showing system-wide statistics and activity")

# Refresh button
col1, col2, col3 = st.columns([1, 1, 4])
with col1:
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.rerun()

st.divider()

# Get API client
api_client = st.session_state.api_client

# Load overview statistics
with st.spinner("Loading overview statistics..."):
    success, stats = api_client.get_overview_statistics()

    if success:
        # Display key metrics
        st.markdown("### Key Metrics")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "Total Sessions",
                stats.get('total_sessions', 0),
                help="Total number of sessions across all courses"
            )

        with col2:
            st.metric(
                "Total Check-ins",
                stats.get('total_checkins', 0),
                help="Total number of student check-ins"
            )

        with col3:
            approval_rate = stats.get('approval_rate', 0)
            st.metric(
                "Approval Rate",
                format_percentage(approval_rate),
                help="Percentage of check-ins approved"
            )

        with col4:
            st.metric(
                "Active Sessions",
                stats.get('active_sessions', 0),
                help="Currently active sessions"
            )

        # Second row of metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "Total Students",
                stats.get('total_students', 0),
                help="Total number of enrolled students"
            )

        with col2:
            st.metric(
                "Total Courses",
                stats.get('total_courses', 0),
                help="Total number of courses"
            )

        with col3:
            flagged = stats.get('flagged_checkins', 0)
            st.metric(
                "Flagged Check-ins",
                flagged,
                delta=f"-{flagged}" if flagged > 0 else "0",
                delta_color="inverse",
                help="Check-ins requiring review"
            )

        with col4:
            avg_attendance = stats.get('average_attendance_rate', 0)
            st.metric(
                "Avg Attendance",
                format_percentage(avg_attendance),
                help="Average attendance rate across all courses"
            )

    else:
        st.error(f"Failed to load statistics: {stats}")

st.divider()

# Daily trends
st.markdown("### Daily Trends")
with st.spinner("Loading daily trends..."):
    success, trends_data = api_client.get_daily_trends(days=30)

    if success and trends_data:
        chart = create_daily_activity_chart(
            trends_data,
            title="Daily Check-ins and Sessions (Last 30 Days)"
        )
        st.plotly_chart(chart, use_container_width=True)
    else:
        st.info("No trend data available")

st.divider()

# Status distribution
col1, col2 = st.columns(2)

with col1:
    st.markdown("### Check-in Status Distribution")
    with st.spinner("Loading status distribution..."):
        if success and stats:
            status_data = {
                'Approved': stats.get('approved_checkins', 0),
                'Pending': stats.get('pending_checkins', 0),
                'Rejected': stats.get('rejected_checkins', 0),
                'Flagged': stats.get('flagged_checkins', 0)
            }
            chart = create_status_distribution_chart(
                status_data,
                title="Check-in Status Breakdown"
            )
            st.plotly_chart(chart, use_container_width=True)

with col2:
    st.markdown("### Risk Distribution")
    with st.spinner("Loading risk distribution..."):
        if success and stats:
            risk_data = {
                'Low': stats.get('low_risk_checkins', 0),
                'Medium': stats.get('medium_risk_checkins', 0),
                'High': stats.get('high_risk_checkins', 0)
            }
            chart = create_risk_distribution_chart(
                risk_data,
                title="Risk Score Distribution"
            )
            st.plotly_chart(chart, use_container_width=True)

st.divider()

# Recent activity
st.markdown("### Recent Activity")
with st.spinner("Loading recent check-ins..."):
    success, recent_checkins = api_client.get_recent_checkins(limit=10)

    if success and recent_checkins:
        # Create timeline
        for checkin in recent_checkins:
            col1, col2, col3, col4 = st.columns([2, 3, 2, 2])

            with col1:
                st.write(format_datetime_relative(checkin.get('timestamp')))

            with col2:
                st.write(f"**{checkin.get('student_name', 'N/A')}** checked in")
                st.caption(f"{checkin.get('course_code', 'N/A')} - {checkin.get('session_title', 'N/A')}")

            with col3:
                status = checkin.get('status', 'N/A')
                if status.lower() == 'approved':
                    st.success(status.upper())
                elif status.lower() == 'pending':
                    st.warning(status.upper())
                elif status.lower() == 'flagged':
                    st.error(status.upper())
                else:
                    st.info(status.upper())

            with col4:
                risk = checkin.get('risk_score', 0)
                if risk < 0.3:
                    st.write(f"✅ Low ({risk:.2f})")
                elif risk < 0.6:
                    st.write(f"⚠️ Medium ({risk:.2f})")
                else:
                    st.write(f"🚨 High ({risk:.2f})")

            st.divider()
    else:
        st.info("No recent activity")

# Flagged check-ins requiring review
st.markdown("### 🚩 Flagged Check-ins Requiring Review")
with st.spinner("Loading flagged check-ins..."):
    success, flagged_checkins = api_client.get_flagged_checkins(limit=20)

    if success:
        display_flagged_checkins(flagged_checkins)
    else:
        st.error(f"Failed to load flagged check-ins: {flagged_checkins}")

# System health indicators
st.divider()
st.markdown("### System Health")

col1, col2, col3 = st.columns(3)

with col1:
    # Calculate health score based on approval rate
    if success and stats:
        approval = stats.get('approval_rate', 0)
        if approval >= 90:
            st.success("✅ Excellent - High approval rate")
        elif approval >= 75:
            st.info("ℹ️ Good - Moderate approval rate")
        else:
            st.warning("⚠️ Attention Needed - Low approval rate")

with col2:
    # Check flagged items
    if success and stats:
        flagged = stats.get('flagged_checkins', 0)
        if flagged == 0:
            st.success("✅ No items flagged for review")
        elif flagged < 10:
            st.info(f"ℹ️ {flagged} items need review")
        else:
            st.warning(f"⚠️ {flagged} items need review")

with col3:
    # Active sessions
    if success and stats:
        active = stats.get('active_sessions', 0)
        if active > 0:
            st.success(f"🟢 {active} active session(s)")
        else:
            st.info("ℹ️ No active sessions")

# Tips and recommendations
with st.expander("💡 Tips for Instructors"):
    st.markdown("""
    **Monitoring Best Practices:**
    - Check flagged check-ins daily to ensure accurate attendance records
    - Review high-risk check-ins for potential attendance fraud
    - Monitor attendance trends to identify struggling students early
    - Export data regularly for backup and grading purposes

    **When to Take Action:**
    - **High Risk Check-ins**: Investigate distances > 500m or unusual timing
    - **Low Attendance**: Contact students with < 75% attendance rate
    - **Flagged Items**: Review and approve/reject within 24 hours
    - **System Issues**: Report persistent technical problems to IT support

    **Quick Links:**
    - 📚 Go to Courses page to view detailed attendance by course
    - 🎯 Visit Sessions page to monitor specific sessions
    - 📥 Use Reports page to export data for grading
    """)
