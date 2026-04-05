"""SAIV Instructor Dashboard - User Management Page (Admin Only)
"""

import streamlit as st
import requests
import pandas as pd
from lib.auth_state import API_BASE_URL, get_auth_headers, require_auth
from lib.response_utils import extract_items

st.set_page_config(page_title="User Management - SAIV Dashboard", layout="wide")


def get_headers():
    return get_auth_headers()


def response_error(response: requests.Response | None, fallback: str = "Unknown error") -> str:
    if response is None:
        return "Connection error"
    try:
        payload = response.json()
    except Exception:
        payload = None
    if isinstance(payload, dict):
        detail = payload.get("detail") or payload.get("message") or payload.get("error")
        if detail:
            return str(detail)
    text = (response.text or "").strip() if hasattr(response, "text") else ""
    return text or fallback


def main():
    require_auth()

    user = st.session_state.get("user", {})
    if user.get("role") != "admin":
        st.error("Access denied. This page is restricted to admins.")
        st.stop()

    st.title("User Management")
    st.markdown("View and manage system users.")

    try:
        response = requests.get(
            f"{API_BASE_URL}/users/",
            headers=get_headers(),
            timeout=15,
        )

        if response.status_code == 200:
            users = extract_items(response.json())

            if not users:
                st.info("No users found.")
                return

            # Summary metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Users", len(users))
            with col2:
                students = sum(1 for u in users if u.get("role") == "student")
                st.metric("Students", students)
            with col3:
                instructors = sum(1 for u in users if u.get("role") in ("instructor", "ta"))
                st.metric("Instructors / TAs", instructors)
            with col4:
                admins = sum(1 for u in users if u.get("role") == "admin")
                st.metric("Admins", admins)

            st.markdown("---")

            # Filters
            col1, col2 = st.columns(2)
            with col1:
                role_filter = st.selectbox(
                    "Filter by Role",
                    options=["All", "student", "instructor", "ta", "admin"],
                )
            with col2:
                search = st.text_input("Search by name or email")

            filtered = users
            if role_filter != "All":
                filtered = [u for u in filtered if u.get("role") == role_filter]
            if search:
                q = search.lower()
                filtered = [
                    u for u in filtered
                    if q in u.get("full_name", "").lower() or q in u.get("email", "").lower()
                ]

            # Users table
            if filtered:
                display = []
                for u in filtered:
                    display.append({
                        "ID": u.get("id", "N/A"),
                        "Name": u.get("full_name", "N/A"),
                        "Email": u.get("email", "N/A"),
                        "Role": u.get("role", "N/A").title(),
                        "Created": u.get("created_at", "N/A")[:10] if u.get("created_at") else "N/A",
                        "Status": "Active" if u.get("is_active", True) else "Inactive",
                    })

                df = pd.DataFrame(display)
                st.dataframe(df, use_container_width=True, hide_index=True)

                # Export
                st.markdown("---")
                csv = df.to_csv(index=False)
                st.download_button(
                    "Download Users CSV",
                    csv,
                    "users.csv",
                    "text/csv",
                    use_container_width=True,
                )

                st.markdown("---")
                st.subheader("User Detail & Update")

                user_options = {
                    f"{u.get('full_name', 'N/A')} ({u.get('email', 'N/A')})": str(u.get("id") or "")
                    for u in filtered
                    if u.get("id")
                }
                if user_options:
                    selected_user_label = st.selectbox(
                        "Select user",
                        options=list(user_options.keys()),
                        key="users_detail_select"
                    )
                    selected_user_id = user_options[selected_user_label]

                    detail_response = requests.get(
                        f"{API_BASE_URL}/users/{selected_user_id}",
                        headers=get_headers(),
                        timeout=10,
                    )

                    if detail_response.status_code == 200:
                        user_detail = detail_response.json()
                        st.json(user_detail)

                        current_role = str(user_detail.get("role") or "student")
                        role_options = ["student", "instructor", "ta", "admin"]
                        default_role_index = role_options.index(current_role) if current_role in role_options else 0
                        is_active_value = bool(user_detail.get("is_active", True))

                        with st.form("update_selected_user_form"):
                            new_role = st.selectbox(
                                "Role",
                                options=role_options,
                                index=default_role_index,
                            )
                            new_is_active = st.checkbox("Active", value=is_active_value)
                            submit_update = st.form_submit_button("Update User", use_container_width=True)

                            if submit_update:
                                patch_payload = {}
                                if new_role != current_role:
                                    patch_payload["role"] = new_role
                                if new_is_active != is_active_value:
                                    patch_payload["is_active"] = new_is_active

                                if not patch_payload:
                                    st.info("No changes detected.")
                                else:
                                    patch_response = requests.patch(
                                        f"{API_BASE_URL}/users/{selected_user_id}",
                                        json=patch_payload,
                                        headers=get_headers(),
                                        timeout=10,
                                    )
                                    if patch_response.status_code == 200:
                                        st.success("User updated successfully.")
                                        st.rerun()
                                    else:
                                        st.error(f"Failed to update user: {response_error(patch_response)}")
                    else:
                        st.error(f"Failed to load user details: {response_error(detail_response)}")
            else:
                st.info("No users match the current filters.")

        elif response.status_code == 403:
            st.error("You don't have permission to view users.")
        else:
            st.error(f"Failed to load users. Status: {response.status_code}")

    except Exception as e:
        st.error(f"Connection error: {str(e)}")


if __name__ == "__main__":
    main()
