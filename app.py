"""SAIV Instructor Dashboard - Main Application
"""

import streamlit as st
import streamlit.components.v1 as components
import os
import time
from prometheus_client import Counter, Histogram, REGISTRY, start_http_server
from lib.auth_state import (
    API_BASE_URL,
    ALLOWED_DASHBOARD_ROLES,
    clear_auth_state,
    get_auth_headers,
    initialize_auth_state,
    save_auth_state,
)
from lib.response_utils import request_with_retry, response_error, parse_json

_METRICS_STARTED = False


def _get_or_create_counter(name: str, documentation: str, labelnames=()):
    try:
        return Counter(name, documentation, labelnames=labelnames)
    except ValueError:
        return REGISTRY._names_to_collectors[name]


def _get_or_create_histogram(name: str, documentation: str, labelnames=()):
    try:
        return Histogram(name, documentation, labelnames=labelnames)
    except ValueError:
        return REGISTRY._names_to_collectors[name]


LOGIN_ATTEMPTS = _get_or_create_counter('saiv_dashboard_login_attempts_total', 'Total dashboard login attempts')
LOGIN_SUCCESS = _get_or_create_counter('saiv_dashboard_login_success_total', 'Total successful dashboard logins')
LOGIN_FAILURE = _get_or_create_counter('saiv_dashboard_login_failure_total', 'Total failed dashboard logins')
API_REQUESTS = _get_or_create_counter('saiv_dashboard_api_requests_total', 'Dashboard API requests', ['endpoint', 'status'])
API_LATENCY = _get_or_create_histogram('saiv_dashboard_api_request_seconds', 'Dashboard API request latency', ['endpoint'])

