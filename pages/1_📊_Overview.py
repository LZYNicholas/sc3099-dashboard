"""
SAIV Instructor Dashboard - Overview Page
"""

import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Page configuration
st.set_page_config(page_title="Overview - SAIV Dashboard", page_icon="📊", layout="wide")

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

    st.title("📊 System Overview")
    st.markdown("Real-time statistics and system health monitoring.")

    # Date range selector
    col1, col2 = st.columns([3, 1])
    with col2:
        days = st.selectbox("Time Range", [7, 14, 30, 90], index=0, format_func=lambda x: f"Last {x} days")

    # Fetch overview statistics
    try:
        response = requests.get(
            f"{API_BASE_URL}/stats/overview?days={days}",
            headers=get_headers(),
            timeout=10
        )

        if response.status_code == 200:
            stats = response.json()

            # Key Metrics Row
            st.subheader("📈 Key Metrics")
            col1, col2, col3, col4, col5 = st.columns(5)

            with col1:
                st.metric("Total Courses", stats.get('total_courses', 0))
            with col2:
                st.metric("Total Sessions", stats.get('total_sessions', 0))
            with col3:
                st.metric("Active Sessions", stats.get('active_sessions', 0))
            with col4:
                st.metric("Check-ins Today", stats.get('total_checkins_today', 0))
            with col5:
                rate = stats.get('average_attendance_rate', 0) * 100
                st.metric("Avg Attendance", f"{rate:.1f}%")

            st.markdown("---")

            # Charts Row
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("📅 Daily Check-ins")
                daily_data = stats.get('daily_checkins', [])
                if daily_data:
                    df = pd.DataFrame(daily_data)
                    fig = px.bar(
                        df, x='date', y='count',
                        labels={'date': 'Date', 'count': 'Check-ins'},
                        color_discrete_sequence=['#1f77b4']
                    )
                    fig.update_layout(showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No check-in data available for the selected period.")

            with col2:
                st.subheader("🚨 Risk Distribution")
                risk_data = stats.get('risk_distribution', {})
                if risk_data:
                    labels = list(risk_data.keys())
                    values = list(risk_data.values())
                    colors = {'low': '#28a745', 'medium': '#ffc107', 'high': '#dc3545'}
                    fig = go.Figure(data=[go.Pie(
                        labels=labels,
                        values=values,
                        marker_colors=[colors.get(l, '#6c757d') for l in labels]
                    )])
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No risk data available.")

            st.markdown("---")

            # Recent Activity
            st.subheader("🕐 Recent Activity")
            recent = stats.get('recent_checkins', [])
            if recent:
                df = pd.DataFrame(recent)
                if 'timestamp' in df.columns:
                    df['timestamp'] = pd.to_datetime(df['timestamp']).dt.strftime('%Y-%m-%d %H:%M')
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("No recent activity to display.")

            # Flagged Check-ins
            st.subheader("⚠️ Flagged Check-ins Requiring Review")
            try:
                flagged_response = requests.get(
                    f"{API_BASE_URL}/checkins/flagged?limit=10",
                    headers=get_headers(),
                    timeout=10
                )
                if flagged_response.status_code == 200:
                    flagged = flagged_response.json()
                    if flagged:
                        for item in flagged:
                            with st.expander(f"🔴 {item.get('student_name', 'Unknown')} - {item.get('session_name', 'Session')}"):
                                st.write(f"**Risk Score:** {item.get('risk_score', 0):.2f}")
                                st.write(f"**Flags:** {', '.join(item.get('flags', []))}")
                                st.write(f"**Time:** {item.get('timestamp', 'Unknown')}")
                    else:
                        st.success("No flagged check-ins requiring review.")
                else:
                    st.info("Could not load flagged check-ins.")
            except Exception as e:
                st.warning(f"Could not load flagged check-ins: {str(e)}")

        else:
            st.error("Failed to load statistics. Please try again.")

    except Exception as e:
        st.error(f"Connection error: {str(e)}")
        st.info("Make sure the backend server is running.")


if __name__ == "__main__":
    main()
