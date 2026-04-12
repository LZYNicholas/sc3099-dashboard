"""SAIV Instructor Dashboard - Sessions Monitoring Page
"""

import streamlit as st
import streamlit.components.v1 as components
import requests
import pandas as pd
import os
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlencode
from zoneinfo import ZoneInfo
from lib.auth_state import API_BASE_URL, get_auth_headers, require_auth
from lib.response_utils import bool_query, extract_items, fetch_all_items, request_with_retry, response_error, parse_json, friendly_error
from lib.ui_theme import apply_theme

try:
    from st_keyup import st_keyup
except Exception:
    st_keyup = None
try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

# Page configuration

SG_TZ = ZoneInfo("Asia/Singapore")
FRONTEND_BASE_URL = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")
AUTO_REFRESH_SECONDS = 30

def get_headers():
    return get_auth_headers()


def _inject_auto_refresh(seconds: int) -> None:
    if seconds <= 0:
        return
    interval_ms = int(seconds * 1000)
    if st_autorefresh is not None:
        st_autorefresh(interval=interval_ms, key=f"sessions_autorefresh_{seconds}")
        return
    st.caption("Auto-refresh dependency missing; polling is temporarily disabled on this page.")


def get_status_color(status):
    """Get color for status badge"""
    colors = {
        'scheduled': '',
        'active': '',
        'closed': '⚫',
        'completed': '⚫',
        'cancelled': ''
    }
    return colors.get(status, '⚪')


def parse_iso_utc(value):
    if not value:
        return None
    ts = pd.to_datetime(value, errors='coerce')
    if pd.isna(ts):
        return None
    if ts.tzinfo is None:
        return ts.tz_localize(SG_TZ)
    return ts.tz_convert(SG_TZ)


def format_datetime_local(value):
    ts = parse_iso_utc(value)
    if ts is None:
        return 'N/A'
    return ts.strftime('%Y-%m-%d %H:%M SGT')


def get_remaining_qr_ttl(expires_at):
    ts = parse_iso_utc(expires_at)
    if ts is None:
        return 0
    return max(0, int(ts.timestamp() - datetime.now(timezone.utc).timestamp()))


def get_checkin_count(session):
    return session.get('checked_in_count', session.get('checkin_count', 0))


def is_checkin_window_open(session):
    opens_at = parse_iso_utc(session.get('checkin_opens_at'))
    closes_at = parse_iso_utc(session.get('checkin_closes_at'))
    if opens_at is None or closes_at is None:
        return False
    now_sg = pd.Timestamp(datetime.now(SG_TZ))
    return opens_at <= now_sg <= closes_at


def fetch_session_qr(session_id):
    try:
        response, error = request_with_retry(
            "GET",
            f"{API_BASE_URL}/sessions/{session_id}/qr",
            headers=get_headers(),
            timeout=10,
            retries=2,
        )
        if response is None:
            return False, (error or "Failed to fetch QR code")
        if response.status_code == 200:
            payload = parse_json(response)
            if not isinstance(payload, dict):
                return False, 'Failed to fetch QR code'

            qr_payload = payload.get('qr_payload')
            qr_expires_at = payload.get('qr_expires_at') or payload.get('qr_code_expires_at')
            qr_code = payload.get('qr_code')

            if not qr_payload:
                return False, 'QR is not available for this session'

            ttl_seconds = payload.get('qr_ttl_seconds')
            if ttl_seconds is None and qr_expires_at:
                ttl_seconds = get_remaining_qr_ttl(qr_expires_at)

            return True, {
                'qr_payload': qr_payload,
                'qr_expires_at': qr_expires_at,
                'qr_ttl_seconds': ttl_seconds,
                'qr_code': qr_code
            }
        try:
            return False, response.json().get('detail', 'Failed to fetch QR code')
        except Exception:
            return False, 'Failed to fetch QR code'
    except Exception as error:
        return False, str(error)


def parse_qr_session_id(payload: str, fallback_session_id: str) -> str:
    try:
        data = json.loads(payload)
        if isinstance(data, dict) and data.get("sessionId"):
            return str(data["sessionId"])
    except Exception:
        pass
    return fallback_session_id


def build_direct_attendance_link(session_id: str, qr_payload: str | None = None) -> str:
    query_params = {"sessionId": session_id}
    if qr_payload:
        query_params["qr"] = qr_payload
    query = urlencode(query_params)
    return f"{FRONTEND_BASE_URL}/attendance?{query}"


