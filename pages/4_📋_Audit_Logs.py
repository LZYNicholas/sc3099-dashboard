"""
SAIV Instructor Dashboard - Audit Logs Page
"""

import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

# Page configuration
st.set_page_config(page_title="Audit Logs - SAIV Dashboard", page_icon="📋", layout="wide")

API_BASE_URL = "http://localhost:8000/api/v1"

def check_auth():
    """Check if user is authenticated"""
    if not st.session_state.get('authenticated', False):
        st.warning("Please login from the main page.")
        st.stop()

def get_headers():
    """Get authorization headers"""
    return {"Authorization": f"Bearer {st.session_state.get('token', '')}"}

def get_action_icon(action):
    """Get icon for action type"""
    icons = {
        'login': '🔐',
        'logout': '🚪',
        'checkin': '✅',
        'create': '➕',
        'update': '✏️',
        'delete': '🗑️',
        'enroll': '📝',
        'review': '👁️',
        'export': '📥',
        'flag': '🚩'
    }
    for key, icon in icons.items():
        if key in action.lower():
            return icon
    return '📌'

def main():
    check_auth()

    st.title("📋 Audit Logs")
    st.markdown("View system audit trail and activity logs.")

    # Filters
    st.subheader("🔍 Filters")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        action_filter = st.selectbox(
            "Action Type",
            options=['All', 'login', 'logout', 'checkin', 'create', 'update', 'delete', 'enroll', 'review', 'export']
        )

    with col2:
        # Date range
        date_range = st.selectbox(
            "Date Range",
            options=['Today', 'Last 7 days', 'Last 30 days', 'Last 90 days', 'All time'],
            index=1
        )

    with col3:
        entity_filter = st.selectbox(
            "Entity Type",
            options=['All', 'user', 'course', 'session', 'checkin', 'enrollment']
        )

    with col4:
        limit = st.number_input("Max Records", min_value=10, max_value=500, value=100, step=10)

    # Calculate date filter
    if date_range == 'Today':
        start_date = datetime.now().replace(hour=0, minute=0, second=0)
    elif date_range == 'Last 7 days':
        start_date = datetime.now() - timedelta(days=7)
    elif date_range == 'Last 30 days':
        start_date = datetime.now() - timedelta(days=30)
    elif date_range == 'Last 90 days':
        start_date = datetime.now() - timedelta(days=90)
    else:
        start_date = None

    # Search
    col1, col2 = st.columns([4, 1])
    with col1:
        search_query = st.text_input("Search (user email, entity ID, or details)", placeholder="Enter search term...")
    with col2:
        st.write("")  # Spacing
        search_btn = st.button("🔍 Search", use_container_width=True)

    st.markdown("---")

    # Fetch audit logs
    try:
        params = {'limit': limit}
        if action_filter != 'All':
            params['action'] = action_filter
        if entity_filter != 'All':
            params['entity_type'] = entity_filter
        if start_date:
            params['start_date'] = start_date.isoformat()
        if search_query:
            params['search'] = search_query

        response = requests.get(
            f"{API_BASE_URL}/audit/",
            params=params,
            headers=get_headers(),
            timeout=15
        )

        if response.status_code == 200:
            logs = response.json()

            if not logs:
                st.info("No audit logs found matching the filters.")
                return

            # Summary statistics
            st.subheader("📊 Summary")
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Total Records", len(logs))
            with col2:
                unique_users = len(set(log.get('user_email', '') for log in logs if log.get('user_email')))
                st.metric("Unique Users", unique_users)
            with col3:
                action_counts = {}
                for log in logs:
                    action = log.get('action', 'unknown')
                    action_counts[action] = action_counts.get(action, 0) + 1
                most_common = max(action_counts, key=action_counts.get) if action_counts else 'N/A'
                st.metric("Most Common Action", most_common)
            with col4:
                # Count flagged or suspicious
                suspicious = sum(1 for log in logs if 'flag' in log.get('action', '').lower() or 'suspicious' in log.get('details', '').lower())
                st.metric("Flagged Events", suspicious)

            st.markdown("---")

            # Logs Table
            st.subheader("📜 Audit Trail")

            # Prepare data for display
            display_data = []
            for log in logs:
                timestamp = log.get('timestamp', '')
                if timestamp:
                    try:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        timestamp = dt.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        pass

                display_data.append({
                    'Timestamp': timestamp,
                    'Action': f"{get_action_icon(log.get('action', ''))} {log.get('action', 'N/A')}",
                    'User': log.get('user_email', 'System'),
                    'Entity': log.get('entity_type', 'N/A'),
                    'Entity ID': log.get('entity_id', 'N/A')[:8] + '...' if log.get('entity_id') and len(log.get('entity_id', '')) > 8 else log.get('entity_id', 'N/A'),
                    'IP Address': log.get('ip_address', 'N/A'),
                    'Details': log.get('details', '')[:50] + '...' if log.get('details') and len(log.get('details', '')) > 50 else log.get('details', 'N/A'),
                    'Full ID': log.get('id', ''),
                    'Full Details': log.get('details', '')
                })

            df = pd.DataFrame(display_data)
            st.dataframe(
                df.drop(columns=['Full ID', 'Full Details']),
                use_container_width=True,
                hide_index=True
            )

            # Detailed View
            st.markdown("---")
            st.subheader("🔎 Detailed View")

            log_options = {i: f"{d['Timestamp']} - {d['Action']} by {d['User']}" for i, d in enumerate(display_data)}
            selected_idx = st.selectbox(
                "Select a log entry to view details",
                options=list(log_options.keys()),
                format_func=lambda x: log_options[x]
            )

            if selected_idx is not None:
                selected_log = logs[selected_idx]
                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("#### Event Information")
                    st.write(f"**ID:** `{selected_log.get('id', 'N/A')}`")
                    st.write(f"**Action:** {selected_log.get('action', 'N/A')}")
                    st.write(f"**Timestamp:** {selected_log.get('timestamp', 'N/A')}")
                    st.write(f"**User:** {selected_log.get('user_email', 'System')}")
                    st.write(f"**User ID:** `{selected_log.get('user_id', 'N/A')}`")

                with col2:
                    st.markdown("#### Context")
                    st.write(f"**Entity Type:** {selected_log.get('entity_type', 'N/A')}")
                    st.write(f"**Entity ID:** `{selected_log.get('entity_id', 'N/A')}`")
                    st.write(f"**IP Address:** {selected_log.get('ip_address', 'N/A')}")
                    st.write(f"**User Agent:** {selected_log.get('user_agent', 'N/A')[:50]}..." if selected_log.get('user_agent') else "N/A")

                st.markdown("#### Details")
                details = selected_log.get('details', 'No additional details')
                st.code(details if details else 'No additional details', language='json')

            # Export option
            st.markdown("---")
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                st.markdown("#### Export Logs")
            with col2:
                csv = df.drop(columns=['Full ID', 'Full Details']).to_csv(index=False)
                st.download_button(
                    "📥 Download CSV",
                    csv,
                    "audit_logs.csv",
                    "text/csv",
                    use_container_width=True
                )
            with col3:
                json_data = pd.DataFrame(logs).to_json(orient='records', indent=2)
                st.download_button(
                    "📥 Download JSON",
                    json_data,
                    "audit_logs.json",
                    "application/json",
                    use_container_width=True
                )

        elif response.status_code == 403:
            st.error("You don't have permission to view audit logs.")
        else:
            st.error(f"Failed to load audit logs. Status: {response.status_code}")

    except Exception as e:
        st.error(f"Connection error: {str(e)}")
        st.info("Make sure the backend server is running.")


if __name__ == "__main__":
    main()
