"""SAIV Instructor Dashboard - Overview Page
"""

import streamlit as st
import streamlit.components.v1 as components
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from lib.auth_state import API_BASE_URL, get_auth_headers, require_auth
from lib.response_utils import request_with_retry, response_error, parse_json, friendly_error
from lib.time_utils import format_sgt
from lib.ui_theme import apply_theme
from lib.ui_components import add_component_css, hero, section_header
try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

# Page configuration
st.set_page_config(page_title="Overview - SAIV Dashboard", layout="wide", initial_sidebar_state="expanded")
apply_theme()
add_component_css()

def get_headers():
    return get_auth_headers()


AUTO_REFRESH_SECONDS = 30


def _inject_auto_refresh(seconds: int) -> None:
    if seconds <= 0:
        return
    interval_ms = int(seconds * 1000)
    if st_autorefresh is not None:
        st_autorefresh(interval=interval_ms, key=f"overview_autorefresh_{seconds}")
        return
    st.caption("Auto-refresh dependency missing; polling is temporarily disabled on this page.")


def main():
    require_auth()
    current_role = str((st.session_state.get('user') or {}).get('role', '')).strip().lower()
    if current_role not in {"instructor", "admin"}:
        st.error("Access denied. This page is restricted to instructors and admins.")
        st.stop()

    hero(
        "System Overview",
        "Command snapshot for attendance operations, risk posture, and recent activity.",
        eyebrow="Operations",
    )
    _inject_auto_refresh(AUTO_REFRESH_SECONDS)
    st.caption(f"Auto-refresh enabled every {AUTO_REFRESH_SECONDS}s")

    # Date range selector
    col1, col2 = st.columns([3, 1])
    with col2:
        days = st.selectbox("Time Range", [7, 14, 30, 90], index=0, format_func=lambda x: f"Last {x} days")

    # Fetch overview statistics
    try:
        response, error = request_with_retry(
            "GET",
            f"{API_BASE_URL}/stats/overview?days={days}",
            headers=get_headers(),
            timeout=10,
            retries=2,
        )
        if response is None:
            st.error(friendly_error(error, "We couldn't connect right now. Please try again."))
            st.info("Make sure the backend server is running.")
            return

        if response.status_code == 200:
            stats = parse_json(response) or {}

            # Key Metrics Row
            section_header("Key Metrics")
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
                rate = float(stats.get('approval_rate', 0) or 0) * 100
                st.metric("Approval Rate", f"{rate:.1f}%")
            with col6:
                st.metric("Flagged (Pending)", stats.get('flagged_pending_review', 0))

            st.markdown("---")
            tab_activity, tab_ops, tab_risk = st.tabs(["Recent Activity", "Operations", "Risk & Quality"])

            with tab_activity:
                section_header("Recent Activity Feed")
                recent = stats.get('recent_checkins', [])
                if recent:
                    df = pd.DataFrame(recent)
                    if 'timestamp' in df.columns:
                        df['timestamp'] = df['timestamp'].apply(lambda v: format_sgt(v, "%Y-%m-%d %H:%M SGT"))
                    st.dataframe(df, use_container_width=True, hide_index=True)

                    st.markdown("##### Flagged Check-ins")
                    flagged_statuses = {"flagged"}
                    flagged_df = df[
                        df.get("status", pd.Series(dtype=str))
                        .astype(str)
                        .str.lower()
                        .isin(flagged_statuses)
                    ].copy()

                    if not flagged_df.empty:
                        preferred_cols = [
                            "status",
                            "student_name",
                            "session_name",
                            "course_code",
                            "risk_score",
                            "timestamp",
                        ]
                        available_cols = [c for c in preferred_cols if c in flagged_df.columns]
                        display_df = flagged_df[available_cols] if available_cols else flagged_df
                        st.dataframe(display_df, use_container_width=True, hide_index=True)
                        if st.button(
                            "Review Flagged Check-ins",
                            key="overview_review_flagged",
                            use_container_width=True,
                        ):
                            st.switch_page("pages/6_Reveal_Appeals.py")
                    else:
                        st.info("No flagged check-ins in the recent feed.")
                else:
                    st.info("No recent activity to display.")

            with tab_ops:
                section_header("Attendance Flow", "Volume trend and consistency over the selected window.")
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("Daily Check-ins")
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
                    st.subheader("3-Day Movement")
                    daily_data = stats.get('trends', {}).get('checkins_by_day', [])
                    if daily_data:
                        trend_df = pd.DataFrame(daily_data)
                        trend_df['date'] = pd.to_datetime(trend_df['date'])
                        trend_df = trend_df.sort_values('date')
                        trend_df['count'] = trend_df['count'].astype(int)
                        trend_df['ma_3'] = trend_df['count'].rolling(window=3, min_periods=1).mean()
                        fig, ax = plt.subplots(figsize=(6, 3))
                        ax.plot(trend_df['date'], trend_df['count'], marker='o', linewidth=1.8, label='Daily')
                        ax.plot(trend_df['date'], trend_df['ma_3'], linestyle='--', linewidth=2, label='3-day MA')
                        ax.set_xlabel('Date')
                        ax.set_ylabel('Check-ins')
                        ax.grid(alpha=0.25)
                        ax.legend(loc='upper left', frameon=False)
                        fig.autofmt_xdate()
                        st.pyplot(fig, clear_figure=True)
                    else:
                        st.info("Not enough trend data for movement chart.")

            with tab_risk:
                section_header("Risk Posture", "Distribution and score shape from recent verification results.")
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("Risk Distribution")
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
                with col2:
                    st.subheader("Risk Score Histogram")
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


        else:
            st.error(response_error(response, "Couldn't load statistics right now."))

    except Exception as e:
        st.error(friendly_error(e, "Couldn't load statistics right now."))
        st.info("Make sure the backend server is running.")


if __name__ == "__main__":
    main()

