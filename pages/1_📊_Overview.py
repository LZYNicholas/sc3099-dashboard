"""
SAIV Instructor Dashboard - Overview Page
"""

import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from lib.auth_state import API_BASE_URL, get_auth_headers, require_auth
from lib.response_utils import extract_items

# Page configuration
st.set_page_config(page_title="Overview - SAIV Dashboard", page_icon="📊", layout="wide")

def get_headers():
    return get_auth_headers()

def main():
    require_auth()

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
            col1, col2, col3, col4, col5, col6 = st.columns(6)

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
            with col6:
                st.metric("Flagged (Pending)", stats.get('flagged_pending_review', 0))

            st.markdown("---")

            # Charts Row
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("📅 Daily Check-ins")
                daily_data = stats.get('trends', {}).get('checkins_by_day', [])
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

            # Advanced analytics (Plotly + Matplotlib)
            st.subheader("🧠 Advanced Analytics")
            col1, col2 = st.columns(2)

            with col1:
                st.caption("Daily check-ins with 3-day moving average (Matplotlib)")
                daily_data = stats.get('trends', {}).get('checkins_by_day', [])
                if daily_data:
                    trend_df = pd.DataFrame(daily_data)
                    trend_df['date'] = pd.to_datetime(trend_df['date'])
                    trend_df = trend_df.sort_values('date')
                    trend_df['count'] = trend_df['count'].astype(int)
                    trend_df['ma_3'] = trend_df['count'].rolling(window=3, min_periods=1).mean()

                    fig, ax = plt.subplots(figsize=(6, 3))
                    ax.plot(trend_df['date'], trend_df['count'], marker='o', linewidth=1.8, label='Daily check-ins')
                    ax.plot(trend_df['date'], trend_df['ma_3'], linestyle='--', linewidth=2, label='3-day MA')
                    ax.set_xlabel('Date')
                    ax.set_ylabel('Check-ins')
                    ax.grid(alpha=0.25)
                    ax.legend(loc='upper left', frameon=False)
                    fig.autofmt_xdate()
                    st.pyplot(fig, clear_figure=True)
                else:
                    st.info("Not enough trend data for moving average chart.")

            with col2:
                st.caption("Risk score histogram from recent check-ins")
                recent = stats.get('recent_checkins', [])
                if recent:
                    recent_df = pd.DataFrame(recent)
                    if 'risk_score' in recent_df.columns:
                        risk_series = pd.to_numeric(recent_df['risk_score'], errors='coerce').dropna()
                        if not risk_series.empty:
                            fig = px.histogram(
                                risk_series,
                                nbins=10,
                                labels={'value': 'Risk Score', 'count': 'Frequency'},
                                color_discrete_sequence=['#ef4444']
                            )
                            fig.update_layout(showlegend=False, margin=dict(l=20, r=20, t=20, b=20))
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.info("No recent risk scores available yet.")
                    else:
                        st.info("Risk scores are not available in recent check-ins.")
                else:
                    st.info("No recent check-ins to analyze.")

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
                    flagged = extract_items(flagged_response.json())
                    if flagged:
                        for item in flagged:
                            if not isinstance(item, dict):
                                continue

                            student_name = item.get('student_name', 'Unknown')
                            session_name = item.get('session_name', 'Session')
                            risk_score = float(item.get('risk_score') or 0)
                            checked_in_at = item.get('checked_in_at') or item.get('timestamp') or 'Unknown'

                            raw_flags = item.get('flags')
                            if isinstance(raw_flags, list):
                                flags = [str(f) for f in raw_flags if f]
                            else:
                                risk_factors = item.get('risk_factors')
                                if isinstance(risk_factors, list):
                                    flags = [
                                        str(f.get('type'))
                                        for f in risk_factors
                                        if isinstance(f, dict) and f.get('type')
                                    ]
                                else:
                                    flags = []

                            with st.expander(f"🔴 {student_name} - {session_name}"):
                                st.write(f"**Risk Score:** {risk_score:.2f}")
                                st.write(f"**Flags:** {', '.join(flags) if flags else 'N/A'}")
                                st.write(f"**Time:** {checked_in_at}")
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