def render_qr_block(qr_data, session_id):
    payload = qr_data.get('qr_payload', '')
    expires_at = qr_data.get('qr_expires_at')
    qr_code_image = qr_data.get('qr_code')

    if expires_at:
        st.caption(f"Available until {format_datetime_local(expires_at)}")

    if qr_code_image:
        st.image(qr_code_image, caption=f"Session QR - {session_id}", width=280)
    else:
        # Try local QR image generation first; fallback to a hosted QR renderer.
        try:
            import qrcode # type: ignore
            qr_img = qrcode.make(payload)
            st.image(qr_img, caption=f"Session QR - {session_id}", width=280)
        except Exception:
            qr_url = f"https://quickchart.io/qr?size=300&text={quote(payload)}"
            st.image(qr_url, caption=f"Session QR - {session_id}", width=280)

    linked_session_id = parse_qr_session_id(payload, session_id)
    attendance_link = build_direct_attendance_link(linked_session_id, payload)
    st.caption("Direct attendance link (equivalent to scanning this QR)")
    st.code(attendance_link)


def session_requires_qr(session) -> bool:
    return bool(session.get('qr_code_enabled'))


def can_manage_qr(role: str) -> bool:
    return role in {'instructor', 'admin'}


def _open_review_queue(session_id: str | None = None, course_id: str | None = None) -> None:
    st.session_state["review_queue_session_id"] = session_id or ""
    st.session_state["review_queue_course_id"] = course_id or ""
    try:
        st.switch_page("pages/6_Reveal_Appeals.py")
    except Exception:
        st.info("Open `Review Appeals` from the sidebar to continue the review flow.")


def _fetch_pending_reviews(limit: int = 200):
    response, error = request_with_retry(
        "GET",
        f"{API_BASE_URL}/checkins/flagged",
        params={"limit": limit},
        headers=get_headers(),
        timeout=10,
        retries=2,
    )
    if response is None:
        return [], (error or "request failed")
    if response.status_code != 200:
        return [], response_error(response)

    payload = parse_json(response) or {}
    if isinstance(payload, dict):
        items = payload.get("items", [])
        if isinstance(items, list):
            return items, None
    if isinstance(payload, list):
        return payload, None
    return [], None


def _submit_quick_review(checkin_id: str, decision: str, note: str = "") -> tuple[bool, str | None]:
    body: dict[str, str] = {"status": decision}
    if note.strip():
        body["review_notes"] = note.strip()

    response, error = request_with_retry(
        "POST",
        f"{API_BASE_URL}/checkins/{checkin_id}/review",
        json=body,
        headers={**get_headers(), "Content-Type": "application/json"},
        timeout=10,
        retries=2,
    )
    if response is None:
        return False, (error or "request failed")
    if response.status_code == 200:
        return True, None
    return False, response_error(response, "Failed to review check-in")


def _update_session_status(session_id: str, status: str) -> tuple[bool, str | None]:
    response, error = request_with_retry(
        "PATCH",
        f"{API_BASE_URL}/sessions/{session_id}",
        json={"status": status},
        headers={**get_headers(), "Content-Type": "application/json"},
        timeout=10,
        retries=2,
    )
    if response is None:
        return False, (error or "request failed")
    if response.status_code == 200:
        return True, None
    return False, response_error(response, f"Failed to set session to {status}")


def _fetch_recent_checkins(*, course_id: str | None, minutes: int = 5, limit: int = 200) -> tuple[list[dict], str | None]:
    now_utc = datetime.now(timezone.utc)
    start_utc = now_utc - timedelta(minutes=minutes)

    params: dict[str, object] = {
        "start_date": start_utc.isoformat().replace("+00:00", "Z"),
        "end_date": now_utc.isoformat().replace("+00:00", "Z"),
        "limit": max(1, min(limit, 200)),
        "offset": 0,
    }
    if course_id:
        params["course_id"] = course_id

    response, error = request_with_retry(
        "GET",
        f"{API_BASE_URL}/checkins/",
        params=params,
        headers=get_headers(),
        timeout=12,
        retries=2,
    )
    if response is None:
        return [], (error or "request failed")
    if response.status_code != 200:
        return [], response_error(response, "Could not load live check-ins")

    payload = parse_json(response)
    if isinstance(payload, dict):
        items = payload.get("items", [])
        return (items if isinstance(items, list) else []), None
    if isinstance(payload, list):
        return payload, None
    return [], None


