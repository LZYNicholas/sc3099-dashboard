"""SAIV Instructor Dashboard - Courses Analytics Page
"""

import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from lib.auth_state import API_BASE_URL, get_auth_headers, require_auth
from lib.response_utils import bool_query, fetch_all_items, response_error as shared_response_error, friendly_error
from lib.ui_theme import apply_theme

# Page configuration

def get_headers():
    return get_auth_headers()


def response_error(response: requests.Response | None, fallback: str = "Unknown error") -> str:
    return shared_response_error(response, fallback)

def main(embedded: bool = False):
    if not embedded:
        require_auth()
    current_role = str((st.session_state.get('user') or {}).get('role', '')).strip().lower()
    if current_role not in {"instructor", "admin"}:
        st.error("Access denied. This page is restricted to instructors and admins.")
        st.stop()

    if not embedded:
        st.title("Course Analytics")
        st.markdown("View detailed statistics and analytics for your courses.")

    # Fetch only active courses (no analytics for deleted courses)
    try:
        courses = fetch_all_items(
            f"{API_BASE_URL}/courses/",
            headers=get_headers(),
            params={"is_active": bool_query(True)},
            timeout=10,
            page_size=200,
        )

        if courses:

            if not courses:
                st.info("No active courses found. Create a course in the Manage page.")
                return

            # Course selector
            course_options = {c['id']: f"{c['code']} - {c['name']}" for c in courses}
            selected_course_id = st.selectbox(
                "Select Course",
                options=list(course_options.keys()),
                format_func=lambda x: course_options[x]
            )

            if selected_course_id:
                # Get course details
                selected_course = next((c for c in courses if c['id'] == selected_course_id), None)

                try:
                    course_detail_response = requests.get(
                        f"{API_BASE_URL}/courses/{selected_course_id}",
                        headers=get_headers(),
                        timeout=10
                    )
                    if course_detail_response.status_code == 200:
                        detail_payload = course_detail_response.json()
                        if isinstance(detail_payload, dict):
                            selected_course = detail_payload
                except Exception:
                    pass

                if selected_course:
                    venue_lat = selected_course.get('venue_latitude')
                    venue_lon = selected_course.get('venue_longitude')
                    risk_threshold = selected_course.get('risk_threshold')

                    # Course Info Card
                    st.markdown("---")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.markdown("### Course Details")
                        st.write(f"**Code:** {selected_course.get('code', 'N/A')}")
                        st.write(f"**Name:** {selected_course.get('name', 'N/A')}")
                        st.write(f"**Semester:** {selected_course.get('semester', 'N/A')}")
                    with col2:
                        st.markdown("### Location")
                        st.write(f"**Latitude:** {venue_lat if venue_lat is not None else 'Not set'}")
                        st.write(f"**Longitude:** {venue_lon if venue_lon is not None else 'Not set'}")
                        st.write(f"**Radius:** {selected_course.get('geofence_radius_meters', 'Not set')}m")
                    with col3:
                        st.markdown("### Security")
                        st.write(f"**Risk Threshold:** {risk_threshold if risk_threshold is not None else 'Not set'}")
                        st.write(f"**Face Recognition:** {'On' if selected_course.get('require_face_recognition') else 'Off'}")
                        st.write(f"**Device Binding:** {'On' if selected_course.get('require_device_binding') else 'Off'}")
                        st.write(f"**Created:** {selected_course.get('created_at', 'Unknown')[:10] if selected_course.get('created_at') else 'Unknown'}")

                # Fetch course statistics
                try:
                    stats_response = requests.get(
                        f"{API_BASE_URL}/stats/courses/{selected_course_id}",
                        headers=get_headers(),
                        timeout=10
                    )

                    if stats_response.status_code == 200:
                        stats = stats_response.json()

                        st.markdown("---")
                        st.subheader("Course Statistics")

                        # Metrics row
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Total Sessions", stats.get('total_sessions', 0))
                        with col2:
                            st.metric("Total Enrolled", stats.get('total_enrolled', stats.get('total_enrollments', 0)))
                        with col3:
                            total_checkins = stats.get('total_checkins', stats.get('total_checked_in', 0))
                            st.metric("Total Check-ins", total_checkins)
                        with col4:
                            rate = stats.get('overall_attendance_rate', stats.get('attendance_rate', 0)) * 100
                            st.metric("Attendance Rate", f"{rate:.1f}%")

                        st.markdown("---")

                        # Charts
                        col1, col2 = st.columns(2)

                        with col1:
                            st.subheader("Attendance Trend")
                            trend_data = stats.get('attendance_trend', [])
                            if not trend_data:
                                # Fallback for current backend payload: derive trend from session stats.
                                sessions_data = stats.get('sessions', [])
                                if isinstance(sessions_data, list) and sessions_data:
                                    derived = []
                                    for row in sessions_data:
                                        if not isinstance(row, dict):
                                            continue
                                        date_value = row.get('date') or row.get('scheduled_start')
                                        raw_rate = row.get('attendance_rate')
                                        try:
                                            rate_value = float(raw_rate) if raw_rate is not None else None
                                        except Exception:
                                            rate_value = None
                                        if rate_value is None:
                                            # Derive attendance rate when explicit rate is absent.
                                            try:
                                                checked_in = float(row.get('checked_in', 0) or 0)
                                                enrolled = float(row.get('enrolled', 0) or 0)
                                                rate_value = (checked_in / enrolled) if enrolled > 0 else 0.0
                                            except Exception:
                                                rate_value = None
                                        if date_value is None or rate_value is None:
                                            continue
                                        if rate_value <= 1:
                                            rate_value *= 100
                                        derived.append({
                                            "date": date_value,
                                            "attendance_rate": max(0.0, min(rate_value, 100.0)),
                                        })
                                    trend_data = sorted(derived, key=lambda r: str(r.get("date")))
                            if trend_data:
                                df = pd.DataFrame(trend_data)
                                if "date" in df.columns:
                                    df["date"] = pd.to_datetime(df["date"], errors="coerce")
                                    df = df.dropna(subset=["date"]).sort_values("date")
                                fig = px.line(
                                    df, x='date', y='attendance_rate',
                                    labels={'date': 'Date', 'attendance_rate': 'Rate (%)'},
                                    markers=True
                                )
                                fig.update_layout(yaxis_range=[0, 100])
                                st.plotly_chart(fig, use_container_width=True)
                            else:
                                st.info("No attendance trend data available.")

                        with col2:
                            st.subheader("Session Breakdown")
                            session_data = stats.get('sessions', [])
                            if session_data:
                                df = pd.DataFrame(session_data)
                                # Accept multiple backend payload variants for session check-in count.
                                y_col = None
                                for candidate in ['checkin_count', 'checked_in', 'checked_in_count', 'total_checkins']:
                                    if candidate in df.columns:
                                        y_col = candidate
                                        break

                                x_col = 'name' if 'name' in df.columns else ('session_name' if 'session_name' in df.columns else ('session_id' if 'session_id' in df.columns else None))

                                if y_col is None or x_col is None:
                                    st.info("Session breakdown data is available but missing expected fields.")
                                    st.dataframe(df, use_container_width=True, hide_index=True)
                                else:
                                    df[y_col] = pd.to_numeric(df[y_col], errors='coerce').fillna(0)
                                    if 'status' not in df.columns:
                                        df['status'] = 'unknown'
                                    # Normalize labels so bars stay visible and understandable.
                                    df['status'] = df['status'].fillna('unknown').astype(str).str.lower()
                                    df['status_display'] = df['status'].map({
                                        'scheduled': 'Scheduled',
                                        'active': 'Active',
                                        'closed': 'Closed (finalized)',
                                        'completed': 'Closed (finalized)',
                                        'cancelled': 'Cancelled',
                                    }).fillna('Unknown')

                                    if 'session_id' in df.columns:
                                        sid_suffix = df['session_id'].astype(str).str[-6:]
                                    else:
                                        sid_suffix = pd.Series([''] * len(df))
                                    name_text = df[x_col].fillna('Untitled Session').astype(str).str.strip()
                                    df['session_label'] = name_text + sid_suffix.map(lambda s: f" [{s}]" if s else "")

                                    if float(df[y_col].sum()) <= 0:
                                        st.info("No check-ins have been recorded for these sessions yet.")
                                        status_counts = (
                                            df['status_display']
                                            .value_counts()
                                            .rename_axis('status_display')
                                            .reset_index(name='count')
                                        )
                                        status_fig = px.bar(
                                            status_counts,
                                            x='status_display',
                                            y='count',
                                            labels={'status_display': 'Session Status', 'count': 'Session Count'},
                                            color='status_display',
                                            color_discrete_map={
                                                'Scheduled': '#6c757d',
                                                'Active': '#28a745',
                                                'Closed (finalized)': '#1f77b4',
                                                'Cancelled': '#dc3545',
                                                'Unknown': '#9ca3af'
                                            }
                                        )
                                        try:
                                            st.plotly_chart(status_fig, use_container_width=True)
                                        except Exception:
                                            st.bar_chart(status_counts.set_index('status_display')['count'])
                                    else:
                                        try:
                                            fig = px.bar(
                                                df, x='session_label', y=y_col,
                                                labels={'session_label': 'Session', y_col: 'Check-ins'},
                                                color='status_display',
                                                color_discrete_map={
                                                    'Scheduled': '#6c757d',
                                                    'Active': '#28a745',
                                                    'Closed (finalized)': '#1f77b4',
                                                    'Cancelled': '#dc3545',
                                                    'Unknown': '#9ca3af'
                                                }
                                            )
                                            st.plotly_chart(fig, use_container_width=True)
                                        except Exception:
                                            fallback_df = df[['session_label', y_col]].copy()
                                            fallback_df = fallback_df.rename(columns={y_col: 'checkins'})
                                            st.bar_chart(fallback_df.set_index('session_label')['checkins'])
                                    st.caption("`Closed (finalized)` means the session ended and attendance was finalized.")
                                    breakdown_cols = [c for c in ['session_label', 'status_display', y_col] if c in df.columns]
                                    st.dataframe(
                                        df[breakdown_cols].rename(columns={y_col: 'checkins'}),
                                        use_container_width=True,
                                        hide_index=True,
                                    )
                            else:
                                st.info("No session data available.")

                        # Student Performance Table
                        st.markdown("---")
                        st.subheader("Student Attendance")
                        student_data = stats.get('student_attendance', [])
                        if student_data:
                            df = pd.DataFrame(student_data)
                            df['attendance_rate'] = (df['attendance_rate'] * 100).round(1).astype(str) + '%'
                            st.dataframe(df, use_container_width=True, hide_index=True)
                        else:
                            st.info("No student attendance data available for this selected course yet.")

                    else:
                        if stats_response.status_code == 404:
                            st.info("Course statistics endpoint is not available on this backend branch yet.")
                        else:
                            st.warning(response_error(stats_response, "Couldn't load course statistics right now."))

                except Exception as e:
                    st.warning(friendly_error(e, "Couldn't load course statistics right now."))

                if not embedded:
                    st.caption("Enrollment list and actions are centralized in `Manage` and `Students` to keep this page analytics-focused.")

        else:
            st.error("Failed to load courses or no courses were returned.")

    except Exception as e:
        st.error(friendly_error(e, "Couldn't load courses right now."))



