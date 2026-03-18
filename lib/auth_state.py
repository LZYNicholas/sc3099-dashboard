import base64
import json
import time
import os
import requests
import streamlit as st
from typing import Any, Dict, Optional, Tuple
from uuid import uuid4


def _resolve_api_base_url() -> str:
    configured = os.getenv('API_BASE_URL')
    if configured:
        return configured

    # In Docker, localhost points to the dashboard container itself.
    if os.path.exists('/.dockerenv'):
        return 'http://backend:8000/api/v1'

    return 'http://localhost:8000/api/v1'


API_BASE_URL = _resolve_api_base_url()
ALLOWED_DASHBOARD_ROLES = {"instructor", "admin", "ta"}
_AUTH_STORE: Dict[str, Dict[str, Any]] = {}


def _ensure_defaults() -> None:
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user' not in st.session_state:
        st.session_state.user = None
    if 'access_token' not in st.session_state:
        st.session_state.access_token = None
    if 'refresh_token' not in st.session_state:
        st.session_state.refresh_token = None
    if 'auth_sid' not in st.session_state:
        st.session_state.auth_sid = None


def _get_query_sid() -> Optional[str]:
    sid = st.query_params.get("sid")
    if isinstance(sid, list):
        return sid[0] if sid else None
    return sid


def _set_query_sid(sid: Optional[str]) -> None:
    # Never expose session identifiers in URL query params.
    if "sid" in st.query_params:
        del st.query_params["sid"]


def _decode_jwt_payload(token: str) -> Dict[str, Any]:
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return {}
        payload = parts[1]
        padding = '=' * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload + padding)
        data = json.loads(decoded.decode('utf-8'))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _is_token_expiring_soon(token: Optional[str], skew_seconds: int = 120) -> bool:
    if not token:
        return True
    payload = _decode_jwt_payload(token)
    exp = payload.get('exp')
    if not isinstance(exp, (int, float)):
        return True
    return exp <= time.time() + skew_seconds


def _fetch_me(token: str) -> Tuple[bool, Any, Optional[int]]:
    try:
        response = requests.get(
            f"{API_BASE_URL}/users/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        if response.status_code != 200:
            return False, None, response.status_code
        return True, response.json(), response.status_code
    except Exception:
        return False, None, None


def _refresh_tokens(refresh_token: Optional[str]) -> Tuple[bool, Optional[str], Optional[str], Optional[Dict[str, Any]]]:
    if not refresh_token:
        return False, None, None, None

    try:
        response = requests.post(
            f"{API_BASE_URL}/auth/refresh",
            cookies={"refresh_token": refresh_token},
            timeout=10
        )
        if response.status_code != 200:
            return False, None, None, None

        data = response.json()
        access_token = data.get('access_token')
        next_refresh_token = data.get('refresh_token') or refresh_token
        user = data.get('user')
        if not access_token or not user:
            return False, None, None, None

        return True, access_token, next_refresh_token, user
    except Exception:
        return False, None, None, None


def _apply_auth_state(sid: str, access_token: str, refresh_token: Optional[str], user: Dict[str, Any]) -> None:
    _AUTH_STORE[sid] = {
        "token": access_token,
        "refresh_token": refresh_token,
        "user": user,
    }
    st.session_state.auth_sid = sid
    st.session_state.access_token = access_token
    st.session_state.refresh_token = refresh_token
    st.session_state.user = user
    st.session_state.authenticated = True
    _set_query_sid(sid)


def _restore_from_store() -> None:
    sid = st.session_state.get('auth_sid') or _get_query_sid()
    if not sid:
        return

    auth_state = _AUTH_STORE.get(sid)
    if not auth_state:
        return

    access_token = auth_state.get('token')
    refresh_token = auth_state.get('refresh_token')
    cached_user = auth_state.get('user') or {}

    if _is_token_expiring_soon(access_token):
        refreshed, access_token, refresh_token, refreshed_user = _refresh_tokens(refresh_token)
        if refreshed and refreshed_user:
            role = refreshed_user.get('role')
            if role not in ALLOWED_DASHBOARD_ROLES:
                clear_auth_state()
                return
            _apply_auth_state(sid, access_token, refresh_token, refreshed_user)
            return

    if access_token:
        success, user, status_code = _fetch_me(access_token)
        if success and user:
            role = user.get('role')
            if role not in ALLOWED_DASHBOARD_ROLES:
                clear_auth_state()
                return
            _apply_auth_state(sid, access_token, refresh_token, user)
            return

        if status_code == 401:
            refreshed, next_access_token, next_refresh_token, refreshed_user = _refresh_tokens(refresh_token)
            if refreshed and next_access_token and refreshed_user:
                role = refreshed_user.get('role')
                if role not in ALLOWED_DASHBOARD_ROLES:
                    clear_auth_state()
                    return
                _apply_auth_state(sid, next_access_token, next_refresh_token, refreshed_user)
                return

    if cached_user and access_token:
        role = cached_user.get('role')
        if role in ALLOWED_DASHBOARD_ROLES:
            _apply_auth_state(sid, access_token, refresh_token, cached_user)
            return


def initialize_auth_state() -> None:
    _ensure_defaults()

    if "token" in st.query_params:
        del st.query_params["token"]
    if "sid" in st.query_params:
        del st.query_params["sid"]

    if st.session_state.get('authenticated') and st.session_state.get('access_token'):
        sid = st.session_state.get('auth_sid') or _get_query_sid() or uuid4().hex
        access_token = st.session_state.get('access_token')
        refresh_token = st.session_state.get('refresh_token')
        user = st.session_state.get('user') or {}

        if _is_token_expiring_soon(access_token):
            refreshed, next_access_token, next_refresh_token, refreshed_user = _refresh_tokens(refresh_token)
            if refreshed and next_access_token and refreshed_user:
                role = refreshed_user.get('role')
                if role not in ALLOWED_DASHBOARD_ROLES:
                    clear_auth_state()
                    return
                _apply_auth_state(sid, next_access_token, next_refresh_token, refreshed_user)
                return

        if user and user.get('role') in ALLOWED_DASHBOARD_ROLES:
            _apply_auth_state(sid, access_token, refresh_token, user)
            return

    _restore_from_store()


def save_auth_state(access_token: str, refresh_token: Optional[str], user: Dict[str, Any]) -> None:
    sid = st.session_state.get('auth_sid') or uuid4().hex
    _apply_auth_state(sid, access_token, refresh_token, user)


def clear_auth_state() -> None:
    sid = st.session_state.get('auth_sid')
    if sid and sid in _AUTH_STORE:
        del _AUTH_STORE[sid]

    st.session_state.authenticated = False
    st.session_state.user = None
    st.session_state.access_token = None
    st.session_state.refresh_token = None
    st.session_state.auth_sid = None
    _set_query_sid(None)


def require_auth() -> None:
    initialize_auth_state()
    if not st.session_state.get('authenticated', False):
        st.warning("Please login from the main page.")
        st.stop()


def get_auth_headers() -> Dict[str, str]:
    initialize_auth_state()
    token = st.session_state.get('access_token', '')
    return {"Authorization": f"Bearer {token}"}