def main(embedded: bool = False):
    if not embedded:
        require_auth()
    current_role = str((st.session_state.get('user') or {}).get('role', '')).strip().lower()
    if current_role not in {"ta", "instructor", "admin"}:
        st.error("Access denied. This page is restricted to TAs, instructors, and admins.")
        st.stop()

    if not embedded:
        st.title("Session Monitoring")
        st.markdown("Monitor sessions and view check-in details.")
        st.info("For create/edit/status/delete actions, use `Manage` -> `Manage Sessions`.")
    _inject_auto_refresh(AUTO_REFRESH_SECONDS)
    st.caption(f"Auto-refresh enabled every {AUTO_REFRESH_SECONDS}s")

    # Fetch active courses for filter (only show active courses)
    try:
        courses = fetch_all_items(
            f"{API_BASE_URL}/courses/",
            headers=get_headers(),
            params={"is_active": bool_query(True)},
            timeout=10,
            page_size=200,
        )
    except:
        courses = []

    # Track active course IDs for later use
    active_course_ids = {c['id'] for c in courses}

    # Filters row
    col1, col2, col3 = st.columns([3, 2, 1])
    with col1:
        course_filter = st.selectbox(
            "Filter by Course",
            options=['All'] + [c['id'] for c in courses],
            format_func=lambda x: 'All Courses' if x == 'All' else next((f"{c['code']} - {c['name']}" for c in courses if c['id'] == x), x)
        )
    with col2:
        status_filter = st.selectbox(
            "Filter by Status",
            options=['All', 'active', 'scheduled', 'closed', 'cancelled']
        )
    with col3:
        st.markdown("<div style='margin-top:28px'>", unsafe_allow_html=True)
        if st.button("Refresh", use_container_width=True, type="secondary"):
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("---")

    # Fetch sessions
    try:
        is_ta = current_role == 'ta'
        url = f"{API_BASE_URL}/sessions/my-sessions" if is_ta else f"{API_BASE_URL}/sessions/"
        params = {"limit": 200}
        if not is_ta:
            params["offset"] = 0
        if course_filter != 'All':
            params['course_id'] = course_filter

        response, error = request_with_retry(
            "GET",
            url,
            params=params,
            headers=get_headers(),
            timeout=10,
            retries=2,
        )
        if response is None:
            st.error(f"Failed to load sessions: {error or 'request failed'}")
            return

        if response.status_code == 200:
            sessions_data = parse_json(response)
            all_sessions = sessions_data.get('items', []) if isinstance(sessions_data, dict) else sessions_data
            sessions = list(all_sessions)

            # Paginate non-TA listing to avoid truncating at first page.
            if not is_ta and isinstance(sessions_data, dict):
                total = sessions_data.get('total')
                if isinstance(total, int):
                    offset = len(sessions)
                    while offset < total:
                        page_params = dict(params)
                        page_params["offset"] = offset
                        page_response, page_error = request_with_retry(
                            "GET",
                            url,
                            params=page_params,
                            headers=get_headers(),
                            timeout=10,
                            retries=2,
                        )
                        if page_response is None:
                            st.warning(f"Partial session list loaded: {page_error or 'request failed'}")
                            break
                        if page_response.status_code != 200:
                            st.warning(
                                f"Partial session list loaded ({page_response.status_code}): "
                                f"{response_error(page_response)}"
                            )
                            break

                        page_data = parse_json(page_response)
                        page_items = page_data.get('items', []) if isinstance(page_data, dict) else []
                        if not page_items:
                            break
                        sessions.extend(page_items)
                        if len(page_items) < int(page_params["limit"]):
                            break
                        offset += len(page_items)

            pending_reviews, pending_error = _fetch_pending_reviews(limit=200)
            pending_by_session: dict[str, int] = {}
            for item in pending_reviews:
                sid = str(item.get("session_id") or "").strip()
                if sid:
                    pending_by_session[sid] = pending_by_session.get(sid, 0) + 1

            if pending_error:
                st.warning(f"Could not load pending review queue: {pending_error}")
            elif pending_reviews:
                pending_col1, pending_col2 = st.columns([2, 1])
                with pending_col1:
                    st.warning(f"{len(pending_reviews)} check-in(s) need review (flagged/appealed).")
                with pending_col2:
                    if st.button("Open Review Queue", key="open_review_queue_top", use_container_width=True, type="primary"):
                        selected_course_id = None if course_filter == "All" else course_filter
                        _open_review_queue(course_id=selected_course_id)

            # Live pulse for active-session monitoring
            active_session_ids = {
                str(s.get("id") or "").strip()
                for s in sessions
                if str(s.get("status") or "").lower() == "active" and str(s.get("id") or "").strip()
            }
            scoped_course_id = None if course_filter == "All" else str(course_filter)
            recent_checkins, recent_checkins_error = _fetch_recent_checkins(course_id=scoped_course_id, minutes=5, limit=200)
            if active_session_ids:
                recent_checkins = [
                    ci for ci in recent_checkins
                    if str((ci or {}).get("session_id") or "").strip() in active_session_ids
                ]

            status_counts = {"approved": 0, "flagged": 0, "rejected": 0}
            latest_checkin_dt = None
            for ci in recent_checkins:
                status_value = str((ci or {}).get("status") or "").strip().lower()
                if status_value in status_counts:
                    status_counts[status_value] += 1
                ts = parse_iso_utc((ci or {}).get("checked_in_at"))
                if ts is not None and (latest_checkin_dt is None or ts > latest_checkin_dt):
                    latest_checkin_dt = ts

            total_live = len(recent_checkins)

            pulse_by_session: dict[str, dict[str, object]] = {}
            for ci in recent_checkins:
                sid = str((ci or {}).get("session_id") or "").strip()
                if not sid:
                    continue
                if sid not in pulse_by_session:
                    pulse_by_session[sid] = {
                        "total": 0,
                        "approved": 0,
                        "flagged": 0,
                        "rejected": 0,
                        "latest": None,
                    }
                bucket = pulse_by_session[sid]
                bucket["total"] = int(bucket["total"]) + 1
                status_value = str((ci or {}).get("status") or "").strip().lower()
                if status_value in {"approved", "flagged", "rejected"}:
                    bucket[status_value] = int(bucket[status_value]) + 1

                ts = parse_iso_utc((ci or {}).get("checked_in_at"))
                if ts is not None:
                    cur_latest = bucket.get("latest")
                    if cur_latest is None or ts > cur_latest:
                        bucket["latest"] = ts

            if scoped_course_id:
                scoped_pending_reviews = [
                    item for item in pending_reviews
                    if str((item or {}).get("course_id") or "").strip() == scoped_course_id
                ]
            else:
                scoped_pending_reviews = pending_reviews
            review_queue_size = len(scoped_pending_reviews)

            if recent_checkins_error:
                st.caption(f"Live pulse warning: {recent_checkins_error}")

            # Apply status filter
            if status_filter != 'All':
                sessions = [s for s in sessions if s.get('status') == status_filter]

            if not sessions:
                st.info("No sessions found matching the filters.")
                return

            # Check for sessions with deleted courses
            sessions_with_deleted_courses = [s for s in sessions if s.get('course_id') not in active_course_ids]
            if sessions_with_deleted_courses:
                st.warning(f"⚠️ {len(sessions_with_deleted_courses)} session(s) belong to deleted courses and cannot accept check-ins.")

            # Scheduled Sessions Section
            scheduled_sessions = [s for s in sessions if s.get('status') == 'scheduled']
            st.subheader(f"Scheduled Sessions ({len(scheduled_sessions)})")
            if scheduled_sessions:
                sched_col1, sched_col2 = st.columns([3, 1])
                with sched_col1:
                    st.caption("Sessions awaiting activation.")
                with sched_col2:
                    st.markdown("<div style='margin-top:8px'>", unsafe_allow_html=True)
                    if st_keyup is not None:
                        sched_search = st_keyup(
                            "Search scheduled",
                            placeholder="Filter by name or course...",
                            key="sched_search_live"
                        )
                    else:
                        sched_search = st.text_input(
                            "Search scheduled",
                            placeholder="Filter by name or course...",
                            label_visibility="collapsed",
                            key="sched_search"
                        )
                    st.markdown("</div>", unsafe_allow_html=True)

                filtered_scheduled = scheduled_sessions
                if sched_search:
                    q = sched_search.lower()
                    filtered_scheduled = [
                        s for s in scheduled_sessions
                        if q in s.get('name', '').lower() or q in s.get('course_name', '').lower()
                    ]

                if not filtered_scheduled:
                    st.info("No scheduled sessions match your search.")
                else:
                    for session in filtered_scheduled:
                        course_deleted = session.get('course_id') not in active_course_ids
                        title_suffix = " ⚠️ [COURSE DELETED]" if course_deleted else ""
                        with st.expander(f"**{session.get('name', 'Session')}** - {session.get('course_name', 'Course')}{title_suffix}", expanded=False):
                            if course_deleted:
                                st.error("⚠️ This session's course has been deleted.")

                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.write(f"**Type:** {session.get('session_type', 'N/A')}")
                                st.write(f"**Start:** {format_datetime_local(session.get('scheduled_start'))}")
                            with col2:
                                st.write(f"**End:** {format_datetime_local(session.get('scheduled_end'))}")
                                st.write(f"**Location:** {session.get('venue_name', session.get('location', 'N/A'))}")
                            with col3:
                                st.metric("Check-ins", get_checkin_count(session))

                            action_col1, action_col2 = st.columns([1, 2])
                            with action_col1:
                                can_activate = not course_deleted
                                if st.button(
                                    "Activate",
                                    key=f"activate_scheduled_{session.get('id')}",
                                    type="primary",
                                    use_container_width=True,
                                    disabled=not can_activate,
                                ):
                                    ok, err = _update_session_status(str(session.get("id") or ""), "active")
                                    if ok:
                                        st.success("Session activated.")
                                        st.rerun()
                                    else:
                                        st.error(err or "Failed to activate session.")
                            with action_col2:
                                if course_deleted:
                                    st.caption("Cannot activate: parent course is deleted.")
                                else:
                                    st.caption("Activate to open check-in controls and QR actions in this view.")

                            # Keep card concise in unified statistics view.

                st.markdown("---")
            else:
                st.info("No sessions scheduled.")

            # Active Sessions Section
            active_sessions = [s for s in sessions if s.get('status') == 'active']
            st.subheader(f"Active Sessions ({len(active_sessions)})")
            if active_sessions:
                open_now_sessions = [s for s in active_sessions if is_checkin_window_open(s)]
                stale_active_sessions = [s for s in active_sessions if not is_checkin_window_open(s)]

                st.caption(f"{len(open_now_sessions)} open now / {len(active_sessions)} status-active")

                if stale_active_sessions:
                    st.warning(
                        f"{len(stale_active_sessions)} session(s) are marked active but their check-in window is closed. "
                        "Close them to keep this list clean."
                    )

                for session in active_sessions:
                    course_deleted = session.get('course_id') not in active_course_ids
                    title_suffix = " ⚠️ [COURSE DELETED]" if course_deleted else ""
                    window_open = is_checkin_window_open(session)
                    window_suffix = " (Open Now)" if window_open else " (Window Closed)"

                    with st.expander(f"**{session.get('name', 'Session')}** - {session.get('course_name', 'Course')}{title_suffix}{window_suffix}", expanded=window_open):
                        if course_deleted:
                            st.error("⚠️ This session's course has been deleted. Check-ins may not work properly.")
                        elif not window_open:
                            st.warning("Check-in window is currently closed for this active session.")

                        session_id_str = str(session.get("id") or "").strip()
                        session_pulse = pulse_by_session.get(
                            session_id_str,
                            {"total": 0, "approved": 0, "flagged": 0, "rejected": 0, "latest": None},
                        )
                        session_total = int(session_pulse.get("total", 0) or 0)
                        session_approved = int(session_pulse.get("approved", 0) or 0)
                        session_flagged = int(session_pulse.get("flagged", 0) or 0)
                        session_rejected = int(session_pulse.get("rejected", 0) or 0)
                        session_approval_rate = (session_approved / session_total * 100.0) if session_total else 0.0
                        session_latest = session_pulse.get("latest")
                        st.markdown("##### Live Pulse (last 5m)")
                        s_p1, s_p2, s_p3, s_p4, s_p5 = st.columns(5)
                        s_p1.metric("Check-ins (5m)", session_total)
                        s_p2.metric(
                            "Approved / Flagged / Rejected",
                            f"{session_approved} / {session_flagged} / {session_rejected}",
                        )
                        s_p3.metric("Approval Rate", f"{session_approval_rate:.1f}%")
                        s_p4.metric(
                            "Last Check-in (SGT)",
                            session_latest.strftime("%H:%M:%S") if session_latest is not None else "N/A",
                        )
                        s_p5.metric("Review Queue", pending_by_session.get(session_id_str, 0))

                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.write(f"**Type:** {session.get('session_type', 'N/A')}")
                            st.write(f"**Start:** {format_datetime_local(session.get('scheduled_start'))}")
                        with col2:
                            st.write(f"**End:** {format_datetime_local(session.get('scheduled_end'))}")
                            st.write(f"**Location:** {session.get('venue_name', session.get('location', 'N/A'))}")
                        with col3:
                            # Quick stats for this session
                            st.metric("Check-ins", get_checkin_count(session))

                        # Keep card concise in unified statistics view.
                        pending_for_session = pending_by_session.get(str(session.get("id") or ""), 0)
                        if pending_for_session > 0:
                            review_col1, review_col2 = st.columns([2, 1])
                            with review_col1:
                                st.warning(f"{pending_for_session} check-in(s) in this session need review.")
                            with review_col2:
                                if st.button("Review This Session", key=f"review_session_{session['id']}", use_container_width=True):
                                    _open_review_queue(
                                        session_id=str(session.get("id") or ""),
                                        course_id=str(session.get("course_id") or ""),
                                    )

                            quick_review_open = st.checkbox(
                                "Quick review here",
                                value=False,
                                key=f"quick_review_toggle_{session['id']}",
                            )
                            if quick_review_open:
                                session_pending = [
                                    item for item in pending_reviews
                                    if str(item.get("session_id") or "") == str(session.get("id") or "")
                                ]
                                session_pending = sorted(
                                    session_pending,
                                    key=lambda item: float(item.get("risk_score") or 0.0),
                                    reverse=True,
                                )[:5]

                                st.caption("Top pending items for this session (highest risk first).")
                                for idx, item in enumerate(session_pending):
                                    checkin_id = str(item.get("id") or "").strip()
                                    if not checkin_id:
                                        continue
                                    student_name = str(item.get("student_name") or "Unknown Student")
                                    status_value = str(item.get("status") or "flagged")
                                    risk_value = float(item.get("risk_score") or 0.0)
                                    checked_in_at = format_datetime_local(item.get("checked_in_at") or item.get("timestamp"))

                                    st.markdown(
                                        f"**{student_name}** | `{status_value}` | Risk `{risk_value:.2f}` | {checked_in_at or 'N/A'}"
                                    )
                                    note = st.text_input(
                                        "Review note (optional)",
                                        key=f"quick_review_note_{session['id']}_{checkin_id}_{idx}",
                                        placeholder="Optional reviewer note",
                                    )
                                    act_col1, act_col2 = st.columns(2)
                                    with act_col1:
                                        if st.button(
                                            "Approve",
                                            key=f"quick_review_approve_{session['id']}_{checkin_id}_{idx}",
                                            type="primary",
                                            use_container_width=True,
                                        ):
                                            ok, err = _submit_quick_review(checkin_id, "approved", note)
                                            if ok:
                                                st.success(f"Approved check-in for {student_name}.")
                                                st.rerun()
                                            else:
                                                st.error(err or "Failed to approve check-in.")
                                    with act_col2:
                                        if st.button(
                                            "Reject",
                                            key=f"quick_review_reject_{session['id']}_{checkin_id}_{idx}",
                                            use_container_width=True,
                                        ):
                                            ok, err = _submit_quick_review(checkin_id, "rejected", note)
                                            if ok:
                                                st.warning(f"Rejected check-in for {student_name}.")
                                                st.rerun()
                                            else:
                                                st.error(err or "Failed to reject check-in.")
                                    st.markdown("---")

                        if window_open:
                            st.markdown("#### Session QR")
                            if not can_manage_qr(current_role):
                                st.info("QR display is restricted to instructor and admin roles.")
                            elif not session_requires_qr(session):
                                st.caption("QR check-in is disabled for this session. Students can submit attendance directly from the attendance page.")
                                direct_link = build_direct_attendance_link(session['id'])
                                st.caption("Direct attendance link (for testing)")
                                st.code(direct_link)
                            else:
                                state_key = f"session_qr_{session['id']}"
                                qr_payload = st.session_state.get(state_key)

                                btn_col1, btn_col2 = st.columns([1, 3])
                                with btn_col1:
                                    button_label = "Show QR" if qr_payload else "Generate QR"
                                    if st.button(
                                        button_label,
                                        key=f"qr_btn_{session['id']}",
                                        use_container_width=True
                                    ):
                                        ok, result = fetch_session_qr(session['id'])
                                        if ok:
                                            qr_payload = result
                                            st.session_state[state_key] = result
                                        else:
                                            st.error(result or "Could not generate QR")
                                with btn_col2:
                                    st.caption("Display the session QR while the check-in window is open.")

                                if qr_payload:
                                    render_qr_block(qr_payload, session['id'])
                                else:
                                    st.caption("No QR has been issued for this session yet.")

                        show_checkins = st.checkbox(
                            "Show Check-ins",
                            value=False,
                            key=f"show_checkins_{session['id']}",
                        )
                        if show_checkins:
                            show_session_checkins(session['id'])

                st.markdown("---")
            else:
                st.info("No active sessions.")

            st.subheader("All Sessions Table / Export")
            display_data = []
            for s in sessions:
                course_deleted = s.get('course_id') not in active_course_ids
                course_display = s.get('course_name', s.get('course_code', 'N/A'))
                if course_deleted:
                    course_display = f"{course_display} [DELETED]"

                display_data.append({
                    'Status': f"{get_status_color(s.get('status', ''))} {s.get('status', 'unknown').title()}",
                    'Name': s.get('name', 'N/A'),
                    'Course': course_display,
                    'Type': s.get('session_type', 'N/A'),
                    'Scheduled Start': format_datetime_local(s.get('scheduled_start')),
                    'Check-ins': get_checkin_count(s),
                    'ID': s.get('id', '')
                })

            df = pd.DataFrame(display_data)
            st.dataframe(df.drop(columns=['ID']), use_container_width=True, hide_index=True)

            sessions_csv = df.drop(columns=['ID']).to_csv(index=False)
            st.download_button(
                "Download Sessions CSV",
                sessions_csv,
                "all_sessions.csv",
                "text/csv",
                use_container_width=True,
                key="csv_export_all_sessions",
            )

            st.markdown("---")
            if current_role in {"instructor", "admin"} and not embedded:
                st.caption("Use the `Check-ins` page from the sidebar for global cross-session exploration and exports.")

        else:
            st.error(response_error(response, "Couldn't load sessions right now."))

    except Exception as e:
        st.error(friendly_error(e, "Couldn't load sessions right now."))


