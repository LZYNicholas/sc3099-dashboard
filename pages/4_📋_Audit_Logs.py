"""
SAIV Dashboard - Audit Log Explorer
Comprehensive audit trail with filtering and search
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# Page configuration
st.set_page_config(page_title="Audit Logs - SAIV", page_icon="📋", layout="wide")

# Check authentication
if not st.session_state.get('authenticated', False):
    st.warning("Please login from the main page to access this section.")
    st.stop()

api_client = st.session_state.api_client

st.title("📋 Audit Log Explorer")
st.markdown("Browse and search the complete audit trail for compliance and security monitoring.")

st.markdown("---")

# Filter Section
st.subheader("🔍 Filters")

col1, col2, col3, col4 = st.columns(4)

with col1:
    action_options = [
        "All",
        "login_success",
        "login_failed",
        "logout",
        "user_created",
        "user_updated",
        "checkin_attempted",
        "checkin_approved",
        "checkin_flagged",
        "checkin_rejected",
        "checkin_appealed",
        "checkin_reviewed",
        "session_created",
        "session_updated",
        "session_deleted",
        "enrollment_added",
        "enrollment_removed",
        "device_registered",
        "face_enrolled"
    ]
    action_filter = st.selectbox("Action Type", options=action_options)

with col2:
    resource_options = ["All", "user", "session", "checkin", "course", "device", "enrollment"]
    resource_filter = st.selectbox("Resource Type", options=resource_options)

with col3:
    success_options = ["All", "Success Only", "Failed Only"]
    success_filter = st.selectbox("Status", options=success_options)

with col4:
    days_back = st.number_input("Days Back", min_value=1, max_value=365, value=7)

# Date range
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input(
        "Start Date",
        value=datetime.now() - timedelta(days=days_back)
    )
with col2:
    end_date = st.date_input(
        "End Date",
        value=datetime.now()
    )

# Search
search_term = st.text_input("Search by User Email", placeholder="Enter email to filter")

# Pagination
col1, col2 = st.columns(2)
with col1:
    page_size = st.selectbox("Results per page", options=[25, 50, 100, 200], index=1)
with col2:
    page = st.number_input("Page", min_value=1, value=1)

offset = (page - 1) * page_size

st.markdown("---")

# Search button
if st.button("🔍 Search Logs", type="primary"):
    st.session_state.search_triggered = True

# Auto-search on first load
if 'search_triggered' not in st.session_state:
    st.session_state.search_triggered = True

if st.session_state.search_triggered:
    with st.spinner("Loading audit logs..."):
        # Build params
        params = {
            "limit": page_size,
            "offset": offset
        }

        if action_filter != "All":
            params["action"] = action_filter

        if resource_filter != "All":
            params["resource_type"] = resource_filter

        if success_filter == "Success Only":
            params["success"] = True
        elif success_filter == "Failed Only":
            params["success"] = False

        if start_date:
            params["start_date"] = datetime.combine(start_date, datetime.min.time()).isoformat()

        if end_date:
            params["end_date"] = datetime.combine(end_date, datetime.max.time()).isoformat()

        success, result = api_client.get_audit_logs(**params)

    if success:
        logs = result.get('items', [])
        total = result.get('total', 0)

        st.info(f"Found {total} logs matching criteria. Showing page {page} ({offset + 1} - {min(offset + page_size, total)})")

        if logs:
            # Filter by search term if provided
            if search_term:
                logs = [
                    log for log in logs
                    if search_term.lower() in (log.get('user_email', '') or '').lower()
                ]

            # Create DataFrame
            df = pd.DataFrame(logs)

            # Format timestamp
            if 'timestamp' in df.columns:
                df['timestamp'] = df['timestamp'].apply(
                    lambda x: x[:19].replace('T', ' ') if x else 'N/A'
                )

            # Display table
            display_cols = ['timestamp', 'user_email', 'action', 'resource_type',
                          'resource_id', 'success', 'ip_address']
            available_cols = [col for col in display_cols if col in df.columns]

            if available_cols:
                df_display = df[available_cols].copy()

                # Rename columns
                column_names = {
                    'timestamp': 'Timestamp',
                    'user_email': 'User',
                    'action': 'Action',
                    'resource_type': 'Resource',
                    'resource_id': 'Resource ID',
                    'success': 'Success',
                    'ip_address': 'IP Address'
                }
                df_display.rename(columns=column_names, inplace=True)

                # Style success column
                def style_success(val):
                    if val == True:
                        return '✅'
                    elif val == False:
                        return '❌'
                    return '❓'

                if 'Success' in df_display.columns:
                    df_display['Success'] = df_display['Success'].apply(style_success)

                st.dataframe(df_display, use_container_width=True, height=500)

                # Pagination info
                total_pages = (total + page_size - 1) // page_size
                st.write(f"Page {page} of {total_pages}")

                # Detailed view
                st.markdown("---")
                st.subheader("📄 Log Details")

                # Select a log to view details
                if not df.empty:
                    log_indices = df.index.tolist()
                    selected_idx = st.selectbox(
                        "Select a log entry to view details",
                        options=log_indices,
                        format_func=lambda x: f"{df.loc[x, 'timestamp']} - {df.loc[x, 'action']} - {df.loc[x, 'user_email'] or 'N/A'}"
                    )

                    if selected_idx is not None:
                        selected_log = logs[selected_idx]

                        col1, col2 = st.columns(2)

                        with col1:
                            st.markdown("**Basic Information:**")
                            st.write(f"- **ID:** {selected_log.get('id', 'N/A')}")
                            st.write(f"- **Timestamp:** {selected_log.get('timestamp', 'N/A')}")
                            st.write(f"- **User:** {selected_log.get('user_email', 'N/A')}")
                            st.write(f"- **Action:** {selected_log.get('action', 'N/A')}")
                            st.write(f"- **Success:** {'✅ Yes' if selected_log.get('success') else '❌ No'}")

                        with col2:
                            st.markdown("**Request Details:**")
                            st.write(f"- **Resource Type:** {selected_log.get('resource_type', 'N/A')}")
                            st.write(f"- **Resource ID:** {selected_log.get('resource_id', 'N/A')}")
                            st.write(f"- **IP Address:** {selected_log.get('ip_address', 'N/A')}")
                            st.write(f"- **Device ID:** {selected_log.get('device_id', 'N/A')}")

                        # Details (JSON)
                        if selected_log.get('details'):
                            st.markdown("**Additional Details:**")
                            st.json(selected_log.get('details'))

                        # User Agent
                        if selected_log.get('user_agent'):
                            st.markdown("**User Agent:**")
                            st.code(selected_log.get('user_agent'))
            else:
                st.warning("No displayable columns in the result")
        else:
            st.info("No logs found matching the criteria.")
    else:
        st.error(f"Failed to load audit logs: {result}")
        st.info("Note: Audit log access may require admin privileges.")

st.markdown("---")

# Statistics
st.subheader("📊 Log Statistics")

col1, col2 = st.columns(2)

with col1:
    st.markdown("#### Common Actions")
    # This would ideally come from an aggregation endpoint
    st.markdown("""
    - `login_success` - Successful user logins
    - `checkin_attempted` - Student check-in attempts
    - `checkin_approved` - Auto-approved check-ins
    - `checkin_flagged` - Check-ins flagged for review
    - `session_created` - New sessions created
    """)

with col2:
    st.markdown("#### Security Events to Monitor")
    st.markdown("""
    - `login_failed` - Failed login attempts (watch for brute force)
    - `checkin_rejected` - Rejected check-ins (potential fraud)
    - Multiple devices per user
    - Check-ins outside geofence
    - High risk score patterns
    """)

# Export section
st.markdown("---")
st.subheader("📥 Export Audit Logs")

col1, col2, col3 = st.columns(3)

with col1:
    export_start = st.date_input(
        "Export Start Date",
        value=datetime.now() - timedelta(days=30),
        key="export_start"
    )

with col2:
    export_end = st.date_input(
        "Export End Date",
        value=datetime.now(),
        key="export_end"
    )

with col3:
    if st.button("📥 Export to CSV"):
        st.info("Export functionality requires backend support. Please use the Reports page for comprehensive exports.")
