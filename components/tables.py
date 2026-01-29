"""
Reusable table components for displaying data
"""

import pandas as pd
import streamlit as st
from typing import List, Dict, Any, Optional
from utils.formatters import (
    format_datetime, format_percentage, format_distance,
    status_badge, risk_badge, get_status_icon
)

def create_student_attendance_table(data: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Create formatted student attendance table

    Args:
        data: List of student attendance records

    Returns:
        Formatted DataFrame
    """
    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)

    # Format columns
    formatted_data = []
    for _, row in df.iterrows():
        formatted_row = {
            'Student ID': row.get('student_id', 'N/A'),
            'Name': row.get('student_name', 'N/A'),
            'Email': row.get('email', 'N/A'),
            'Sessions Attended': row.get('attended', 0),
            'Total Sessions': row.get('total', 0),
            'Attendance Rate': format_percentage(row.get('attendance_rate', 0)),
            'Last Check-in': format_datetime(row.get('last_checkin'))
        }
        formatted_data.append(formatted_row)

    return pd.DataFrame(formatted_data)

def create_checkin_list_table(data: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Create formatted check-in list table

    Args:
        data: List of check-in records

    Returns:
        Formatted DataFrame
    """
    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)

    # Format columns
    formatted_data = []
    for _, row in df.iterrows():
        formatted_row = {
            'ID': row.get('id', 'N/A'),
            'Student': row.get('student_name', 'N/A'),
            'Time': format_datetime(row.get('timestamp')),
            'Status': row.get('status', 'N/A').upper(),
            'Distance': format_distance(row.get('distance_from_venue')),
            'Risk Score': f"{row.get('risk_score', 0):.2f}" if row.get('risk_score') is not None else 'N/A',
            'Verification': row.get('verification_method', 'N/A')
        }
        formatted_data.append(formatted_row)

    return pd.DataFrame(formatted_data)

def create_session_list_table(data: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Create formatted session list table

    Args:
        data: List of session records

    Returns:
        Formatted DataFrame
    """
    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)

    # Format columns
    formatted_data = []
    for _, row in df.iterrows():
        formatted_row = {
            'ID': row.get('id', 'N/A'),
            'Course': row.get('course_code', 'N/A'),
            'Title': row.get('title', 'N/A'),
            'Date': format_datetime(row.get('scheduled_time'), "%Y-%m-%d"),
            'Time': format_datetime(row.get('scheduled_time'), "%H:%M"),
            'Location': row.get('location', 'N/A'),
            'Check-ins': row.get('checkin_count', 0),
            'Status': 'Active' if row.get('is_active') else 'Inactive'
        }
        formatted_data.append(formatted_row)

    return pd.DataFrame(formatted_data)

def create_audit_log_table(data: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Create formatted audit log table

    Args:
        data: List of audit log records

    Returns:
        Formatted DataFrame
    """
    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)

    # Format columns
    formatted_data = []
    for _, row in df.iterrows():
        formatted_row = {
            'Timestamp': format_datetime(row.get('timestamp')),
            'User': row.get('user_email', 'System'),
            'Action': row.get('action', 'N/A'),
            'Resource': row.get('resource_type', 'N/A'),
            'Resource ID': row.get('resource_id', 'N/A'),
            'Status': 'Success' if row.get('success') else 'Failed',
            'IP Address': row.get('ip_address', 'N/A')
        }
        formatted_data.append(formatted_row)

    return pd.DataFrame(formatted_data)

def display_student_attendance_table(data: List[Dict[str, Any]], show_low_attendance: bool = True):
    """
    Display student attendance table with formatting and highlighting

    Args:
        data: List of student attendance records
        show_low_attendance: Whether to highlight low attendance
    """
    if not data:
        st.info("No student data available")
        return

    df = create_student_attendance_table(data)

    if show_low_attendance:
        # Highlight low attendance
        def highlight_low_attendance(row):
            try:
                rate = float(row['Attendance Rate'].rstrip('%'))
                if rate < 50:
                    return ['background-color: #f8d7da'] * len(row)
                elif rate < 75:
                    return ['background-color: #fff3cd'] * len(row)
                else:
                    return [''] * len(row)
            except:
                return [''] * len(row)

        styled_df = df.style.apply(highlight_low_attendance, axis=1)
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)

