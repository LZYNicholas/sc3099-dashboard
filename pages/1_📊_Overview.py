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
    return {"Authorization": f"Bearer {st.session_state.get('access_token', '')}"}

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

            # Check-ins by Hour & Verification Status Row
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("🕐 Check-ins by Hour")
                try:
                    from datetime import date
                    today_str = date.today().isoformat()
                    checkins_response = requests.get(
                        f"{API_BASE_URL}/checkins/",
                        params={"start_date": f"{today_str}T00:00:00Z", "limit": 500},
                        headers=get_headers(),
                        timeout=15
                    )
                    if checkins_response.status_code == 200:
                        checkins_data = checkins_response.json()
                        checkins_list = checkins_data.get('items', []) if isinstance(checkins_data, dict) else checkins_data
                        if checkins_list:
                            ci_df = pd.DataFrame(checkins_list)
                            if 'checked_in_at' in ci_df.columns:
                                ci_df['hour'] = pd.to_datetime(ci_df['checked_in_at']).dt.hour
                            elif 'timestamp' in ci_df.columns:
                                ci_df['hour'] = pd.to_datetime(ci_df['timestamp']).dt.hour
                            else:
                                ci_df['hour'] = 0
                            hourly = ci_df.groupby('hour').size().reset_index(name='count')
                            # Fill missing hours
                            all_hours = pd.DataFrame({'hour': range(24)})
                            hourly = all_hours.merge(hourly, on='hour', how='left').fillna(0)
                            hourly['count'] = hourly['count'].astype(int)
                            hourly['hour_label'] = hourly['hour'].apply(lambda h: f"{h:02d}:00")
                            fig = px.bar(
                                hourly, x='hour_label', y='count',
                                labels={'hour_label': 'Hour', 'count': 'Check-ins'},
                                color_discrete_sequence=['#17becf']
                            )
                            fig.update_layout(showlegend=False, xaxis_tickangle=-45)
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.info("No check-ins today to show hourly distribution.")
                    else:
                        st.info("Could not load check-in data for hourly chart.")
                except Exception as e:
                    st.warning(f"Could not load hourly check-ins: {str(e)}")

            with col2:
                st.subheader("✅ Verification Status")
                try:
                    checkins_response2 = requests.get(
                        f"{API_BASE_URL}/checkins/",
                        params={"limit": 500},
                        headers=get_headers(),
                        timeout=15
                    )
                    if checkins_response2.status_code == 200:
                        checkins_data2 = checkins_response2.json()
                        checkins_list2 = checkins_data2.get('items', []) if isinstance(checkins_data2, dict) else checkins_data2
                        if checkins_list2:
                            status_counts = {}
                            for ci in checkins_list2:
                                s = ci.get('status', 'unknown')
                                status_counts[s] = status_counts.get(s, 0) + 1
                            labels = list(status_counts.keys())
                            values = list(status_counts.values())
                            status_colors = {
                                'approved': '#28a745', 'verified': '#28a745',
                                'flagged': '#ffc107', 'pending': '#6c757d',
                                'rejected': '#dc3545', 'appealed': '#fd7e14'
                            }
                            fig = go.Figure(data=[go.Pie(
                                labels=labels,
                                values=values,
                                marker_colors=[status_colors.get(l, '#adb5bd') for l in labels]
                            )])
                            fig.update_traces(textinfo='label+percent+value')
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.info("No check-in data available for status breakdown.")
                    else:
                        st.info("Could not load verification status data.")
                except Exception as e:
                    st.warning(f"Could not load verification status: {str(e)}")

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