def show_session_checkins(session_id):
    """Display check-ins for a session"""
    try:
        response, error = request_with_retry(
            "GET",
            f"{API_BASE_URL}/checkins/session/{session_id}",
            headers=get_headers(),
            timeout=10,
            retries=2,
        )
        if response is None:
            st.warning(friendly_error(error, "Couldn't load check-ins right now."))
            return

        if response.status_code == 200:
            checkins = parse_json(response)
            if isinstance(checkins, dict):
                checkins = checkins.get('items', checkins.get('records', []))
            if checkins:
                st.markdown("#### Check-ins")
                for ci in checkins:
                    col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
                    with col1:
                        st.write(f"**{ci.get('student_name', 'Unknown')}**")
                    with col2:
                        st.write(format_datetime_local(ci.get('checked_in_at', ci.get('timestamp'))))
                    with col3:
                        st.write(f"Risk: {ci.get('risk_score', 0):.2f}")
                    with col4:
                        st.write(ci.get('status', ''))

                # CSV export for gradebook
                export_rows = []
                for ci in checkins:
                    export_rows.append({
                        'Check-in ID': ci.get('id', ''),
                        'Student ID': ci.get('student_id', ''),
                        'Student Name': ci.get('student_name', ''),
                        'Student Email': ci.get('student_email', ''),
                        'Session ID': ci.get('session_id', session_id),
                        'Timestamp': ci.get('checked_in_at', ci.get('timestamp', '')),
                        'Status': ci.get('status', ''),
                        'Risk Score': ci.get('risk_score', ''),
                        'Liveness Score': ci.get('liveness_score', ''),
                        'Face Match Score': ci.get('face_match_score', ''),
                    })
                csv_data = pd.DataFrame(export_rows).to_csv(index=False)
                st.download_button(
                    "Download Check-ins CSV (Gradebook)",
                    csv_data,
                    f"session_{session_id}_checkins.csv",
                    "text/csv",
                    use_container_width=True,
                    key=f"csv_export_{session_id}",
                )

                st.markdown("#### Check-in Detail")
                checkin_options = {
                    f"{ci.get('student_name', 'Unknown')} - {ci.get('id', 'N/A')}": ci.get('id')
                    for ci in checkins
                    if ci.get('id')
                }
                if checkin_options:
                    selected_checkin_label = st.selectbox(
                        "Select check-in",
                        options=list(checkin_options.keys()),
                        key=f"checkin_detail_select_{session_id}"
                    )
                    selected_checkin_id = checkin_options[selected_checkin_label]
                    if st.button("Load Check-in Detail", key=f"load_checkin_detail_{session_id}"):
                        detail_response, detail_error = request_with_retry(
                            "GET",
                            f"{API_BASE_URL}/checkins/{selected_checkin_id}",
                            headers=get_headers(),
                            timeout=10,
                            retries=2,
                        )
                        if detail_response is None:
                            st.warning(friendly_error(detail_error, "Couldn't load check-in details right now."))
                            return
                        if detail_response.status_code == 200:
                            detail = parse_json(detail_response)
                            st.json(detail)
                            # ...existing code...
                        else:
                            st.warning(response_error(detail_response, "Couldn't load check-in details right now."))
            else:
                st.info("No check-ins yet.")
        else:
            st.warning("Could not load check-ins.")

    except Exception as e:
        st.warning(friendly_error(e, "Couldn't load check-ins right now."))


