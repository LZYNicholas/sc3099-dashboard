import requests
import streamlit as st
from typing import Any, Dict, Optional, Tuple
from uuid import uuid4

API_BASE_URL = "http://localhost:8000/api/v1"
ALLOWED_DASHBOARD_ROLES = {"instructor", "admin", "ta"}
_AUTH_STORE: Dict[str, Dict[str, Any]] = {}


def _ensure_defaults() -> None:
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user' not in st.session_state:
        st.session_state.user = None
    if 'access_token' not in st.session_state:
        st.session_state.access_token = None
    if 'auth_sid' not in st.session_state:
        st.session_state.auth_sid = None


def _get_query_sid() -> Optional[str]:
    sid = st.query_params.get("sid")
    if isinstance(sid, list):
        return sid[0] if sid else None
    return sid


def _set_query_sid(sid: Optional[str]) -> None:
    if sid:
        st.query_params["sid"] = sid
        return

    if "sid" in st.query_params:
        del st.query_params["sid"]


def _fetch_me(token: str) -> Tuple[bool, Any]:
    try:
        response = requests.get(
            f"{API_BASE_URL}/users/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        if response.status_code != 200:
            return False, None
        return True, response.json()
    except Exception:
        return False, None


def initialize_auth_state() -> None:
    _ensure_defaults()

    if "token" in st.query_params:
        del st.query_params["token"]

    if st.session_state.get('authenticated') and st.session_state.get('access_token'):
        return

    sid = _get_query_sid()
    if not sid:
        return

    auth_state = _AUTH_STORE.get(sid)
    token = auth_state.get('token') if auth_state else None
    if not token:
        return

    success, user = _fetch_me(token)
    if not success:
        clear_auth_state()
        return

    role = (user or {}).get('role')
    if role not in ALLOWED_DASHBOARD_ROLES:
        clear_auth_state()
        return

    st.session_state.auth_sid = sid
    st.session_state.access_token = token
    st.session_state.user = user
    st.session_state.authenticated = True


def save_auth_state(token: str, user: Dict[str, Any]) -> None:
    sid = st.session_state.get('auth_sid') or uuid4().hex
    _AUTH_STORE[sid] = {"token": token, "user": user}
    st.session_state.auth_sid = sid
    st.session_state.access_token = token
    st.session_state.user = user
    st.session_state.authenticated = True
    _set_query_sid(sid)


def clear_auth_state() -> None:
    sid = st.session_state.get('auth_sid')
    if sid and sid in _AUTH_STORE:
        del _AUTH_STORE[sid]

    st.session_state.authenticated = False
    st.session_state.user = None
    st.session_state.access_token = None
    st.session_state.auth_sid = None
    _set_query_sid(None)


def require_auth() -> None:
    initialize_auth_state()
    if not st.session_state.get('authenticated', False):
        st.warning("Please login from the main page.")
        st.stop()


def get_auth_headers() -> Dict[str, str]:
    token = st.session_state.get('access_token', '')
    return {"Authorization": f"Bearer {token}"}