# Page configuration
st.set_page_config(
    page_title="SAIV Instructor Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

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

initialize_auth_state()


def ensure_metrics_server() -> None:
    global _METRICS_STARTED
    if _METRICS_STARTED:
        return

    try:
        metrics_port = int(os.getenv('PROM_METRICS_PORT', '9101'))
        start_http_server(metrics_port)
    except Exception:
        # Keep dashboard functional if metrics port is unavailable.
        pass
    finally:
        _METRICS_STARTED = True


def login(email: str, password: str) -> bool:
    """Authenticate user"""
    LOGIN_ATTEMPTS.inc()
    try:
        # Use the shared auth endpoint, then gate dashboard access by role.
        started = time.perf_counter()
        response, error = request_with_retry(
            "POST",
            f"{API_BASE_URL}/auth/login",
            json={"email": email, "password": password},
            timeout=10,
            retries=2,
        )
        if response is None:
            LOGIN_FAILURE.inc()
            st.error(f"Connection error: {error or 'request failed'}")
            return False

        API_LATENCY.labels(endpoint='/auth/login').observe(time.perf_counter() - started)
        API_REQUESTS.labels(endpoint='/auth/login', status=str(response.status_code)).inc()

        if response.status_code == 200:
            data = parse_json(response) or {}
            user = data.get('user', {})

            # Check role
            if user.get('role') not in ALLOWED_DASHBOARD_ROLES:
                LOGIN_FAILURE.inc()
                st.error("Access denied. Only instructors, TAs, and admins can access this dashboard.")
                return False

            # Extract JWT token from response body
            token = data.get('access_token')
            refresh_token = data.get('refresh_token')
            if not token or not refresh_token:
                LOGIN_FAILURE.inc()
                st.error("No authentication token received from server.")
                return False

            save_auth_state(token, refresh_token, user)
            LOGIN_SUCCESS.inc()
            return True
        else:
            LOGIN_FAILURE.inc()
            st.error(f"Login failed: {response_error(response, 'Login failed')}")
            return False
    except Exception as e:
        LOGIN_FAILURE.inc()
        st.error(f"Connection error: {str(e)}")
        return False


def logout():
    """Call backend logout and clear local session."""
    try:
        headers = get_auth_headers()
        request_with_retry(
            "POST",
            f"{API_BASE_URL}/auth/logout",
            headers=headers,
            timeout=8,
            retries=1,
        )
    except Exception:
        pass

    clear_auth_state()


def inject_login_autofill_hints() -> None:
        """Set browser autofill hints for Streamlit login inputs."""
        components.html(
                """
                <script>
                (function () {
                    const apply = () => {
                        const email = window.parent.document.querySelector('input[aria-label="Email"]');
                        const password = window.parent.document.querySelector('input[aria-label="Password"]');

                        if (email) {
                            email.setAttribute('autocomplete', 'username');
                            email.setAttribute('name', 'username');
                            email.setAttribute('type', 'email');
                            email.setAttribute('inputmode', 'email');
                        }

                        if (password) {
                            password.setAttribute('autocomplete', 'current-password');
                            password.setAttribute('name', 'password');
                        }
                    };

                    apply();
                    const observer = new MutationObserver(apply);
                    observer.observe(window.parent.document.body, { childList: true, subtree: true });
                    setTimeout(() => observer.disconnect(), 10000);
                })();
                </script>
                """,
                height=0,
                width=0,
        )


def login_page():
    """Display login page"""
    inject_login_autofill_hints()
    st.markdown('<div class="main-header">SAIV Instructor Dashboard</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        tab1, tab2 = st.tabs(["Login", "Register"])
        
        with tab1:
            st.markdown("Please login with your instructor credentials.")
            with st.form("login_form"):
                email = st.text_input(
                    "Email",
                    placeholder="instructor@example.com",
                    autocomplete="email"
                )
                password = st.text_input(
                    "Password",
                    type="password",
                    autocomplete="current-password"
                )
                submit = st.form_submit_button("Login", use_container_width=True)

                if submit:
                    if email and password:
                        with st.spinner("Authenticating..."):
                            if login(email, password):
                                st.success("Login successful!")
                                st.rerun()
                    else:
                        st.warning("Please enter both email and password.")

        with tab2:
            st.markdown("Register for a new dashboard account.")
            with st.form("register_form"):
                new_name = st.text_input("Full Name")
                new_email = st.text_input("Email", placeholder="instructor@example.com")
                new_password = st.text_input("Password", type="password")
                new_role = st.selectbox("Role", ["instructor", "admin", "ta"])
                submit_register = st.form_submit_button("Register", use_container_width=True)
                
                if submit_register:
                    if not (new_name and new_email and new_password):
                        st.warning("Please fill in all fields.")
                    else:
                        with st.spinner("Creating account..."):
                            try:
                                res, error = request_with_retry(
                                    "POST",
                                    f"{API_BASE_URL}/auth/register",
                                    json={
                                        "email": new_email,
                                        "password": new_password,
                                        "full_name": new_name,
                                        "role": new_role
                                    },
                                    timeout=10,
                                    retries=2,
                                )
                                if res is None:
                                    st.error(f"Connection error: {error or 'request failed'}")
                                    return

                                if res.status_code == 201:
                                    st.success(f"Account for {new_email} created successfully! You can now login.")
                                else:
                                    st.error(f"Registration failed: {response_error(res)}")
                            except Exception as e:
                                st.error(f"Connection error: {e}")


def main_page():
    """Display main dashboard"""
    # Sidebar
    with st.sidebar:
        st.markdown("### User Info")
        user = st.session_state.user
        st.write(f"**{user.get('full_name', 'User')}**")
        st.write(f"Role: {user.get('role', 'unknown').title()}")
        st.write(f"Email: {user.get('email', '')}")

        st.markdown("---")

        if st.button("Logout", use_container_width=True):
            logout()
            st.rerun()

    # Main content
    st.markdown('<div class="main-header">SAIV Instructor Dashboard</div>', unsafe_allow_html=True)

    st.markdown("""
    ### Welcome to the Instructor Dashboard

    Use the sidebar to navigate between pages:

    - **Overview** - View system statistics
    - **Courses** - Course analytics
    - **Sessions** - Monitor sessions and check-ins
    - **Audit Logs** - View audit trail
    - **Reports** - Export data
    - **Manage** - Create courses and sessions
    - **Review Appeals** - Review flagged & appealed check-ins

    ### Quick Start

    1. Go to **Manage** to create a course
    2. Create a session within that course
    3. Enroll students in the course
    4. Set the session to **Active** to allow check-ins
    5. Students can now check in via the frontend at http://localhost:3000
    6. Review any **flagged or appealed** check-ins in the Review Appeals page
    """)

    # Quick stats
    st.markdown("---")
    st.subheader("Quick Stats")

    try:
        headers = get_auth_headers()
        response, error = request_with_retry(
            "GET",
            f"{API_BASE_URL}/stats/overview",
            headers=headers,
            timeout=10,
            retries=2,
        )
        if response is None:
            st.warning(f"Could not load statistics: {error or 'request failed'}")
            return

        if response.status_code == 200:
            stats = parse_json(response) or {}
            col1, col2, col3, col4, col5 = st.columns(5)

            with col1:
                st.metric("Total Sessions", stats.get('total_sessions', 0))
            with col2:
                st.metric("Active Sessions", stats.get('active_sessions', 0))
            with col3:
                st.metric("Check-ins Today", stats.get('total_checkins_today', 0))
            with col4:
                rate = stats.get('average_attendance_rate', 0) * 100
                st.metric("Avg Attendance", f"{rate:.1f}%")
            with col5:
                flagged = stats.get('flagged_pending_review', 0)
                st.metric("⚠️ Pending Review", flagged)
        else:
            st.info("Statistics will appear once you have courses and sessions.")
    except Exception as e:
        st.warning(f"Could not load statistics: {str(e)}")


def main():
    """Main entry point"""
    ensure_metrics_server()

    if not st.session_state.authenticated:
        login_page()
    else:
        main_page()


if __name__ == "__main__":
    main()
