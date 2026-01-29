"""
SAIV Instructor Dashboard - Main Application
Streamlit-based dashboard for monitoring attendance and analytics
"""

import streamlit as st
from lib.api_client import APIClient
import time

# Page configuration
st.set_page_config(
    page_title="SAIV Instructor Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 1rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .success-badge {
        background-color: #d4edda;
        color: #155724;
        padding: 0.25rem 0.5rem;
        border-radius: 0.25rem;
        font-weight: bold;
    }
    .warning-badge {
        background-color: #fff3cd;
        color: #856404;
        padding: 0.25rem 0.5rem;
        border-radius: 0.25rem;
        font-weight: bold;
    }
    .danger-badge {
        background-color: #f8d7da;
        color: #721c24;
        padding: 0.25rem 0.5rem;
        border-radius: 0.25rem;
        font-weight: bold;
    }
    .info-badge {
        background-color: #d1ecf1;
        color: #0c5460;
        padding: 0.25rem 0.5rem;
        border-radius: 0.25rem;
        font-weight: bold;
    }
    .stButton>button {
        width: 100%;
    }
    div[data-testid="stSidebarNav"] {
        padding-top: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'api_client' not in st.session_state:
    st.session_state.api_client = None
if 'user' not in st.session_state:
    st.session_state.user = None
if 'token' not in st.session_state:
    st.session_state.token = None

def login_page():
    """Display login page"""
    st.markdown('<div class="main-header">SAIV Instructor Dashboard</div>', unsafe_allow_html=True)
    st.markdown("### Login")
    st.markdown("Please login with your instructor credentials to access the dashboard.")

    with st.form("login_form"):
        email = st.text_input("Email", placeholder="instructor@example.com")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")

        if submit:
            if not email or not password:
                st.error("Please enter both email and password")
                return

            with st.spinner("Authenticating..."):
                api_client = APIClient()
                success, result = api_client.login(email, password)

                if success:
                    user = result.get('user', {})
                    role = user.get('role', '')

                    # Check if user is instructor or admin
                    if role not in ['instructor', 'admin']:
                        st.error("Access denied. This dashboard is only available to instructors and administrators.")
                        return

                    # Set session state
                    st.session_state.authenticated = True
                    st.session_state.api_client = api_client
                    st.session_state.user = user
                    st.session_state.token = result.get('access_token')

                    st.success(f"Welcome, {user.get('full_name', email)}!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"Login failed: {result}")

def main_app():
    """Display main application after authentication"""
    # Sidebar
    with st.sidebar:
        st.markdown("### User Info")
        user = st.session_state.user
        st.write(f"**Name:** {user.get('full_name', 'N/A')}")
        st.write(f"**Email:** {user.get('email', 'N/A')}")
        st.write(f"**Role:** {user.get('role', 'N/A').title()}")

        st.markdown("---")

        if st.button("Logout", type="primary"):
            # Clear session state
            st.session_state.authenticated = False
            st.session_state.api_client = None
            st.session_state.user = None
            st.session_state.token = None
            st.rerun()

    # Main content
    st.markdown('<div class="main-header">SAIV Instructor Dashboard</div>', unsafe_allow_html=True)

    st.markdown("""
    ### Welcome to the Student Attendance & Identity Verification Dashboard

    This dashboard provides comprehensive tools for monitoring attendance, reviewing check-ins,
    and analyzing course analytics.

    **Available Features:**
    - 📊 **Overview**: System-wide statistics and recent activity
    - 📚 **Courses**: Course-level attendance analytics and trends
    - 🎯 **Sessions**: Real-time session monitoring and check-in review
    - 📋 **Audit Logs**: Complete audit trail with filtering and search
    - 📥 **Reports**: Export data for grading and record-keeping

    **Getting Started:**
    Use the sidebar navigation to access different sections of the dashboard.
    Each page provides specific tools and visualizations for monitoring and analysis.
    """)

    # Quick stats
    st.markdown("### Quick Stats")

    with st.spinner("Loading statistics..."):
        api_client = st.session_state.api_client
        success, stats = api_client.get_overview_statistics()

        if success:
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
                    f"{approval_rate:.1f}%",
                    help="Percentage of check-ins approved"
                )

            with col4:
                st.metric(
                    "Active Sessions",
                    stats.get('active_sessions', 0),
                    help="Currently active sessions"
                )
        else:
            st.error(f"Failed to load statistics: {stats}")

    # Getting started guide
    with st.expander("📖 Quick Start Guide"):
        st.markdown("""
        **Monitoring Attendance:**
        1. Navigate to **Courses** to view course-level attendance
        2. Select a course to see detailed attendance breakdown
        3. Identify students with low attendance

        **Reviewing Check-ins:**
        1. Go to **Sessions** page
        2. Select a session to review
        3. Check flagged check-ins for potential issues
        4. Review distance and timing anomalies

        **Exporting Data:**
        1. Visit **Reports** page
        2. Select the data type to export
        3. Choose date range and format
        4. Download CSV or JSON files

        **Audit Trail:**
        1. Access **Audit Logs** page
        2. Filter by date, user, or action
        3. Search for specific events
        4. Export filtered logs for compliance
        """)

def main():
    """Main application entry point"""
    if not st.session_state.authenticated:
        login_page()
    else:
        main_app()

if __name__ == "__main__":
    main()
