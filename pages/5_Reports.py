"""SAIV Instructor Dashboard - Reports & Export Page
"""

import streamlit as st
import requests
import pandas as pd
import json
from datetime import datetime
from lib.auth_state import API_BASE_URL, get_auth_headers, require_auth
from lib.response_utils import extract_items, fetch_all_items, request_with_retry, response_error

# Page configuration
st.set_page_config(page_title="Reports - SAIV Dashboard", layout="wide", initial_sidebar_state="expanded")

def get_headers():
    return get_auth_headers()


def _get_format_options():
    """Return API-supported export format options only."""
    options = ['csv', 'json']
    labels = {'csv': 'CSV (Comma Separated)', 'json': 'JSON'}
    return options, labels


def main():
    require_auth()
    current_role = str((st.session_state.get('user') or {}).get('role', '')).strip().lower()
    if current_role not in {'instructor', 'admin'}:
        st.error("Access denied. This page is restricted to instructors and admins.")
        st.stop()

    st.title("Reports & Data Export")
    st.markdown("Generate and download attendance reports in various formats.")

    tab1, tab2, tab3 = st.tabs(["Course Reports", "Session Reports", "Custom Reports"])

    with tab1:
        course_reports()

    with tab2:
        session_reports()

    with tab3:
        custom_reports()

    st.caption("Session-level operational exports are available in `Sessions` to avoid duplicate report workflows.")


def _offer_download(response, export_format, base_filename, title):
    """Offer download button for the given response and format."""
    mime_types = {
        'csv': 'text/csv',
        'json': 'application/json'
    }
    st.success("Report generated successfully!")
    st.download_button(
        f"Download {export_format.upper()} Report",
        response.content,
        f"{base_filename}.{export_format}",
        mime_types.get(export_format, 'application/octet-stream'),
        use_container_width=True
    )


def _load_all_courses():
    try:
        return fetch_all_items(
            f"{API_BASE_URL}/courses/",
            headers=get_headers(),
            timeout=10,
            page_size=200,
        )
    except Exception:
        return []


def _fetch_checkins(params: dict) -> list[dict]:
    rows: list[dict] = []
    limit = 200
    offset = 0
    while True:
        query = {**params, "limit": limit, "offset": offset}
        resp = requests.get(
            f"{API_BASE_URL}/checkins/",
            params=query,
            headers=get_headers(),
            timeout=20
        )
        if resp.status_code != 200:
            break
        payload = resp.json()
        items = extract_items(payload)
        if not items:
            break
        rows.extend(items)
        if len(items) < limit:
            break
        offset += limit
    return rows


def _build_checkin_export_df(
    checkins: list[dict],
    *,
    include_details: bool = True,
    include_risk: bool = False,
    include_location: bool = False,
    include_photos: bool = False,
) -> pd.DataFrame:
    data_rows: list[dict] = []
    for ci in checkins:
        row = {
            "Check-in ID": ci.get("id"),
            "Student ID": ci.get("student_id"),
            "Session ID": ci.get("session_id"),
            "Timestamp": ci.get("checked_in_at"),
            "Verification Status": ci.get("status"),
        }
        if include_details:
            row.update({
                "Student Name": ci.get("student_name"),
                "Student Email": ci.get("student_email"),
                "Course Code": ci.get("course_code"),
                "Session Name": ci.get("session_name"),
            })
        if include_risk:
            row.update({
                "Risk Score": ci.get("risk_score"),
                "Liveness Score": ci.get("liveness_score"),
                "Face Match Score": ci.get("face_match_score"),
                "Liveness Passed": ci.get("liveness_passed"),
                "Risk Factors": json.dumps(ci.get("risk_factors")) if isinstance(ci.get("risk_factors"), (dict, list)) else ci.get("risk_factors"),
                "Risk Signals": json.dumps(ci.get("risk_signals")) if isinstance(ci.get("risk_signals"), (dict, list)) else ci.get("risk_signals"),
            })
        if include_location:
            row.update({
                "Latitude": ci.get("latitude"),
                "Longitude": ci.get("longitude"),
                "Distance From Venue (m)": ci.get("distance_from_venue_meters"),
            })
        if include_photos:
            row["Photo Reference"] = ""
        data_rows.append(row)
    return pd.DataFrame(data_rows)


