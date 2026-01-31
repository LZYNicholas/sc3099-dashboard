"""
SAIV Instructor Dashboard - Main Application
"""

import streamlit as st
import requests

# Page configuration
st.set_page_config(
    page_title="SAIV Instructor Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# API Configuration
API_BASE_URL = "http://localhost:8000/api/v1"

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 1rem;
    }
    .stButton>button {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user' not in st.session_state:
    st.session_state.user = None
if 'token' not in st.session_state:
    st.session_state.token = None


def login(email: str, password: str) -> bool:
    """Authenticate user"""
    try:
        # Backend uses /user/login endpoint
        response = requests.post(
            "http://localhost:8000/user/login",
            json={"email": email, "password": password},
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            user = data.get('user', {})

            # Check role
            if user.get('role') not in ['instructor', 'admin', 'ta']:
                st.error("Access denied. Only instructors, TAs, and admins can access this dashboard.")
                return False

            # Backend returns token in cookie, but we'll use user data for now
            st.session_state.token = "authenticated"  # Token is in cookie
            st.session_state.user = user
            st.session_state.authenticated = True
            return True
        else:
            try:
                error = response.json().get('error', 'Login failed')
            except:
                error = 'Login failed'
            st.error(f"Login failed: {error}")
            return False
    except Exception as e:
        st.error(f"Connection error: {str(e)}")
        return False


def logout():
    """Clear session"""
    st.session_state.authenticated = False
    st.session_state.user = None
    st.session_state.token = None


def login_page():
    """Display login page"""
    st.markdown('<div class="main-header">📊 SAIV Instructor Dashboard</div>', unsafe_allow_html=True)
    st.markdown("Please login with your instructor credentials.")

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        with st.form("login_form"):
            email = st.text_input("Email", placeholder="instructor@example.com")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login", use_container_width=True)

            if submit:
                if email and password:
                    with st.spinner("Authenticating..."):
                        if login(email, password):
                            st.success("Login successful!")
                            st.rerun()
                else:
                    st.warning("Please enter both email and password.")


def main_page():
    """Display main dashboard"""
    # Sidebar
    with st.sidebar:
        st.markdown("### 👤 User Info")
        user = st.session_state.user
        st.write(f"**{user.get('full_name', 'User')}**")
        st.write(f"Role: {user.get('role', 'unknown').title()}")
        st.write(f"Email: {user.get('email', '')}")

        st.markdown("---")

        if st.button("🚪 Logout", use_container_width=True):
            logout()
            st.rerun()

    # Main content
    st.markdown('<div class="main-header">📊 SAIV Instructor Dashboard</div>', unsafe_allow_html=True)

    st.markdown("""
    ### Welcome to the Instructor Dashboard

    Use the sidebar to navigate between pages:

    - **📊 Overview** - View system statistics
    - **📚 Courses** - Course analytics
    - **🎯 Sessions** - Monitor sessions and check-ins
    - **📋 Audit Logs** - View audit trail
    - **📥 Reports** - Export data
    - **➕ Manage** - Create courses and sessions

    ### Quick Start

    1. Go to **➕ Manage** to create a course
    2. Create a session within that course
    3. Enroll students in the course
    4. Set the session to **Active** to allow check-ins
    5. Students can now check in via the frontend at http://localhost:3000
    """)

    # Quick stats
    st.markdown("---")
    st.subheader("📈 Quick Stats")

    try:
        headers = {"Authorization": f"Bearer {st.session_state.token}"}
        response = requests.get(f"{API_BASE_URL}/stats/overview", headers=headers, timeout=10)

        if response.status_code == 200:
            stats = response.json()
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Total Sessions", stats.get('total_sessions', 0))
            with col2:
                st.metric("Active Sessions", stats.get('active_sessions', 0))
            with col3:
                st.metric("Check-ins Today", stats.get('total_checkins_today', 0))
            with col4:
                rate = stats.get('average_attendance_rate', 0) * 100
                st.metric("Avg Attendance", f"{rate:.1f}%")
        else:
            st.info("Statistics will appear once you have courses and sessions.")
    except Exception as e:
        st.warning(f"Could not load statistics: {str(e)}")


def main():
    """Main entry point"""
    if not st.session_state.authenticated:
        login_page()
    else:
        main_page()


if __name__ == "__main__":
    main()
