"""
SAIV Instructor Dashboard - Metrics & System Health Page
Provides operational metrics, risk analytics, and system health monitoring.
"""

import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Page configuration
st.set_page_config(page_title="Metrics - SAIV Dashboard", page_icon="📈", layout="wide")

API_BASE_URL = "http://localhost:8000/api/v1"
FACE_SERVICE_URL = "http://localhost:8001"


def check_auth():
    """Check if user is authenticated"""
    if not st.session_state.get('authenticated', False):
        st.warning("Please login from the main page.")
        st.stop()


def get_headers():
    """Get authorization headers"""
    return {"Authorization": f"Bearer {st.session_state.get('access_token', '')}"}


def check_service_health(url, name, timeout=5):
    """Ping a service and return health status"""
    try:
        response = requests.get(url, timeout=timeout)
        return {
            'name': name,
            'status': 'healthy' if response.status_code < 500 else 'degraded',
            'response_time_ms': int(response.elapsed.total_seconds() * 1000),
            'status_code': response.status_code
        }
    except requests.exceptions.ConnectionError:
        return {'name': name, 'status': 'down', 'response_time_ms': None, 'status_code': None}
    except requests.exceptions.Timeout:
        return {'name': name, 'status': 'timeout', 'response_time_ms': None, 'status_code': None}
    except Exception:
        return {'name': name, 'status': 'unknown', 'response_time_ms': None, 'status_code': None}