def _download_custom_export(df: pd.DataFrame, *, export_format: str, filename_base: str, include_stats: bool = False):
    st.success("Report generated successfully!")
    if export_format == "csv":
        payload = df.to_csv(index=False)
        mime = "text/csv"
        file_name = f"{filename_base}.csv"
    else:
        records = df.to_dict(orient="records")
        if include_stats:
            content = {
                "summary": {
                    "total_records": len(records),
                    "approved": int((df.get("Verification Status", pd.Series(dtype=str)) == "approved").sum()) if not df.empty else 0,
                    "flagged_or_appealed": int(df.get("Verification Status", pd.Series(dtype=str)).isin(["flagged", "appealed"]).sum()) if not df.empty else 0,
                    "rejected": int((df.get("Verification Status", pd.Series(dtype=str)) == "rejected").sum()) if not df.empty else 0,
                },
                "records": records,
            }
            payload = json.dumps(content, indent=2)
        else:
            payload = json.dumps(records, indent=2)
        mime = "application/json"
        file_name = f"{filename_base}.json"

    st.download_button(
        f"Download {export_format.upper()} Report",
        payload,
        file_name,
        mime,
        use_container_width=True,
    )


def course_reports():
    """Course attendance reports"""
    st.subheader("Course Attendance Reports")
    st.markdown("Export attendance data for entire courses.")

    try:
        courses = _load_all_courses()

        if courses:

            if not courses:
                st.info("No courses available. Create a course first.")
                return

            col1, col2 = st.columns(2)

            with col1:
                course_options = {c['id']: f"{c['code']} - {c['name']}" for c in courses}
                selected_course = st.selectbox(
                    "Select Course",
                    options=list(course_options.keys()),
                    format_func=lambda x: course_options[x],
                    key="course_report_select"
                )

            with col2:
                fmt_options, fmt_labels = _get_format_options()
                export_format = st.selectbox(
                    "Export Format",
                    options=fmt_options,
                    format_func=lambda x: fmt_labels[x],
                    key="course_format"
                )

            use_date_range = st.checkbox("Filter by date range", value=False, key="course_export_use_dates")
            date_col1, date_col2 = st.columns(2)
            with date_col1:
                start_date = st.date_input("Start Date", key="course_export_start", disabled=not use_date_range)
            with date_col2:
                end_date = st.date_input("End Date", key="course_export_end", disabled=not use_date_range)

            st.markdown("---")

            if st.button("Generate Course Report", use_container_width=True, key="gen_course_report"):
                with st.spinner("Generating report..."):
                    try:
                        params = {"format": export_format}
                        if use_date_range:
                            params["start_date"] = pd.Timestamp(start_date).tz_localize("UTC").isoformat()
                            params["end_date"] = pd.Timestamp(end_date).tz_localize("UTC").replace(
                                hour=23, minute=59, second=59
                            ).isoformat()

                        response, error = request_with_retry(
                            "GET",
                            f"{API_BASE_URL}/export/attendance/{selected_course}",
                            params=params,
                            headers=get_headers(),
                            timeout=25,
                            retries=2,
                        )
                        if response is None:
                            st.error(f"Failed to generate report: {error or 'request failed'}")
                            return
                        if response.status_code != 200:
                            st.error(f"Failed to generate report ({response.status_code}): {response_error(response)}")
                            return

                        if not response.content:
                            st.warning("No records found for the selected course/date range.")
                        else:
                            course_name = course_options[selected_course].replace(' ', '_').replace('-', '_')
                            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                            _offer_download(
                                response,
                                export_format,
                                f"attendance_{course_name}_{timestamp}",
                                "Course Attendance Report",
                            )

                    except Exception as e:
                        st.error(f"Error generating report: {str(e)}")

        else:
            st.error("Failed to load courses.")

    except Exception as e:
        st.error(f"Connection error: {str(e)}")


