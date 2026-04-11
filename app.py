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
from lib.ui_theme import apply_theme
from lib.ui_components import add_component_css, hero, section_header
from lib.response_utils import request_with_retry, response_error, parse_json, friendly_error

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
apply_theme()
add_component_css()

st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #0f6fb2;
        margin-bottom: 1rem;
    }
    .stButton>button {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

initialize_auth_state()

def normalize_invalid_path() -> None:
    """Recover from stale '/undefined' route that can blank the app."""
    components.html(
        """
        <script>
        (function () {
          try {
            const path = window.parent.location.pathname || "";
            if (path === "/undefined") {
              window.parent.history.replaceState({}, "", "/");
              window.parent.location.reload();
            }
          } catch (e) {
            // no-op
          }
        })();
        </script>
        """,
        height=0,
        width=0,
    )


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
            st.error(friendly_error(error, "We couldn't connect right now. Please try again."))
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
            st.error(f"Login failed: {response_error(response, 'Unable to sign in right now.')}")
            return False
    except Exception as e:
        LOGIN_FAILURE.inc()
        st.error(friendly_error(e, "We couldn't connect right now. Please try again."))
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
    hero(
        "SAIV Dashboard",
        "Attendance operations, risk reviews, and reporting in one workspace.",
        eyebrow="Secure Access",
    )

    tab1, tab2 = st.tabs(["Sign In", "Create Account"])

    with tab1:
        section_header("Sign In", "Use your instructor, TA, or admin account.")
        with st.form("login_form"):
            email = st.text_input("Email", placeholder="instructor@example.com", autocomplete="email")
            password = st.text_input("Password", type="password", autocomplete="current-password")
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
        section_header("Register", "Create a dashboard account with role-based access.")
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
                                    "role": new_role,
                                },
                                timeout=10,
                                retries=2,
                            )
                            if res is None:
                                st.error(friendly_error(error, "We couldn't connect right now. Please try again."))
                                return
                            if res.status_code == 201:
                                st.success(f"Account for {new_email} created successfully! You can now login.")
                            else:
                                st.error(f"Registration failed: {response_error(res, 'Unable to create account right now.')}")
                        except Exception as e:
                            st.error(friendly_error(e, "We couldn't connect right now. Please try again."))

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

    hero(
        f"Welcome back, {user.get('full_name', 'User')}",
        "Choose a workflow below to jump straight into operations.",
        eyebrow="Dashboard Home",
    )

    c1, c2, c3 = st.columns(3, gap="small")
    with c1:
        if st.button("Manage Courses", use_container_width=True, key="home_manage"):
            st.switch_page("pages/2_Manage_Course_Session_Enrollments_Devices.py")
    with c2:
        if st.button("Review Appeals", use_container_width=True, key="home_review"):
            st.switch_page("pages/6_Reveal_Appeals.py")
    with c3:
        if st.button("Generate Reports", use_container_width=True, key="home_reports"):
            st.switch_page("pages/7_Reports.py")

    d1, d2 = st.columns(2, gap="medium")
    with d1:
        st.markdown(
            """
            <div class="ui-card">
              <h4>Operational Control</h4>
              <p>Create courses and sessions, manage attendance windows, and keep class operations running smoothly.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with d2:
        st.markdown(
            """
            <div class="ui-card">
              <h4>Risk & Compliance</h4>
              <p>Track risk indicators, resolve flagged submissions, and export evidence-ready attendance reports.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Quick stats
    st.markdown("---")
    section_header("Live Snapshot", "Current platform summary for your scope.")

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
            st.warning(friendly_error(error, "Couldn't load statistics right now."))
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
                st.metric("Pending Review", flagged)
        else:
            st.info("Statistics will appear once you have courses and sessions.")
    except Exception as e:
        st.warning(friendly_error(e, "Couldn't load statistics right now."))

def main():
    """Main entry point"""
    normalize_invalid_path()
    ensure_metrics_server()

    if not st.session_state.authenticated:
        login_page()
    else:
        st.switch_page("pages/1_Overview.py")


if __name__ == "__main__":
    main()