def display_checkin_list_table(data: List[Dict[str, Any]], show_actions: bool = False):
    """
    Display check-in list table with status indicators

    Args:
        data: List of check-in records
        show_actions: Whether to show action buttons
    """
    if not data:
        st.info("No check-ins available")
        return

    for idx, checkin in enumerate(data):
        with st.container():
            col1, col2, col3, col4, col5 = st.columns([2, 2, 1, 1, 1])

            with col1:
                st.write(f"**{checkin.get('student_name', 'N/A')}**")
                st.caption(checkin.get('student_email', 'N/A'))

            with col2:
                st.write(format_datetime(checkin.get('timestamp')))

            with col3:
                status = checkin.get('status', 'N/A')
                st.markdown(status_badge(status), unsafe_allow_html=True)

            with col4:
                risk = checkin.get('risk_score')
                st.markdown(risk_badge(risk), unsafe_allow_html=True)

            with col5:
                distance = checkin.get('distance_from_venue')
                st.write(format_distance(distance))

            # Show additional details
            with st.expander("Details"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write(f"**Verification:** {checkin.get('verification_method', 'N/A')}")
                with col2:
                    st.write(f"**Device:** {checkin.get('device_info', 'N/A')}")
                with col3:
                    st.write(f"**Location:** {checkin.get('location_coords', 'N/A')}")

                if checkin.get('notes'):
                    st.write(f"**Notes:** {checkin.get('notes')}")

            if show_actions and checkin.get('status', '').lower() in ['pending', 'flagged']:
                col1, col2, col3 = st.columns([1, 1, 4])
                with col1:
                    if st.button("Approve", key=f"approve_{idx}"):
                        return {'action': 'approve', 'checkin_id': checkin.get('id')}
                with col2:
                    if st.button("Reject", key=f"reject_{idx}"):
                        return {'action': 'reject', 'checkin_id': checkin.get('id')}

            st.divider()

def display_session_list_table(data: List[Dict[str, Any]]):
    """
    Display session list table

    Args:
        data: List of session records
    """
    if not data:
        st.info("No sessions available")
        return

    df = create_session_list_table(data)
    st.dataframe(df, use_container_width=True, hide_index=True)

def display_audit_log_table(data: List[Dict[str, Any]]):
    """
    Display audit log table with expandable details

    Args:
        data: List of audit log records
    """
    if not data:
        st.info("No audit logs available")
        return

    for idx, log in enumerate(data):
        with st.container():
            col1, col2, col3, col4 = st.columns([2, 2, 2, 1])

            with col1:
                st.write(format_datetime(log.get('timestamp')))

            with col2:
                st.write(f"**{log.get('action', 'N/A')}**")
                st.caption(log.get('user_email', 'System'))

            with col3:
                st.write(f"{log.get('resource_type', 'N/A')} #{log.get('resource_id', 'N/A')}")

            with col4:
                success = log.get('success', False)
                if success:
                    st.markdown(status_badge('approved'), unsafe_allow_html=True)
                else:
                    st.markdown(status_badge('rejected'), unsafe_allow_html=True)

            # Show additional details
            with st.expander("Details"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**IP Address:** {log.get('ip_address', 'N/A')}")
                    st.write(f"**User Agent:** {log.get('user_agent', 'N/A')}")
                with col2:
                    st.write(f"**Request ID:** {log.get('request_id', 'N/A')}")
                    if log.get('error_message'):
                        st.error(f"**Error:** {log.get('error_message')}")

                if log.get('details'):
                    st.write("**Additional Details:**")
                    st.json(log.get('details'))

            st.divider()

def create_summary_metrics(data: Dict[str, Any]):
    """
    Display summary metrics in columns

    Args:
        data: Dictionary with metric names as keys and values
    """
    num_cols = min(len(data), 4)
    cols = st.columns(num_cols)

    for idx, (key, value) in enumerate(data.items()):
        col_idx = idx % num_cols
        with cols[col_idx]:
            if isinstance(value, dict):
                st.metric(
                    label=value.get('label', key),
                    value=value.get('value', 'N/A'),
                    delta=value.get('delta'),
                    help=value.get('help')
                )
            else:
                st.metric(label=key, value=value)

def display_flagged_checkins(data: List[Dict[str, Any]]):
    """
    Display flagged check-ins requiring review with prominent styling

    Args:
        data: List of flagged check-in records
    """
    if not data:
        st.success("No flagged check-ins requiring review")
        return

    st.warning(f"**{len(data)} check-ins flagged for review**")

    for idx, checkin in enumerate(data):
        with st.container():
            # Header row with key info
            col1, col2, col3, col4 = st.columns([3, 2, 2, 2])

            with col1:
                st.write(f"**{get_status_icon('flagged')} {checkin.get('student_name', 'N/A')}**")
                st.caption(checkin.get('student_email', 'N/A'))

            with col2:
                st.write(format_datetime(checkin.get('timestamp')))

            with col3:
                risk = checkin.get('risk_score')
                st.markdown(risk_badge(risk), unsafe_allow_html=True)

            with col4:
                distance = checkin.get('distance_from_venue')
                st.write(f"Distance: {format_distance(distance)}")

            # Flagged reasons
            if checkin.get('flag_reasons'):
                st.write("**Flagged because:**")
                for reason in checkin.get('flag_reasons', []):
                    st.write(f"- {reason}")

            st.divider()