def session_reports():
    """Session-specific reports"""
    st.subheader("Session Reports")
    st.markdown("Export attendance data for individual sessions.")

    try:
        courses = _load_all_courses()

        if courses:

            if not courses:
                st.info("No courses available.")
                return

            col1, col2 = st.columns(2)

            with col1:
                course_options = {c['id']: f"{c['code']} - {c['name']}" for c in courses}
                selected_course = st.selectbox(
                    "Select Course",
                    options=list(course_options.keys()),
                    format_func=lambda x: course_options[x],
                    key="session_course_select"
                )

            sessions_response, sessions_error = request_with_retry(
                "GET",
                f"{API_BASE_URL}/sessions/",
                params={"course_id": selected_course},
                headers=get_headers(),
                timeout=10,
                retries=2,
            )
            if sessions_response is None:
                st.error(f"Failed to load sessions: {sessions_error or 'request failed'}")
                return
            sessions = extract_items(sessions_response.json()) if sessions_response.status_code == 200 else []

            with col2:
                if sessions:
                    session_options = {s['id']: f"{s['name']} ({s.get('status', 'unknown')})" for s in sessions}
                    selected_session = st.selectbox(
                        "Select Session",
                        options=list(session_options.keys()),
                        format_func=lambda x: session_options[x],
                        key="session_report_select"
                    )
                else:
                    st.info("No sessions available for this course.")
                    return

            col1, col2 = st.columns(2)

            with col1:
                fmt_options, fmt_labels = _get_format_options()
                export_format = st.selectbox(
                    "Export Format",
                    options=fmt_options,
                    format_func=lambda x: fmt_labels[x],
                    key="session_format"
                )

            with col2:
                st.caption("Uses backend session export endpoint.")

            st.markdown("---")

            if st.button("Generate Session Report", use_container_width=True, key="gen_session_report"):
                with st.spinner("Generating report..."):
                    try:
                        export_resp, export_error = request_with_retry(
                            "GET",
                            f"{API_BASE_URL}/export/session/{selected_session}",
                            params={"format": export_format},
                            headers=get_headers(),
                            timeout=25,
                            retries=2,
                        )
                        if export_resp is None:
                            st.error(f"Failed to generate session report: {export_error or 'request failed'}")
                            return
                        if export_resp.status_code != 200:
                            st.error(f"Failed to generate report ({export_resp.status_code}): {response_error(export_resp)}")
                            return
                        if not export_resp.content:
                            st.warning("No check-ins found for this session.")
                        else:
                            session_name = session_options[selected_session].split('(')[0].strip().replace(' ', '_')
                            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                            _offer_download(
                                export_resp,
                                export_format,
                                f"session_{session_name}_{timestamp}",
                                "Session Attendance Report",
                            )

                    except Exception as e:
                        st.error(f"Error generating report: {str(e)}")

        else:
            st.error("Failed to load courses.")

    except Exception as e:
        st.error(f"Connection error: {str(e)}")