def show_session_details(session_id, sessions, active_course_ids=None):
    """Display detailed session information"""
    session = next((s for s in sessions if s['id'] == session_id), None)
    if not session:
        return

    try:
        session_detail_response, _error = request_with_retry(
            "GET",
            f"{API_BASE_URL}/sessions/{session_id}",
            headers=get_headers(),
            timeout=10,
            retries=2,
        )
        if session_detail_response is not None and session_detail_response.status_code == 200:
            session_detail = parse_json(session_detail_response)
            if isinstance(session_detail, dict):
                session = {**session, **session_detail}
    except Exception:
        pass

    # Check if course is deleted
    if active_course_ids is None:
        active_course_ids = set()
    course_deleted = session.get('course_id') not in active_course_ids

    if course_deleted:
        st.error("⚠️ This session's course has been deleted. The session cannot accept new check-ins.")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Session Information")
        st.write(f"**Name:** {session.get('name', 'N/A')}")
        st.write(f"**Type:** {session.get('session_type', 'N/A')}")
        st.write(f"**Status:** {get_status_color(session.get('status', ''))} {session.get('status', 'unknown').title()}")
        st.write(f"**Location:** {session.get('venue_name', session.get('location', 'Not specified'))}")

    with col2:
        st.markdown("#### Timing")
        st.write(f"**Scheduled Start:** {format_datetime_local(session.get('scheduled_start'))}")
        st.write(f"**Scheduled End:** {format_datetime_local(session.get('scheduled_end'))}")
        st.write(f"**Check-in Opens:** {format_datetime_local(session.get('checkin_opens_at'))}")
        st.write(f"**Check-in Closes:** {format_datetime_local(session.get('checkin_closes_at'))}")
        if session.get('actual_start'):
            st.write(f"**Actual Start:** {format_datetime_local(session.get('actual_start'))}")
        if session.get('actual_end'):
            st.write(f"**Actual End:** {format_datetime_local(session.get('actual_end'))}")

    # Fetch session statistics
    try:
        stats_response, stats_error = request_with_retry(
            "GET",
            f"{API_BASE_URL}/stats/sessions/{session_id}",
            headers=get_headers(),
            timeout=10,
            retries=2,
        )
        if stats_response is None:
            st.warning(friendly_error(stats_error, "Couldn't load session statistics right now."))
            return

        if stats_response.status_code == 200:
            stats = parse_json(stats_response) or {}

            st.markdown("---")
            st.markdown("#### Statistics")

            col1, col2, col3, col4 = st.columns(4)
            by_status = stats.get('by_status', {}) if isinstance(stats.get('by_status'), dict) else {}
            with col1:
                st.metric("Total Check-ins", stats.get('total_checkins', stats.get('checked_in_count', stats.get('checked_in', 0))))
            with col2:
                st.metric("Approved", stats.get('approved_count', by_status.get('approved', 0)))
            with col3:
                st.metric("Rejected", by_status.get('rejected', 0))
            with col4:
                st.metric("Flagged", stats.get('flagged_count', 0))

    except Exception as e:
        st.warning(friendly_error(e, "Couldn't load session statistics right now."))

    # Check-ins Table
    st.markdown("---")
    st.markdown("#### Check-in Records")
    show_session_checkins(session_id)



