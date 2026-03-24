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


def main():
    require_auth()

    user = st.session_state.get("user", {})
    if user.get("role") not in ("admin", "instructor"):
        st.error("Access denied. This page is restricted to admins and instructors.")
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
