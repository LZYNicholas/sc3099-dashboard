"""SAIV Instructor Dashboard - Profile Page
"""

import streamlit as st

from lib.auth_state import API_BASE_URL, get_auth_headers, require_auth
from lib.response_utils import parse_json, request_with_retry, response_error

st.set_page_config(page_title="Profile - SAIV Dashboard", layout="wide", initial_sidebar_state="expanded")


def main() -> None:
    require_auth()

    current_role = str((st.session_state.get("user") or {}).get("role", "")).strip().lower()
    if current_role not in {"ta", "instructor", "admin"}:
        st.error("Access denied. This page is restricted to TAs, instructors, and admins.")
        st.stop()

    st.title("My Profile")
    st.caption("Manage your dashboard profile details.")

    response, error = request_with_retry(
        "GET",
        f"{API_BASE_URL}/users/me",
        headers=get_auth_headers(),
        timeout=10,
        retries=2,
    )
    if response is None:
        st.error(f"Failed to load profile: {error or 'request failed'}")
        return
    if response.status_code != 200:
        st.error(f"Failed to load profile ({response.status_code}): {response_error(response)}")
        return

    me = parse_json(response) if response is not None else {}
    if not isinstance(me, dict):
        st.error("Failed to load profile data.")
        return

    st.markdown("#### Account")
    c1, c2 = st.columns(2)
    with c1:
        st.text_input("Email", value=str(me.get("email") or ""), disabled=True)
    with c2:
        st.text_input("Role", value=str(me.get("role") or "").title(), disabled=True)

    st.markdown("---")
    with st.form("profile_update_form"):
        full_name = st.text_input("Full Name", value=str(me.get("full_name") or ""))
        submitted = st.form_submit_button("Save Profile", use_container_width=True)
        if submitted:
            payload = {"full_name": full_name.strip()}
            update_response, update_error = request_with_retry(
                "PUT",
                f"{API_BASE_URL}/users/me",
                json=payload,
                headers={**get_auth_headers(), "Content-Type": "application/json"},
                timeout=10,
                retries=2,
            )
            if update_response is None:
                st.error(f"Failed to update profile: {update_error or 'request failed'}")
                return
            if update_response.status_code != 200:
                st.error(f"Failed to update profile ({update_response.status_code}): {response_error(update_response)}")
                return

            updated = parse_json(update_response)
            if isinstance(updated, dict):
                st.session_state.user = {
                    **(st.session_state.get("user") or {}),
                    **updated,
                }
            st.success("Profile updated successfully.")


if __name__ == "__main__":
    main()