def main():
    check_auth()

    st.title("📈 System Metrics & Health")
    st.markdown("Operational metrics, risk analytics, and system health monitoring.")

    # =========================================================================
    # SYSTEM HEALTH STATUS
    # =========================================================================
    st.subheader("🏥 System Health")

    services = [
        (f"{API_BASE_URL}/stats/overview?days=1", "Backend API"),
        (f"{FACE_SERVICE_URL}/docs", "Face Recognition Service"),
    ]

    health_cols = st.columns(len(services))
    for idx, (url, name) in enumerate(services):
        health = check_service_health(url, name)
        with health_cols[idx]:
            if health['status'] == 'healthy':
                st.success(f"🟢 **{name}**: Healthy")
                if health['response_time_ms'] is not None:
                    st.caption(f"Response: {health['response_time_ms']}ms")
            elif health['status'] == 'degraded':
                st.warning(f"🟡 **{name}**: Degraded (HTTP {health['status_code']})")
            elif health['status'] == 'timeout':
                st.error(f"🔴 **{name}**: Timeout")
            else:
                st.error(f"🔴 **{name}**: Unreachable")

    st.markdown("---")

    # =========================================================================
    # KEY PERFORMANCE INDICATORS
    # =========================================================================
    st.subheader("📊 Key Performance Indicators")

    try:
        response = requests.get(
            f"{API_BASE_URL}/stats/overview?days=7",
            headers=get_headers(),
            timeout=10
        )

        if response.status_code == 200:
            stats = response.json()

            col1, col2, col3, col4, col5 = st.columns(5)

            with col1:
                approval_rate = stats.get('approval_rate', 0) * 100
                st.metric("Approval Rate", f"{approval_rate:.1f}%")
            with col2:
                avg_risk = stats.get('average_risk_score', 0)
                st.metric("Avg Risk Score", f"{avg_risk:.3f}")
            with col3:
                st.metric("High-Risk Today", stats.get('high_risk_checkins_today', 0))
            with col4:
                st.metric("Flagged Pending", stats.get('flagged_pending_review', 0))
            with col5:
                st.metric("Check-ins (7d)", stats.get('total_checkins_week', 0))
        else:
            st.warning("Could not load KPI data from backend.")
            stats = {}

    except Exception as e:
        st.error(f"Failed to load metrics: {str(e)}")
        stats = {}

    st.markdown("---")

    # =========================================================================
    # RISK SCORE DISTRIBUTION
    # =========================================================================
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📉 Risk Score Distribution")
        try:
            checkins_response = requests.get(
                f"{API_BASE_URL}/checkins/",
                params={"limit": 500},
                headers=get_headers(),
                timeout=15
            )
            if checkins_response.status_code == 200:
                checkins_data = checkins_response.json()
                checkins_list = checkins_data.get('items', []) if isinstance(checkins_data, dict) else checkins_data
                if checkins_list:
                    risk_scores = [ci.get('risk_score', 0) for ci in checkins_list if ci.get('risk_score') is not None]
                    if risk_scores:
                        df_risk = pd.DataFrame({'risk_score': risk_scores})

                        # Categorize into bands
                        def risk_band(score):
                            if score < 0.3:
                                return 'Low (< 0.3)'
                            elif score < 0.5:
                                return 'Medium (0.3–0.5)'
                            elif score < 0.7:
                                return 'High (0.5–0.7)'
                            else:
                                return 'Critical (≥ 0.7)'

                        df_risk['band'] = df_risk['risk_score'].apply(risk_band)

                        # Histogram
                        fig = px.histogram(
                            df_risk, x='risk_score', nbins=20,
                            labels={'risk_score': 'Risk Score', 'count': 'Number of Check-ins'},
                            color_discrete_sequence=['#636efa']
                        )
                        fig.add_vline(x=0.5, line_dash="dash", line_color="red",
                                      annotation_text="Threshold (0.5)")
                        fig.update_layout(showlegend=False, yaxis_title="Count")
                        st.plotly_chart(fig, use_container_width=True)

                        # Band summary
                        band_counts = df_risk['band'].value_counts().to_dict()
                        bcol1, bcol2, bcol3, bcol4 = st.columns(4)
                        with bcol1:
                            st.metric("🟢 Low", band_counts.get('Low (< 0.3)', 0))
                        with bcol2:
                            st.metric("🟡 Medium", band_counts.get('Medium (0.3–0.5)', 0))
                        with bcol3:
                            st.metric("🟠 High", band_counts.get('High (0.5–0.7)', 0))
                        with bcol4:
                            st.metric("🔴 Critical", band_counts.get('Critical (≥ 0.7)', 0))
                    else:
                        st.info("No risk score data available.")
                else:
                    st.info("No check-in data to analyze.")
            else:
                st.warning("Could not load check-in data for risk analysis.")
        except Exception as e:
            st.warning(f"Could not load risk distribution: {str(e)}")

    # =========================================================================
    # ATTENDANCE RATE TREND
    # =========================================================================
    with col2:
        st.subheader("📈 Attendance Rate Trend")
        if stats:
            trends = stats.get('trends', {})
            attendance_by_day = trends.get('attendance_rate_by_day', [])
            if attendance_by_day:
                df_att = pd.DataFrame(attendance_by_day)
                df_att['rate_pct'] = df_att['rate'] * 100
                fig = px.line(
                    df_att, x='date', y='rate_pct',
                    labels={'date': 'Date', 'rate_pct': 'Attendance Rate (%)'},
                    color_discrete_sequence=['#00cc96'],
                    markers=True
                )
                fig.update_layout(yaxis_range=[0, 100])
                st.plotly_chart(fig, use_container_width=True)
            else:
                # Fall back to daily check-ins trend
                checkins_by_day = trends.get('checkins_by_day', [])
                if checkins_by_day:
                    df_daily = pd.DataFrame(checkins_by_day)
                    fig = px.line(
                        df_daily, x='date', y='count',
                        labels={'date': 'Date', 'count': 'Check-ins'},
                        color_discrete_sequence=['#00cc96'],
                        markers=True
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No trend data available for the selected period.")
        else:
            st.info("Trend data unavailable — backend not reachable.")

    st.markdown("---")

    # =========================================================================
    # HIGH-RISK ALERTS
    # =========================================================================
    st.subheader("🚨 High-Risk Alerts")

    try:
        flagged_response = requests.get(
            f"{API_BASE_URL}/checkins/flagged?limit=20",
            headers=get_headers(),
            timeout=10
        )
        if flagged_response.status_code == 200:
            flagged = flagged_response.json()
            if isinstance(flagged, dict):
                flagged = flagged.get('items', [])

            if flagged:
                st.warning(f"⚠️ {len(flagged)} check-in(s) require review")

                for item in flagged:
                    risk_score = item.get('risk_score', 0)
                    if risk_score >= 0.7:
                        icon = "🔴"
                    elif risk_score >= 0.5:
                        icon = "🟠"
                    else:
                        icon = "🟡"

                    student = item.get('student_name', 'Unknown Student')
                    session = item.get('session_name', 'Unknown Session')
                    timestamp = item.get('checked_in_at', item.get('timestamp', 'N/A'))
                    if isinstance(timestamp, str) and len(timestamp) > 16:
                        timestamp = timestamp[:16]

                    with st.expander(f"{icon} {student} — {session} (Risk: {risk_score:.2f})"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**Status:** {item.get('status', 'N/A')}")
                            st.write(f"**Risk Score:** {risk_score:.3f}")
                            st.write(f"**Time:** {timestamp}")
                        with col2:
                            risk_factors = item.get('risk_factors', [])
                            if risk_factors:
                                st.write("**Risk Factors:**")
                                for rf in risk_factors:
                                    if isinstance(rf, dict):
                                        st.write(f"  - {rf.get('type', 'unknown')} ({rf.get('severity', 'N/A')})")
                                    else:
                                        st.write(f"  - {rf}")
                            else:
                                flags = item.get('flags', [])
                                if flags:
                                    st.write(f"**Flags:** {', '.join(flags)}")
                                else:
                                    st.write("No detailed risk factors available.")

                            if item.get('appeal_reason'):
                                st.write(f"**Appeal:** {item.get('appeal_reason')}")
            else:
                st.success("✅ No high-risk alerts — all check-ins within normal thresholds.")
        else:
            st.info("Could not load flagged check-ins.")
    except Exception as e:
        st.warning(f"Could not load high-risk alerts: {str(e)}")


if __name__ == "__main__":
    main()