def custom_reports():
    """Custom report builder"""
    st.subheader("Custom Report Builder")
    st.markdown("Build custom reports with specific data fields and filters.")

    report_type = st.selectbox(
        "Report Type",
        options=['attendance_summary', 'student_performance', 'risk_analysis', 'enrollment_status'],
        format_func=lambda x: {
            'attendance_summary': 'Attendance Summary',
            'student_performance': 'Student Performance',
            'risk_analysis': 'Risk Analysis',
            'enrollment_status': 'Enrollment Status'
        }[x]
    )

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Filters")
        date_col1, date_col2 = st.columns(2)
        with date_col1:
            start_date = st.date_input("Start Date", key="custom_start")
        with date_col2:
            end_date = st.date_input("End Date", key="custom_end")

        try:
            raw_courses = _load_all_courses()
            courses = [c for c in raw_courses if isinstance(c, dict) and c.get("id")]
        except Exception:
            courses = []

        if courses:
            course_options = ["All"] + [str(c["id"]) for c in courses]
            selected_courses = st.multiselect(
                "Filter by Courses",
                options=course_options,
                default=["All"],
                format_func=lambda x: "All Courses" if x == "All" else next(
                    (f"{c.get('code', 'N/A')} - {c.get('name', 'Unnamed')}" for c in courses if str(c.get("id")) == x),
                    x
                ),
            )
        else:
            selected_courses = ["All"]
            st.caption("No courses available for filtering.")

        selected_statuses = st.multiselect(
            "Statuses",
            options=["pending", "approved", "flagged", "rejected", "appealed"],
            default=["approved", "flagged", "rejected", "appealed"],
        )

    with col2:
        st.markdown("#### Data Fields")
        if report_type == 'attendance_summary':
            fields = st.multiselect(
                "Include Fields",
                options=['date', 'course', 'session', 'total_records', 'approved', 'flagged', 'rejected', 'attendance_rate'],
                default=['date', 'course', 'session', 'total_records', 'attendance_rate']
            )
        elif report_type == 'student_performance':
            fields = st.multiselect(
                "Include Fields",
                options=['student_name', 'student_email', 'course_code', 'total_checkins', 'approved', 'flagged', 'rejected', 'attendance_rate', 'avg_risk_score'],
                default=['student_name', 'student_email', 'total_checkins', 'attendance_rate']
            )
        elif report_type == 'risk_analysis':
            fields = st.multiselect(
                "Include Fields",
                options=['student_name', 'student_email', 'course_code', 'session_name', 'timestamp', 'status', 'risk_score', 'liveness_score', 'distance_from_venue_meters', 'risk_factors'],
                default=['student_name', 'session_name', 'timestamp', 'status', 'risk_score', 'risk_factors']
            )
        else:
            fields = st.multiselect(
                "Include Fields",
                options=['student_name', 'student_email', 'course_code', 'course_name', 'status', 'enrolled_at'],
                default=['student_name', 'student_email', 'course_code', 'status']
            )

        export_format = st.selectbox(
            "Export Format",
            options=['csv', 'json'],
            format_func=lambda x: {'csv': 'CSV', 'json': 'JSON'}[x],
            key="custom_format"
        )

    st.markdown("---")
    st.markdown("#### Preview")
    st.info("Click 'Generate Report' to preview and download the custom report.")

    def _collect_checkins() -> list[dict]:
        course_ids = [] if "All" in selected_courses else selected_courses
        query_courses = course_ids or [None]
        rows: list[dict] = []
        start_iso = pd.Timestamp(start_date).tz_localize("UTC").isoformat() if start_date else None
        end_iso = pd.Timestamp(end_date).tz_localize("UTC").replace(hour=23, minute=59, second=59).isoformat() if end_date else None

        for course_id in query_courses:
            params: dict[str, object] = {"limit": 200, "offset": 0}
            if course_id:
                params["course_id"] = course_id
            if start_iso:
                params["start_date"] = start_iso
            if end_iso:
                params["end_date"] = end_iso

            offset = 0
            while True:
                params["offset"] = offset
                resp = requests.get(
                    f"{API_BASE_URL}/checkins/",
                    params=params,
                    headers=get_headers(),
                    timeout=15,
                )
                if resp.status_code != 200:
                    break
                payload = resp.json()
                items = extract_items(payload)
                if selected_statuses:
                    items = [i for i in items if i.get("status") in selected_statuses]
                rows.extend(items)
                if len(items) < 200:
                    break
                offset += 200

        return rows

    def _collect_enrollments() -> list[dict]:
        if not courses:
            return []
        course_ids = [str(c["id"]) for c in courses] if "All" in selected_courses else selected_courses
        rows: list[dict] = []
        for course_id in course_ids:
            resp = requests.get(
                f"{API_BASE_URL}/enrollments/course/{course_id}",
                headers=get_headers(),
                timeout=15,
            )
            if resp.status_code != 200:
                continue
            payload = resp.json()
            students = payload.get("students", []) if isinstance(payload, dict) else []
            course_meta = next((c for c in courses if str(c.get("id")) == course_id), {})
            for s in students:
                rows.append(
                    {
                        "student_name": s.get("student_name"),
                        "student_email": s.get("student_email"),
                        "course_code": course_meta.get("code"),
                        "course_name": course_meta.get("name"),
                        "status": s.get("status", "active"),
                        "enrolled_at": s.get("enrolled_at"),
                    }
                )
        return rows

    def _safe_risk_factors(value) -> str:
        if value is None:
            return ""
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        return str(value)

    if st.button("Generate Custom Report", use_container_width=True, key="gen_custom_report"):
        with st.spinner("Generating custom report..."):
            records: list[dict] = []

            if report_type == "enrollment_status":
                records = _collect_enrollments()
            else:
                checkins = _collect_checkins()
                if report_type == "attendance_summary":
                    if checkins:
                        df = pd.DataFrame(checkins)
                        df["date"] = pd.to_datetime(df.get("checked_in_at"), errors="coerce").dt.date.astype(str)
                        grouped = (
                            df.groupby(["date", "course_code", "session_name"], dropna=False)
                            .agg(
                                total_records=("id", "count"),
                                approved=("status", lambda x: int((x == "approved").sum())),
                                flagged=("status", lambda x: int((x.isin(["flagged", "appealed"])).sum())),
                                rejected=("status", lambda x: int((x == "rejected").sum())),
                            )
                            .reset_index()
                        )
                        grouped["attendance_rate"] = grouped.apply(
                            lambda r: (r["approved"] / r["total_records"]) if r["total_records"] else 0, axis=1
                        )
                        grouped.rename(columns={"course_code": "course", "session_name": "session"}, inplace=True)
                        records = grouped.to_dict("records")
                elif report_type == "student_performance":
                    if checkins:
                        df = pd.DataFrame(checkins)
                        grouped = (
                            df.groupby(["student_name", "student_email", "course_code"], dropna=False)
                            .agg(
                                total_checkins=("id", "count"),
                                approved=("status", lambda x: int((x == "approved").sum())),
                                flagged=("status", lambda x: int((x.isin(["flagged", "appealed"])).sum())),
                                rejected=("status", lambda x: int((x == "rejected").sum())),
                                avg_risk_score=("risk_score", "mean"),
                            )
                            .reset_index()
                        )
                        grouped["attendance_rate"] = grouped.apply(
                            lambda r: (r["approved"] / r["total_checkins"]) if r["total_checkins"] else 0, axis=1
                        )
                        records = grouped.to_dict("records")
                else:
                    for row in checkins:
                        records.append(
                            {
                                "student_name": row.get("student_name"),
                                "student_email": row.get("student_email"),
                                "course_code": row.get("course_code"),
                                "session_name": row.get("session_name"),
                                "timestamp": row.get("checked_in_at"),
                                "status": row.get("status"),
                                "risk_score": row.get("risk_score"),
                                "liveness_score": row.get("liveness_score"),
                                "distance_from_venue_meters": row.get("distance_from_venue_meters"),
                                "risk_factors": _safe_risk_factors(row.get("risk_factors")),
                            }
                        )
                    records.sort(key=lambda r: float(r.get("risk_score") or 0), reverse=True)

            if not records:
                st.warning("No data matched the selected filters.")
                return

            df = pd.DataFrame(records)
            if fields:
                selected_cols = [c for c in fields if c in df.columns]
                if selected_cols:
                    df = df[selected_cols]

            st.success(f"Report generated with {len(df)} row(s).")
            st.dataframe(df, use_container_width=True, hide_index=True)

            if export_format == "csv":
                payload = df.to_csv(index=False)
                mime = "text/csv"
            else:
                payload = df.to_json(orient="records", indent=2)
                mime = "application/json"

            st.download_button(
                f"Download {export_format.upper()}",
                payload,
                f"custom_report_{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{export_format}",
                mime,
                use_container_width=True,
            )


if __name__ == "__main__":
    main()

