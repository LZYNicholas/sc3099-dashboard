"""
SAIV Dashboard - Session Monitoring Page
Real-time session monitoring and check-in review
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# Page configuration
st.set_page_config(page_title="Sessions - SAIV", page_icon="🎯", layout="wide")

# Check authentication
if not st.session_state.get('authenticated', False):
    st.warning("Please login from the main page to access this section.")
    st.stop()

api_client = st.session_state.api_client

st.title("🎯 Session Monitoring")
st.markdown("Monitor active sessions and review student check-ins in real-time.")

# Refresh button
col1, col2 = st.columns([6, 1])
with col2:
    if st.button("🔄 Refresh"):
        st.rerun()

st.markdown("---")

# Get all sessions
with st.spinner("Loading sessions..."):
    success, sessions_data = api_client.get_sessions()

if not success:
    st.error(f"Failed to load sessions: {sessions_data}")
    st.stop()

sessions = sessions_data.get('items', [])

if not sessions:
    st.info("No sessions found. Create a session to get started.")
    st.stop()

# Session selector
session_options = {
    f"{s.get('course_code', 'N/A')} - {s.get('name', 'Unnamed')} ({s.get('status', 'unknown')})": s
    for s in sessions
}

selected_session_name = st.selectbox(
    "Select Session",
    options=list(session_options.keys()),
    help="Choose a session to view details and check-ins"
)

selected_session = session_options[selected_session_name]
session_id = selected_session.get('id')

st.markdown("---")

# Session Details
st.subheader("📋 Session Details")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"**Course:** {selected_session.get('course_code', 'N/A')}")
    st.markdown(f"**Session:** {selected_session.get('name', 'N/A')}")

with col2:
    status = selected_session.get('status', 'unknown')
    status_colors = {
        'active': '🟢',
        'scheduled': '🔵',
        'closed': '⚫',
        'cancelled': '🔴'
    }
    st.markdown(f"**Status:** {status_colors.get(status, '⚪')} {status.title()}")
    st.markdown(f"**Type:** {selected_session.get('session_type', 'N/A').title()}")

with col3:
    st.markdown(f"**Start:** {selected_session.get('scheduled_start', 'N/A')[:16] if selected_session.get('scheduled_start') else 'N/A'}")
    st.markdown(f"**End:** {selected_session.get('scheduled_end', 'N/A')[:16] if selected_session.get('scheduled_end') else 'N/A'}")

with col4:
    st.markdown(f"**Venue:** {selected_session.get('venue_name', 'N/A')}")
    st.markdown(f"**Check-in Window:** {selected_session.get('checkin_opens_at', 'N/A')[:16] if selected_session.get('checkin_opens_at') else 'N/A'}")

st.markdown("---")

# Session Statistics
st.subheader("📊 Session Statistics")

with st.spinner("Loading session statistics..."):
    success, stats = api_client.get_session_statistics(session_id)

if success:
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Total Enrolled",
            stats.get('total_enrolled', 0),
            help="Number of students enrolled in this course"
        )

    with col2:
        st.metric(
            "Checked In",
            stats.get('checked_in', 0),
            help="Number of students who checked in"
        )

    with col3:
        attendance_rate = stats.get('attendance_rate', 0) * 100
        st.metric(
            "Attendance Rate",
            f"{attendance_rate:.1f}%",
            help="Percentage of enrolled students who checked in"
        )

    with col4:
        avg_risk = stats.get('average_risk_score', 0)
        st.metric(
            "Avg Risk Score",
            f"{avg_risk:.2f}",
            help="Average risk score of check-ins"
        )

    # Status breakdown and risk distribution
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Status Breakdown")
        by_status = stats.get('by_status', {})

        if by_status:
            status_df = pd.DataFrame([
                {"Status": k.title(), "Count": v}
                for k, v in by_status.items()
            ])

            fig = px.pie(
                status_df,
                values='Count',
                names='Status',
                color='Status',
                color_discrete_map={
                    'Approved': '#28a745',
                    'Flagged': '#ffc107',
                    'Rejected': '#dc3545',
                    'Pending': '#6c757d'
                }
            )
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No check-in status data available")

    with col2:
        st.markdown("#### Risk Distribution")
        risk_dist = stats.get('risk_distribution', {})

        if risk_dist:
            risk_df = pd.DataFrame([
                {"Risk Level": "Low (< 0.3)", "Count": risk_dist.get('low', 0)},
                {"Risk Level": "Medium (0.3-0.5)", "Count": risk_dist.get('medium', 0)},
                {"Risk Level": "High (> 0.5)", "Count": risk_dist.get('high', 0)}
            ])

            fig = px.bar(
                risk_df,
                x='Risk Level',
                y='Count',
                color='Risk Level',
                color_discrete_map={
                    'Low (< 0.3)': '#28a745',
                    'Medium (0.3-0.5)': '#ffc107',
                    'High (> 0.5)': '#dc3545'
                }
            )
            fig.update_layout(height=300, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No risk distribution data available")

    # Check-in timeline
    st.markdown("#### Check-in Timeline")
    timeline = stats.get('checkin_timeline', [])

    if timeline:
        timeline_df = pd.DataFrame(timeline)
        fig = px.bar(
            timeline_df,
            x='minute',
            y='count',
            labels={'minute': 'Minutes After Session Start', 'count': 'Check-ins'},
            title='Check-in Distribution Over Time'
        )
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No timeline data available")
else:
    st.warning(f"Could not load session statistics: {stats}")

st.markdown("---")

# Check-in List
st.subheader("👥 Student Check-ins")

with st.spinner("Loading check-ins..."):
    success, checkins = api_client.get_session_checkins(session_id)

if success and checkins:
    # Create DataFrame
    df = pd.DataFrame(checkins)

    # Filter options
    col1, col2 = st.columns(2)
    with col1:
        status_filter = st.multiselect(
            "Filter by Status",
            options=['approved', 'flagged', 'rejected', 'pending'],
            default=[]
        )
    with col2:
        search_term = st.text_input("Search by Student Name or Email")

    # Apply filters
    if status_filter:
        df = df[df['status'].isin(status_filter)]

    if search_term:
        mask = (
            df['student_name'].str.contains(search_term, case=False, na=False) |
            df['student_email'].str.contains(search_term, case=False, na=False)
        )
        df = df[mask]

    # Display table
    if not df.empty:
        display_cols = ['student_name', 'student_email', 'status', 'checked_in_at',
                       'risk_score', 'distance_from_venue_meters', 'liveness_passed']

        # Only include columns that exist
        available_cols = [col for col in display_cols if col in df.columns]
        df_display = df[available_cols].copy()

        # Format columns
        if 'checked_in_at' in df_display.columns:
            df_display['checked_in_at'] = df_display['checked_in_at'].apply(
                lambda x: x[:19] if x else 'N/A'
            )

        if 'risk_score' in df_display.columns:
            df_display['risk_score'] = df_display['risk_score'].apply(
                lambda x: f"{x:.2f}" if x else 'N/A'
            )

        if 'distance_from_venue_meters' in df_display.columns:
            df_display['distance_from_venue_meters'] = df_display['distance_from_venue_meters'].apply(
                lambda x: f"{x:.1f}m" if x else 'N/A'
            )

        # Rename columns for display
        column_names = {
            'student_name': 'Student',
            'student_email': 'Email',
            'status': 'Status',
            'checked_in_at': 'Check-in Time',
            'risk_score': 'Risk Score',
            'distance_from_venue_meters': 'Distance',
            'liveness_passed': 'Liveness'
        }
        df_display.rename(columns=column_names, inplace=True)

        st.dataframe(df_display, use_container_width=True, height=400)
        st.write(f"Showing {len(df_display)} of {len(checkins)} check-ins")
    else:
        st.info("No check-ins match the selected filters")
else:
    st.info("No check-ins recorded for this session yet.")

st.markdown("---")

# Flagged Check-ins Review Section
st.subheader("🚩 Flagged Check-ins Review")

with st.spinner("Loading flagged check-ins..."):
    success, flagged = api_client.get_flagged_checkins(limit=20)

if success and flagged:
    # Filter to this session
    session_flagged = [c for c in flagged if c.get('session_id') == session_id]

    if session_flagged:
        st.warning(f"⚠️ {len(session_flagged)} check-ins require review for this session")

        for checkin in session_flagged:
            with st.expander(f"🚩 {checkin.get('student_name', 'Unknown')} - Risk: {checkin.get('risk_score', 0):.2f}"):
                col1, col2 = st.columns(2)

                with col1:
                    st.write(f"**Student:** {checkin.get('student_name')}")
                    st.write(f"**Email:** {checkin.get('student_email')}")
                    st.write(f"**Checked in:** {checkin.get('checked_in_at', 'N/A')[:19]}")
                    st.write(f"**Status:** {checkin.get('status')}")

                with col2:
                    st.write(f"**Risk Score:** {checkin.get('risk_score', 0):.2f}")
                    st.write("**Risk Factors:**")
                    for factor in checkin.get('risk_factors', []):
                        st.write(f"  - {factor.get('type')}: {factor.get('weight', 0):.2f}")

                if checkin.get('appeal_reason'):
                    st.info(f"**Appeal Reason:** {checkin.get('appeal_reason')}")

                # Review actions
                st.markdown("---")
                col1, col2, col3 = st.columns([3, 1, 1])

                with col1:
                    review_notes = st.text_input(
                        "Review Notes",
                        key=f"review_notes_{checkin['id']}",
                        placeholder="Optional notes for the review"
                    )

                with col2:
                    if st.button("✅ Approve", key=f"approve_{checkin['id']}", type="primary"):
                        success, result = api_client.review_checkin(
                            checkin['id'], 'approved', review_notes
                        )
                        if success:
                            st.success("Approved!")
                            st.rerun()
                        else:
                            st.error(f"Failed: {result}")

                with col3:
                    if st.button("❌ Reject", key=f"reject_{checkin['id']}"):
                        success, result = api_client.review_checkin(
                            checkin['id'], 'rejected', review_notes
                        )
                        if success:
                            st.success("Rejected!")
                            st.rerun()
                        else:
                            st.error(f"Failed: {result}")
    else:
        st.success("✅ No flagged check-ins for this session!")
else:
    st.success("✅ No flagged check-ins requiring review!")

# Export button
st.markdown("---")
st.subheader("📥 Export Session Data")

col1, col2 = st.columns(2)

with col1:
    export_format = st.selectbox("Export Format", options=["csv", "json"])

with col2:
    if st.button("📥 Download Session Data"):
        with st.spinner("Generating export..."):
            success, data = api_client.export_session_data(session_id, export_format)

            if success:
                file_ext = export_format
                mime_type = "text/csv" if export_format == "csv" else "application/json"

                st.download_button(
                    label=f"Download {export_format.upper()}",
                    data=data,
                    file_name=f"session_{session_id}_{datetime.now().strftime('%Y%m%d')}.{file_ext}",
                    mime=mime_type
                )
            else:
                st.error(f"Export failed: {data}")
