"""SAIV Dashboard - Course & Session Management
Create and manage courses and sessions for attendance
"""

import streamlit as st
import streamlit.components.v1 as components
import requests
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from lib.auth_state import API_BASE_URL, get_auth_headers, require_auth
from lib.response_utils import bool_query, extract_items, response_error as shared_response_error, friendly_error
from lib.ui_theme import apply_theme

# Page configuration
st.set_page_config(page_title="Manage - SAIV", layout="wide", initial_sidebar_state="expanded")
apply_theme()

require_auth()

# API Configuration
SG_TZ = ZoneInfo("Asia/Singapore")
_API_GET_CACHE: dict[tuple[str, tuple[tuple[str, str], ...], str], requests.Response | None] = {}


def to_api_datetime(value: datetime) -> str:
    # Always send timezone-aware Singapore timestamps to backend.
    if value.tzinfo is None:
        value = value.replace(tzinfo=SG_TZ)
    else:
        value = value.astimezone(SG_TZ)
    return value.isoformat()

def get_headers():
    headers = get_auth_headers()
    headers["Content-Type"] = "application/json"
    return headers

def clear_api_cache() -> None:
    _API_GET_CACHE.clear()

def api_post(endpoint: str, data: dict):
    """Make POST request to API"""
    try:
        response = requests.post(
            f"{API_BASE_URL}{endpoint}",
            json=data,
            headers=get_headers(),
            timeout=10
        )
        clear_api_cache()
        return response
    except Exception as e:
        st.error(friendly_error(e, "We couldn't connect to the server. Please try again."))
        return None

def api_get(endpoint: str, params: dict = None):
    """Make GET request to API"""
    cache_key: tuple[str, tuple[tuple[str, str], ...], str] | None = None
    try:
        query_params = None
        if params is not None:
            query_params = {
                k: bool_query(v) if isinstance(v, bool) else v
                for k, v in params.items()
            }
        auth_header = get_headers().get("Authorization", "")
        cache_key = (
            endpoint,
            tuple(sorted((str(k), str(v)) for k, v in (query_params or {}).items())),
            auth_header,
        )
        if cache_key in _API_GET_CACHE:
            return _API_GET_CACHE[cache_key]

        response = requests.get(
            f"{API_BASE_URL}{endpoint}",
            params=query_params,
            headers=get_headers(),
            timeout=10
        )
        _API_GET_CACHE[cache_key] = response
        return response
    except Exception as e:
        st.error(friendly_error(e, "We couldn't connect to the server. Please try again."))
        if cache_key is not None:
            _API_GET_CACHE[cache_key] = None
        return None


def fetch_all_courses(is_active: bool | None = None, page_size: int = 200) -> list[dict]:
    items: list[dict] = []
    offset = 0

    while True:
        params: dict[str, object] = {"limit": page_size, "offset": offset}
        if is_active is not None:
            params["is_active"] = is_active

        response = api_get("/courses/", params)
        if response is None or response.status_code != 200:
            break

        page_items = response_items(response)
        if not page_items:
            break

        items.extend(page_items)

        try:
            payload = response.json()
        except Exception:
            payload = None

        if isinstance(payload, dict):
            total = payload.get("total")
            if isinstance(total, int) and len(items) >= total:
                break

        if len(page_items) < page_size:
            break

        offset += page_size

    return items

def fetch_all_sessions(page_size: int = 200, filters: dict[str, object] | None = None) -> list[dict]:
    items: list[dict] = []
    offset = 0
    base_filters = dict(filters or {})

    while True:
        params: dict[str, object] = {**base_filters, "limit": page_size, "offset": offset}
        response = api_get("/sessions/", params)
        if response is None or response.status_code != 200:
            break

        page_items = response_items(response)
        if not page_items:
            break

        items.extend(page_items)

        try:
            payload = response.json()
        except Exception:
            payload = None

        if isinstance(payload, dict):
            total = payload.get("total")
            if isinstance(total, int) and len(items) >= total:
                break

        if len(page_items) < page_size:
            break

        offset += page_size

    return items

def fetch_all_users(filters: dict[str, object] | None = None, page_size: int = 100) -> tuple[list[dict], str | None]:
    items: list[dict] = []
    offset = 0
    safe_page_size = max(1, min(int(page_size), 100))
    base_filters = dict(filters or {})

    while True:
        params: dict[str, object] = {**base_filters, "limit": safe_page_size, "offset": offset}
        response = api_get("/users/", params)
        if response is None:
            return [], "Failed to connect to server"
        if response.status_code != 200:
            return [], response_error(response, "Failed to load users")

        page_items = response_items(response)
        if not page_items:
            break

        items.extend(page_items)

        try:
            payload = response.json()
        except Exception:
            payload = None

        if isinstance(payload, dict):
            total = payload.get("total")
            if isinstance(total, int) and len(items) >= total:
                break

        if len(page_items) < safe_page_size:
            break

        offset += safe_page_size

    return items, None

def api_patch(endpoint: str, data: dict):
    """Make PATCH request to API"""
    try:
        response = requests.patch(
            f"{API_BASE_URL}{endpoint}",
            json=data,
            headers=get_headers(),
            timeout=10
        )
        clear_api_cache()
        return response
    except Exception as e:
        st.error(friendly_error(e, "We couldn't connect to the server. Please try again."))
        return None

def api_put(endpoint: str, data: dict):
    """Make PUT request to API"""
    try:
        response = requests.put(
            f"{API_BASE_URL}{endpoint}",
            json=data,
            headers=get_headers(),
            timeout=10
        )
        clear_api_cache()
        return response
    except Exception as e:
        st.error(friendly_error(e, "We couldn't connect to the server. Please try again."))
        return None


def api_delete(endpoint: str):
    """Make DELETE request to API"""
    try:
        headers = {}
        auth = get_auth_headers().get("Authorization")
        if auth:
            headers["Authorization"] = auth
        response = requests.delete(
            f"{API_BASE_URL}{endpoint}",
            headers=headers,
            timeout=10
        )
        clear_api_cache()
        return response
    except Exception as e:
        st.error(friendly_error(e, "We couldn't connect to the server. Please try again."))
        return None


def response_items(response: requests.Response):
    try:
        return extract_items(response.json())
    except Exception:
        return []


def response_error(response: requests.Response | None, fallback: str = "Unknown error") -> str:
    return shared_response_error(response, fallback)


def fetch_active_instructors() -> tuple[list[dict], str | None]:
    users, users_error = fetch_all_users({"role": "instructor", "is_active": True}, page_size=100)
    if users_error:
        return [], users_error

    instructors = []
    for user in users:
        user_id = str(user.get("id") or "").strip()
        if not user_id:
            continue
        full_name = str(user.get("full_name") or "Unnamed Instructor").strip()
        email = str(user.get("email") or "").strip()
        label = f"{full_name} ({email})" if email else full_name
        instructors.append({
            "id": user_id,
            "label": label,
        })

    instructors.sort(key=lambda item: item["label"].lower())
    return instructors, None


def _safe_float(value, default: float) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _parse_api_datetime(value, fallback: datetime) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        raw = value.strip()
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            return fallback
    else:
        return fallback

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=SG_TZ)
    return parsed.astimezone(SG_TZ)


_GEO_PARAM_TARGET = "__geo_target"
_GEO_PARAM_STATUS = "__geo_status"
_GEO_PARAM_LAT = "__geo_lat"
_GEO_PARAM_LON = "__geo_lon"
_GEO_PARAM_MESSAGE = "__geo_message"
_GEO_EVENT_KEY = "_geo_event"
_GEO_PENDING_CREATE_SESSION_COURSE_ID = "_geo_pending_create_session_course_id"
_GEO_PENDING_MANAGE_SESSION_ID = "_geo_pending_manage_session_id"
_GEO_PENDING_EDIT_COURSE_ID = "_geo_pending_edit_course_id"
_PENDING_MANAGE_SESSION_SELECTION = "_pending_manage_session_selection"


def _geo_target_to_section(target: str) -> str | None:
    normalized = str(target or "").strip().lower()
    if normalized.startswith("create_session_"):
        return "Create Session"
    if normalized.startswith("edit_session_"):
        return "Manage Sessions"
    if normalized.startswith("create_course"):
        return "Create Course"
    if normalized.startswith("edit_course_"):
        return "Manage Course"
    return None


def _consume_geolocation_event() -> None:
    query_params = st.query_params
    target = query_params.get(_GEO_PARAM_TARGET)
    if not target:
        return

    status = str(query_params.get(_GEO_PARAM_STATUS, "error")).strip().lower() or "error"
    message = str(query_params.get(_GEO_PARAM_MESSAGE, "")).strip()
    lat_raw = query_params.get(_GEO_PARAM_LAT)
    lon_raw = query_params.get(_GEO_PARAM_LON)

    event: dict[str, object] = {"target": str(target), "status": status, "message": message}
    if status == "success":
        try:
            event["lat"] = float(lat_raw)
            event["lon"] = float(lon_raw)
        except Exception:
            event["status"] = "error"
            event["message"] = "We couldn't read your current coordinates from the browser."

    st.session_state[_GEO_EVENT_KEY] = event
    normalized_target = str(target).strip().lower()
    if normalized_target.startswith("create_session_"):
        pending_course_id = str(target).split("create_session_", 1)[1].strip()
        if pending_course_id:
            st.session_state[_GEO_PENDING_CREATE_SESSION_COURSE_ID] = pending_course_id
    elif normalized_target.startswith("edit_session_"):
        pending_session_id = str(target).split("edit_session_", 1)[1].strip()
        if pending_session_id:
            st.session_state[_GEO_PENDING_MANAGE_SESSION_ID] = pending_session_id
    elif normalized_target.startswith("edit_course_"):
        pending_edit_course_id = str(target).split("edit_course_", 1)[1].strip()
        if pending_edit_course_id:
            st.session_state[_GEO_PENDING_EDIT_COURSE_ID] = pending_edit_course_id
    target_section = _geo_target_to_section(str(target))
    if target_section:
        st.session_state["manage_active_section"] = target_section
        st.session_state["manage_section_control"] = target_section
        st.session_state["manage_section_control_fallback"] = target_section
    for param_key in (
        _GEO_PARAM_TARGET,
        _GEO_PARAM_STATUS,
        _GEO_PARAM_LAT,
        _GEO_PARAM_LON,
        _GEO_PARAM_MESSAGE,
    ):
        if param_key in query_params:
            del query_params[param_key]


def _apply_geolocation_to_fields(target: str, lat_key: str, lon_key: str) -> None:
    event = st.session_state.get(_GEO_EVENT_KEY)
    if not isinstance(event, dict):
        return
    if str(event.get("target")) != str(target):
        return

    if event.get("status") == "success":
        st.session_state[lat_key] = float(event.get("lat"))
        st.session_state[lon_key] = float(event.get("lon"))
        st.success("Latitude and longitude were updated.")
    else:
        message = str(event.get("message") or "Location access was not granted.")
        st.warning(f"Couldn't use current location: {message}")

    st.session_state.pop(_GEO_EVENT_KEY, None)


def _number_input_with_state_default(label: str, key: str, default: float, **kwargs):
    if key not in st.session_state:
        st.session_state[key] = default
    return st.number_input(label, key=key, **kwargs)


def _text_input_with_state_default(label: str, key: str, default: str, **kwargs):
    if key not in st.session_state:
        st.session_state[key] = default
    return st.text_input(label, key=key, **kwargs)


def render_map_marker_picker(target: str, lat_key: str, lon_key: str, initial_lat: float, initial_lon: float) -> None:
    _apply_geolocation_to_fields(target, lat_key, lon_key)
    lat = _safe_float(st.session_state.get(lat_key), initial_lat)
    lon = _safe_float(st.session_state.get(lon_key), initial_lon)
    st.caption("Pick a location on the map. Drag marker or click map, then apply.")
    components.html(
        f"""
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <style>
          #map-{target} {{ height: 270px; width: 100%; border-radius: 8px; border: 1px solid #d0d5dd; }}
          .map-controls-{target} {{ margin-top: 8px; display: flex; gap: 8px; align-items: center; }}
          .map-coord-{target} {{ font-size: 0.82rem; color: #667085; }}
          .map-btn-{target} {{ background:#0f6fb2;color:white;border:none;border-radius:8px;padding:8px 12px;font-size:0.9rem;cursor:pointer; }}
        </style>
        <div id="map-{target}"></div>
        <div class="map-controls-{target}">
          <button type="button" id="map-apply-{target}" class="map-btn-{target}">Use Marker Coordinates</button>
          <span id="map-coord-{target}" class="map-coord-{target}"></span>
        </div>
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <script>
        (function () {{
          const target = {json.dumps(target)};
          const initialLat = Number({json.dumps(lat)});
          const initialLon = Number({json.dumps(lon)});
          const mapEl = document.getElementById("map-" + target);
          const coordEl = document.getElementById("map-coord-" + target);
          const applyBtn = document.getElementById("map-apply-" + target);
          if (!mapEl || !applyBtn || !window.L) return;
          const finish = (lat, lon) => {{
            const url = new URL(window.parent.location.href);
            url.searchParams.set({_GEO_PARAM_TARGET!r}, target);
            url.searchParams.set({_GEO_PARAM_STATUS!r}, "success");
            url.searchParams.set({_GEO_PARAM_LAT!r}, String(lat));
            url.searchParams.set({_GEO_PARAM_LON!r}, String(lon));
            url.searchParams.delete({_GEO_PARAM_MESSAGE!r});
            window.parent.history.replaceState({{}}, "", url.toString());
            window.parent.location.reload();
          }};
          const map = L.map(mapEl).setView([initialLat, initialLon], 15);
          L.tileLayer("https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{ maxZoom: 19, attribution: "&copy; OpenStreetMap contributors" }}).addTo(map);
          const marker = L.marker([initialLat, initialLon], {{ draggable: true }}).addTo(map);
          const setMarkerPosition = (lat, lon, zoom=16) => {{
            marker.setLatLng([lat, lon]);
            map.setView([lat, lon], zoom);
            renderCoords();
          }};
          const renderCoords = () => {{
            const pos = marker.getLatLng();
            coordEl.textContent = `Lat: ${{pos.lat.toFixed(6)}}, Lon: ${{pos.lng.toFixed(6)}}`;
          }};
          renderCoords();
          marker.on("dragend", renderCoords);
          map.on("click", (e) => {{ marker.setLatLng(e.latlng); renderCoords(); }});
          applyBtn.addEventListener("click", () => {{
            const pos = marker.getLatLng();
            finish(pos.lat, pos.lng);
          }});
          if (navigator.geolocation) {{
            navigator.geolocation.getCurrentPosition(
              (position) => {{
                setMarkerPosition(position.coords.latitude, position.coords.longitude, 17);
              }},
              () => {{
                // Keep existing initial coordinates if permission denied/unavailable.
              }},
              {{ enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }}
            );
          }}
        }})();
        </script>
        """,
        height=330,
    )


def render_current_location_picker(target: str, lat_key: str, lon_key: str) -> None:
    _apply_geolocation_to_fields(target, lat_key, lon_key)
    st.caption("Use your browser location permissions to auto-fill current latitude and longitude.")
    components.html(
        f"""
        <div style="display:flex;align-items:center;gap:8px;">
          <button id="geo-btn-{target}" style="background:#0f6fb2;color:white;border:none;border-radius:8px;padding:8px 12px;font-size:0.9rem;cursor:pointer;">
            Use Current Coordinates
          </button>
          <span style="font-size:0.82rem;color:#667085;">Permission prompt appears in your browser.</span>
        </div>
        <script>
        (function () {{
          const target = {json.dumps(target)};
          const button = document.getElementById("geo-btn-" + target);
          if (!button) return;
          const finish = (status, message, lat, lon) => {{
            const url = new URL(window.parent.location.href);
            url.searchParams.set({_GEO_PARAM_TARGET!r}, target);
            url.searchParams.set({_GEO_PARAM_STATUS!r}, status);
            if (message) url.searchParams.set({_GEO_PARAM_MESSAGE!r}, String(message));
            else url.searchParams.delete({_GEO_PARAM_MESSAGE!r});
            if (typeof lat === "number" && typeof lon === "number") {{
              url.searchParams.set({_GEO_PARAM_LAT!r}, String(lat));
              url.searchParams.set({_GEO_PARAM_LON!r}, String(lon));
            }} else {{
              url.searchParams.delete({_GEO_PARAM_LAT!r});
              url.searchParams.delete({_GEO_PARAM_LON!r});
            }}
            window.parent.history.replaceState({{}}, "", url.toString());
            window.parent.location.reload();
          }};
          button.addEventListener("click", () => {{
            if (!navigator.geolocation) {{
              finish("error", "Geolocation is not supported in this browser.");
              return;
            }}
            navigator.geolocation.getCurrentPosition(
              (position) => finish("success", "", position.coords.latitude, position.coords.longitude),
              (error) => {{
                let reason = "Unable to get your current location.";
                if (error && error.code === 1) reason = "Location permission was denied.";
                if (error && error.code === 2) reason = "Location services are unavailable.";
                if (error && error.code === 3) reason = "Location request timed out.";
                finish("error", reason);
              }},
              {{ enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }}
            );
          }});
        }})();
        </script>
        """,
        height=58,
    )

st.title("Course & Session Management")
st.markdown("Create and manage courses and sessions for student attendance.")

current_role = str((st.session_state.get("user") or {}).get("role") or "").strip().lower()
if current_role not in {"instructor", "admin"}:
    st.error("Access denied. This page is restricted to instructors and admins.")
    st.stop()

st.markdown("---")

# Section switcher (faster than tabs because only one section executes per rerun)
_consume_geolocation_event()
manage_sections = ["Create Course", "Manage Course", "Create Session", "Manage Enrollments", "Manage Sessions", "Manage Devices"]
default_manage_section = "Create Course"
if "manage_active_section" not in st.session_state or st.session_state.get("manage_active_section") not in manage_sections:
    st.session_state["manage_active_section"] = default_manage_section
if st.session_state.get("manage_section_control") not in manage_sections:
    st.session_state["manage_section_control"] = st.session_state["manage_active_section"]

try:
    active_section = st.segmented_control(
        "Manage Section",
        options=manage_sections,
        key="manage_section_control",
    )
    if not active_section:
        active_section = st.session_state.get("manage_active_section", default_manage_section)
except Exception:
    st.markdown("##### Manage Section")
    active_section = st.radio(
        "Manage Section",
        options=manage_sections,
        horizontal=True,
        key="manage_section_control_fallback",
    )

if not active_section:
    active_section = st.session_state.get("manage_active_section", default_manage_section)
st.session_state["manage_active_section"] = active_section

# ============================================================================
# TAB 1: CREATE COURSE
# ============================================================================
if active_section == "Create Course":
    st.subheader("Create New Course")
    st.markdown("Create a new course for attendance tracking.")
    # Reset stale Streamlit widget state once when defaults change.
    create_course_default_coords_version = "2026-04-10-v2"
    if st.session_state.get("create_course_default_coords_version") != create_course_default_coords_version:
        st.session_state["create_course_venue_lat_v3"] = 1.3460885449338553
        st.session_state["create_course_venue_lon_v3"] = 103.68122503972508
        st.session_state["create_course_venue_name_v3"] = ""
        st.session_state["create_course_default_coords_version"] = create_course_default_coords_version
    if current_role != "admin":
        st.info("Only admins can create courses and assign instructors.")
    else:
        instructors, instructor_error = fetch_active_instructors()

        if instructor_error:
            st.error(f"Could not load instructors: {instructor_error}")
        elif not instructors:
            st.warning("No active instructors were found. Create or activate an instructor account first.")

        with st.form("create_course_form"):
            st.markdown("##### Course Location")
            st.caption("Pick coordinates first. Applying map/current location refreshes the page.")
            course_loc_left, course_loc_right = st.columns([2, 1])

            with course_loc_left:
                _apply_geolocation_to_fields("create_course", "create_course_venue_lat_v3", "create_course_venue_lon_v3")
                render_map_marker_picker(
                    "create_course",
                    "create_course_venue_lat_v3",
                    "create_course_venue_lon_v3",
                    _safe_float(st.session_state.get("create_course_venue_lat_v3"), 1.3460885449338553),
                    _safe_float(st.session_state.get("create_course_venue_lon_v3"), 103.68122503972508),
                )
                render_current_location_picker("create_course", "create_course_venue_lat_v3", "create_course_venue_lon_v3")

            with course_loc_right:
                venue_lat = _number_input_with_state_default(
                    "Venue Latitude",
                    key="create_course_venue_lat_v3",
                    default=1.3460885449338553,
                    format="%.6f",
                    help="GPS latitude of venue",
                )
                venue_lon = _number_input_with_state_default(
                    "Venue Longitude",
                    key="create_course_venue_lon_v3",
                    default=103.68122503972508,
                    format="%.6f",
                    help="GPS longitude of venue",
                )
                venue_name = st.text_input(
                    "Default Venue",
                    placeholder="COM1-0212",
                    help="Default venue for sessions",
                    key="create_course_venue_name_v3"
                )

            st.markdown("---")
            col1, col2 = st.columns(2)

            with col1:
                course_code = st.text_input(
                    "Course Code *",
                    placeholder="CS3099",
                    help="Unique course code (e.g., CS3099)",
                    key="create_course_code",
                )
                course_name = st.text_input(
                    "Course Name *",
                    placeholder="Capstone Project",
                    help="Full name of the course",
                    key="create_course_name",
                )
                semester = st.text_input(
                    "Semester *",
                    placeholder="AY2024-25 Sem 2",
                    help="Academic semester",
                    key="create_course_semester",
                )
                selected_instructor = st.selectbox(
                    "Instructor *",
                    options=instructors,
                    format_func=lambda option: option["label"],
                    index=None,
                    placeholder="Select an instructor",
                    disabled=bool(instructor_error) or not instructors,
                    help="Assign the course owner instructor",
                    key="create_course_instructor",
                )

            with col2:
                st.caption("Course details")

            col1, col2 = st.columns(2)
            with col1:
                geofence_radius = st.number_input(
                    "Geofence Radius (meters)",
                    value=100,
                    min_value=10,
                    max_value=1000,
                    help="How far from venue students can check in",
                    key="create_course_geofence",
                )
            with col2:
                risk_threshold = st.slider(
                    "Risk Threshold",
                    min_value=0.0,
                    max_value=1.0,
                    value=0.5,
                    step=0.1,
                    help="Check-ins above this score will be flagged",
                    key="create_course_risk_threshold",
                )

            submit_course = st.form_submit_button(
                "Create Course",
                type="primary",
                use_container_width=True,
                disabled=bool(instructor_error) or not instructors
            )

            if submit_course:
                if not course_code or not course_name or not semester or not selected_instructor:
                    st.error("Please fill in all required fields and choose an instructor.")
                else:
                    normalized_code = course_code.strip().upper()
                    normalized_semester = semester.strip()

                    course_data = {
                        "code": normalized_code,
                        "name": course_name.strip(),
                        "semester": normalized_semester,
                        "instructor_id": selected_instructor["id"],
                        "venue_name": venue_name or None,
                        "venue_latitude": venue_lat,
                        "venue_longitude": venue_lon,
                        "geofence_radius_meters": geofence_radius,
                        "risk_threshold": risk_threshold
                    }

                    with st.spinner("Creating course..."):
                        response = api_post("/courses/", course_data)

                        if response is not None and response.status_code == 201:
                            result = response.json()
                            st.success("Course created successfully!")
                            st.json(result)
                        elif response is not None:
                            error = response_error(response)
                            st.error(f"Failed to create course: {error}")
                        else:
                            st.error("Failed to connect to server")

    st.info("Course editing and deletion are available in the `Manage Course` tab.")


# ============================================================================
# TAB: MANAGE COURSE
# ============================================================================
if active_section == "Manage Course":
    st.subheader("Manage Courses")
    st.markdown("View, edit, and delete existing courses.")
    pending_edit_course_id = str(st.session_state.get(_GEO_PENDING_EDIT_COURSE_ID, "") or "").strip()
    if pending_edit_course_id:
        st.session_state["create_course_load_existing"] = True
    show_existing_courses = st.toggle(
        "Load Existing Courses List",
        value=False,
        key="create_course_load_existing",
        help="Turn on only when needed. Rendering many course edit forms/maps can be slow.",
    )

    if st.button("Refresh Courses", disabled=not show_existing_courses):
        st.rerun()

    if not show_existing_courses:
        st.caption("Existing courses list is paused to keep Manage Course responsive.")
    courses = fetch_all_courses(is_active=True) if show_existing_courses else []
    if courses:
        edit_instructors: list[dict] = []
        edit_instructor_error: str | None = None
        if current_role == "admin":
            edit_instructors, edit_instructor_error = fetch_active_instructors()

        sessions_by_course: dict[str, list[dict]] = {}
        for session in fetch_all_sessions(page_size=200):
            course_id = session.get('course_id')
            if isinstance(course_id, str):
                sessions_by_course.setdefault(course_id, []).append(session)
        for course in courses:
            current_course_id = str(course.get("id") or "")
            with st.expander(
                f"{course.get('code')} - {course.get('name')}",
                expanded=bool(pending_edit_course_id and current_course_id == pending_edit_course_id),
            ):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**ID:** `{course.get('id')}`")
                    st.write(f"**Semester:** {course.get('semester')}")
                    st.write(f"**Venue:** {course.get('venue_name', 'Not set')}")
                with col2:
                    st.write(f"**Geofence:** {course.get('geofence_radius_meters', 100)}m")
                    st.write(f"**Risk Threshold:** {course.get('risk_threshold', 0.5)}")
                    st.write(f"**Active:** {'Yes' if course.get('is_active') else 'No'}")

                course_lat_key = f"course_lat_{course.get('id')}"
                course_lon_key = f"course_lon_{course.get('id')}"
                if course_lat_key not in st.session_state:
                    st.session_state[course_lat_key] = _safe_float(course.get("venue_latitude"), 1.3460885449338553)
                if course_lon_key not in st.session_state:
                    st.session_state[course_lon_key] = _safe_float(course.get("venue_longitude"), 103.68122503972508)
                st.markdown("##### Edit Course")
                with st.form(f"edit_course_form_{course.get('id')}"):
                    edit_col1, edit_col2 = st.columns(2)

                    with edit_col1:
                        updated_name = st.text_input(
                            "Course Name",
                            value=str(course.get("name") or ""),
                            key=f"course_name_{course.get('id')}"
                        )
                        updated_semester = st.text_input(
                            "Semester",
                            value=str(course.get("semester") or ""),
                            key=f"course_semester_{course.get('id')}"
                        )
                        updated_venue_name = _text_input_with_state_default(
                            "Venue",
                            key=f"course_venue_{course.get('id')}",
                            default=str(course.get("venue_name") or ""),
                        )
                        updated_description = st.text_area(
                            "Description",
                            value=str(course.get("description") or ""),
                            key=f"course_desc_{course.get('id')}"
                        )

                    with edit_col2:
                        _apply_geolocation_to_fields(
                            f"edit_course_{course.get('id')}",
                            f"course_lat_{course.get('id')}",
                            f"course_lon_{course.get('id')}",
                        )
                        render_map_marker_picker(
                            f"edit_course_{course.get('id')}",
                            f"course_lat_{course.get('id')}",
                            f"course_lon_{course.get('id')}",
                            _safe_float(st.session_state.get(f"course_lat_{course.get('id')}"), _safe_float(course.get("venue_latitude"), 1.3460885449338553)),
                            _safe_float(st.session_state.get(f"course_lon_{course.get('id')}"), _safe_float(course.get("venue_longitude"), 103.68122503972508)),
                        )
                        render_current_location_picker(
                            f"edit_course_{course.get('id')}",
                            f"course_lat_{course.get('id')}",
                            f"course_lon_{course.get('id')}",
                        )
                        updated_lat = _number_input_with_state_default(
                            "Venue Latitude",
                            key=f"course_lat_{course.get('id')}",
                            default=_safe_float(course.get("venue_latitude"), 1.3460885449338553),
                            format="%.6f",
                        )
                        updated_lon = _number_input_with_state_default(
                            "Venue Longitude",
                            key=f"course_lon_{course.get('id')}",
                            default=_safe_float(course.get("venue_longitude"), 103.68122503972508),
                            format="%.6f",
                        )
                        updated_geofence = st.number_input(
                            "Geofence Radius (meters)",
                            value=int(_safe_float(course.get("geofence_radius_meters"), 100)),
                            min_value=10,
                            max_value=1000,
                            key=f"course_geofence_{course.get('id')}"
                        )
                        updated_risk_threshold = st.slider(
                            "Risk Threshold",
                            min_value=0.0,
                            max_value=1.0,
                            step=0.1,
                            value=max(0.0, min(1.0, _safe_float(course.get("risk_threshold"), 0.5))),
                            key=f"course_risk_{course.get('id')}"
                        )

                    updated_instructor_id = None
                    if current_role == "admin":
                        if edit_instructor_error:
                            st.warning(f"Instructors unavailable: {edit_instructor_error}")
                        elif edit_instructors:
                            current_instructor_id = str(course.get("instructor_id") or "").strip()
                            default_index = 0
                            for idx, inst in enumerate(edit_instructors):
                                if inst.get("id") == current_instructor_id:
                                    default_index = idx
                                    break

                            selected_instructor = st.selectbox(
                                "Assigned Instructor",
                                options=edit_instructors,
                                format_func=lambda option: option["label"],
                                index=default_index,
                                key=f"course_instructor_{course.get('id')}"
                            )
                            updated_instructor_id = selected_instructor.get("id")

                    submit_edit_course = st.form_submit_button(
                        "Save Course Changes",
                        type="primary",
                        use_container_width=True
                    )

                    if submit_edit_course:
                        if not updated_name.strip() or not updated_semester.strip():
                            st.error("Course name and semester are required.")
                        else:
                            update_payload = {
                                "name": updated_name.strip(),
                                "semester": updated_semester.strip(),
                                "description": updated_description.strip() or None,
                                "venue_name": updated_venue_name.strip() or None,
                                "venue_latitude": updated_lat,
                                "venue_longitude": updated_lon,
                                "geofence_radius_meters": updated_geofence,
                                "risk_threshold": updated_risk_threshold,
                            }

                            if current_role == "admin" and updated_instructor_id:
                                update_payload["instructor_id"] = updated_instructor_id

                            response = api_put(f"/courses/{course.get('id')}", update_payload)
                            if response is not None and response.status_code == 200:
                                st.success("Course updated successfully.")
                                st.rerun()
                            elif response is not None:
                                st.error(response_error(response, "Couldn't update the course right now."))
                            else:
                                st.error("Failed to connect to server while updating course.")

                if course.get('is_active'):
                    course_sessions = sessions_by_course.get(course.get('id'), [])

                    if course_sessions:
                        active_sessions = [s for s in course_sessions if s.get('status') in ['scheduled', 'active']]
                        if active_sessions:
                            st.warning(f"This course has {len(active_sessions)} scheduled/active session(s). Deleting will prevent new check-ins.")
                        else:
                            st.caption(f"This course has {len(course_sessions)} session(s).")

                    if st.button("Delete Course", key=f"delete_course_{course.get('id')}"):
                        try:
                            headers = {}
                            token = st.session_state.get('access_token')
                            if token:
                                headers["Authorization"] = f"Bearer {token}"

                            response = requests.delete(
                                f"{API_BASE_URL}/courses/{course.get('id')}",
                                headers=headers,
                                timeout=10
                            )

                            if response.status_code == 204:
                                st.success("Course deleted (deactivated)!")
                                st.rerun()
                            else:
                                error = response_error(response)
                                st.error(f"Failed to delete: {error}")
                        except Exception as e:
                            st.error(friendly_error(e, "We couldn't connect to the server. Please try again."))
        if pending_edit_course_id:
            st.session_state.pop(_GEO_PENDING_EDIT_COURSE_ID, None)
    else:
        if not show_existing_courses:
            st.info("Existing courses list is currently hidden. Turn on `Load Existing Courses List` to view them.")
        else:
            st.info("No courses found. Create one above!")


# ============================================================================
# TAB 2: CREATE SESSION
# ============================================================================
if active_section == "Create Session":
    st.subheader("Create New Session")
    st.markdown("Create a new attendance session for a course.")

    # Get only ACTIVE courses for dropdown - cannot create sessions for deleted courses
    courses = fetch_all_courses(is_active=True)
    instructors: list[dict] = []
    instructor_error: str | None = None
    if current_role == "admin":
        instructors, instructor_error = fetch_active_instructors()

    if not courses:
        st.warning("No courses found. Please create a course first.")
    else:
        # Course selection outside form so map interactions are not buffered by form state.
        course_options = {f"{c['code']} - {c['name']}": c for c in courses}
        pending_course_id = str(st.session_state.pop(_GEO_PENDING_CREATE_SESSION_COURSE_ID, "") or "").strip()
        if pending_course_id:
            pending_label = next(
                (label for label, course in course_options.items() if str(course.get("id") or "") == pending_course_id),
                None,
            )
            if pending_label:
                st.session_state["create_session_course"] = pending_label
        selected_course_name = st.selectbox(
            "Select Course *",
            options=list(course_options.keys()),
            key="create_session_course",
        )
        selected_course = course_options[selected_course_name]
        session_location_suffix = str(selected_course.get("id") or "default")
        session_venue_key = f"create_session_venue_{session_location_suffix}"
        default_lat = selected_course.get('venue_latitude')
        if default_lat is None:
            default_lat = 1.3460885449338553
        default_lon = selected_course.get('venue_longitude')
        if default_lon is None:
            default_lon = 103.68122503972508
        default_geofence = selected_course.get('geofence_radius_meters')
        if default_geofence is None:
            default_geofence = 100
        default_risk_threshold = selected_course.get('risk_threshold')
        if default_risk_threshold is None:
            default_risk_threshold = 0.5
        session_lat_key = f"create_session_lat_{session_location_suffix}"
        session_lon_key = f"create_session_lon_{session_location_suffix}"
        if session_venue_key not in st.session_state:
            st.session_state[session_venue_key] = str(selected_course.get('venue_name') or '')
        if session_lat_key not in st.session_state:
            st.session_state[session_lat_key] = float(default_lat)
        if session_lon_key not in st.session_state:
            st.session_state[session_lon_key] = float(default_lon)

        with st.form("create_session_form"):
            st.caption(f"Selected course: {selected_course.get('code', 'N/A')} - {selected_course.get('name', 'N/A')}")
            default_start = datetime.now(SG_TZ) + timedelta(minutes=10)
            default_start = default_start.replace(second=0, microsecond=0)
            minute_remainder = default_start.minute % 5
            minutes_to_add = (5 - minute_remainder) if minute_remainder else 5
            default_start = default_start + timedelta(minutes=minutes_to_add)
            default_end = default_start + timedelta(hours=2)
            default_checkin_open = default_start - timedelta(minutes=15)
            default_checkin_close = default_start + timedelta(minutes=30)

            st.markdown("##### Venue")
            st.caption("Pick coordinates first. Applying map/current location refreshes the page.")
            venue_left, venue_right = st.columns([2, 1])
            with venue_left:
                _apply_geolocation_to_fields(f"create_session_{session_location_suffix}", session_lat_key, session_lon_key)
                render_map_marker_picker(
                    f"create_session_{session_location_suffix}",
                    session_lat_key,
                    session_lon_key,
                    _safe_float(st.session_state.get(session_lat_key), float(default_lat)),
                    _safe_float(st.session_state.get(session_lon_key), float(default_lon)),
                )
                render_current_location_picker(
                    f"create_session_{session_location_suffix}",
                    session_lat_key,
                    session_lon_key,
                )
            with venue_right:
                session_venue = st.text_input(
                    "Venue Name",
                    help="Leave empty to use course default",
                    key=session_venue_key,
                )
                session_lat = _number_input_with_state_default(
                    "Venue Latitude",
                    key=session_lat_key,
                    default=float(default_lat),
                    format="%.6f",
                )
                session_lon = _number_input_with_state_default(
                    "Venue Longitude",
                    key=session_lon_key,
                    default=float(default_lon),
                    format="%.6f",
                )

            st.markdown("---")
            selected_session_instructor = None
            if current_role == "admin":
                default_instructor_id = str(selected_course.get('instructor_id') or "").strip()
                default_index = None
                if default_instructor_id:
                    for idx, instructor in enumerate(instructors):
                        if instructor.get("id") == default_instructor_id:
                            default_index = idx
                            break

                selected_session_instructor = st.selectbox(
                    "Session Instructor *",
                    options=instructors,
                    format_func=lambda option: option["label"],
                    index=default_index,
                    placeholder="Select an instructor",
                    disabled=bool(instructor_error) or not instructors,
                    help="Required when admin creates a session",
                    key="create_session_instructor",
                )

                if instructor_error:
                    st.error(f"Could not load instructors: {instructor_error}")
                elif not instructors:
                    st.warning("No active instructors were found. Create or activate an instructor first.")

            st.markdown("##### Session Basics")
            basics_left, basics_right = st.columns([1.4, 1])
            with basics_left:
                session_name = st.text_input(
                    "Session Name *",
                    placeholder="Lecture 1: Introduction",
                    help="Name/title of the session",
                    key="create_session_name",
                )
                session_description = st.text_area(
                    "Description",
                    key="create_session_description",
                    help="Optional details about this session",
                )
            with basics_right:
                session_type = st.selectbox(
                    "Session Type *",
                    options=["lecture", "tutorial", "lab", "other"],
                    help="Type of session",
                    key="create_session_type",
                )
                st.caption("All dates and times are in Singapore Time (SGT).")

            st.markdown("##### Session Timing (SGT)")
            timing_col1, timing_col2 = st.columns(2)
            with timing_col1:
                st.markdown("Start")
                start_date_col, start_time_col = st.columns(2)
                with start_date_col:
                    start_date = st.date_input(
                        "Start Date *",
                        value=default_start.date(),
                        key="create_session_start_date",
                    )
                with start_time_col:
                    start_time = st.time_input(
                        "Start Time *",
                        value=default_start.replace(tzinfo=None).time(),
                        key="create_session_start_time",
                    )
            with timing_col2:
                st.markdown("End")
                end_date_col, end_time_col = st.columns(2)
                with end_date_col:
                    end_date = st.date_input(
                        "End Date *",
                        value=default_end.date(),
                        key="create_session_end_date",
                    )
                with end_time_col:
                    end_time = st.time_input(
                        "End Time *",
                        value=default_end.replace(tzinfo=None).time(),
                        key="create_session_end_time",
                    )

            st.markdown("##### Check-in Window (SGT)")
            window_col1, window_col2 = st.columns(2)
            with window_col1:
                st.markdown("Open")
                open_date_col, open_time_col = st.columns(2)
                with open_date_col:
                    checkin_open_date = st.date_input(
                        "Check-in Open Date",
                        value=default_checkin_open.date(),
                        key="create_session_checkin_open_date",
                    )
                with open_time_col:
                    checkin_open_time = st.time_input(
                        "Check-in Open Time",
                        value=default_checkin_open.replace(tzinfo=None).time(),
                        key="create_session_checkin_open_time",
                    )
            with window_col2:
                st.markdown("Close")
                close_date_col, close_time_col = st.columns(2)
                with close_date_col:
                    checkin_close_date = st.date_input(
                        "Check-in Close Date",
                        value=default_checkin_close.date(),
                        key="create_session_checkin_close_date",
                    )
                with close_time_col:
                    checkin_close_time = st.time_input(
                        "Check-in Close Time",
                        value=default_checkin_close.replace(tzinfo=None).time(),
                        key="create_session_checkin_close_time",
                    )

            st.markdown("##### Security Settings")
            sec_col1, sec_col2 = st.columns(2)
            with sec_col1:
                require_liveness = st.checkbox("Require Liveness Check", value=True, key="create_session_require_liveness")
                require_face_match = st.checkbox("Require Face Match", value=False, key="create_session_require_face_match")
                qr_code_enabled = st.checkbox(
                    "Require QR Code",
                    value=False,
                    help="Students must scan the instructor QR before submitting attendance",
                    key="create_session_qr_enabled",
                )
            with sec_col2:
                session_geofence = st.number_input(
                    "Geofence Radius (m)",
                    value=int(default_geofence),
                    min_value=10,
                    max_value=1000,
                    key="create_session_geofence",
                )
                session_risk_threshold = st.slider(
                    "Risk Threshold",
                    min_value=0.0,
                    max_value=1.0,
                    value=float(default_risk_threshold),
                    step=0.1,
                    key="create_session_risk_threshold",
                )

            submit_session = st.form_submit_button("Create Session", type="primary", use_container_width=True)

            if submit_session:
                # Build datetime objects first for validation
                scheduled_start = datetime.combine(start_date, start_time).replace(tzinfo=SG_TZ)
                scheduled_end = datetime.combine(end_date, end_time).replace(tzinfo=SG_TZ)
                checkin_opens = datetime.combine(checkin_open_date, checkin_open_time).replace(tzinfo=SG_TZ)
                checkin_closes = datetime.combine(checkin_close_date, checkin_close_time).replace(tzinfo=SG_TZ)

                # Validation checks
                validation_errors = []

                if not session_name:
                    validation_errors.append("Please enter a session name")

                if current_role == "admin":
                    if not instructors or instructor_error:
                        validation_errors.append("Cannot create session: active instructors could not be loaded")
                    elif not selected_session_instructor:
                        validation_errors.append("Please select a session instructor")

                if checkin_closes <= checkin_opens:
                    validation_errors.append("Check-in close time must be after open time")

                # Warn if session is in the past (but allow it - instructor might be backfilling)
                if scheduled_start < datetime.now(SG_TZ):
                    st.warning("Note: This session is scheduled in the past.")

                if validation_errors:
                    for error in validation_errors:
                        st.error(error)
                else:
                    session_data = {
                        "course_id": selected_course['id'],
                        "name": session_name,
                        "description": session_description.strip() or None,
                        "session_type": session_type,
                        "scheduled_start": to_api_datetime(scheduled_start),
                        "scheduled_end": to_api_datetime(scheduled_end),
                        "checkin_opens_at": to_api_datetime(checkin_opens),
                        "checkin_closes_at": to_api_datetime(checkin_closes),
                        "venue_name": session_venue or None,
                        "venue_latitude": session_lat,
                        "venue_longitude": session_lon,
                        "geofence_radius_meters": session_geofence,
                        "require_liveness_check": require_liveness,
                        "require_face_match": require_face_match,
                        "risk_threshold": session_risk_threshold,
                        "qr_code_enabled": qr_code_enabled
                    }
                    if current_role == "admin" and selected_session_instructor:
                        session_data["instructor_id"] = selected_session_instructor["id"]

                    with st.spinner("Creating session..."):
                        response = api_post("/sessions/", session_data)

                        if response is not None and response.status_code == 201:
                            result = response.json()
                            st.success("Session created successfully!")
                            st.json(result)
                        elif response is not None:
                            error = response_error(response)
                            st.error(f"Failed to create session: {error}")
                        else:
                            st.error("Failed to connect to server")

    st.markdown("---")
    st.info("Session editing, lifecycle status changes, and deletion are centralized in the `Manage Sessions` tab to avoid duplicate controls.")


# ============================================================================
# TAB 3: MANAGE ENROLLMENTS
# ============================================================================
if active_section == "Manage Enrollments":
    st.subheader("Manage Student Enrollments")
    st.markdown("Enroll students in courses.")

    # Get only ACTIVE courses for dropdown - cannot enroll in deleted courses
    courses = fetch_all_courses(is_active=True)

    if not courses:
        st.warning("No courses found. Please create a course first.")
    else:
        course_options = {f"{c['code']} - {c['name']}": c for c in courses}
        selected_course_name = st.selectbox(
            "Select Course",
            options=list(course_options.keys()),
            key="enroll_course"
        )
        selected_course = course_options[selected_course_name]

        st.markdown("---")

        # Single enrollment using student UUID (direct API method)
        st.markdown("##### Enroll Single Student")
        
        # Load all students for selection
        available_students = []
        students, students_error = fetch_all_users({"role": "student"}, page_size=100)
        if students_error:
            st.warning(f"Could not load full student list: {students_error}")
        else:
            for user in students:
                user_id = str(user.get("id") or "").strip()
                if not user_id:
                    continue
                full_name = str(user.get("full_name") or "Unnamed").strip()
                email = str(user.get("email") or "").strip()
                label = f"{full_name} ({email})" if email else full_name
                available_students.append({
                    "id": user_id,
                    "label": label,
                    "email": email,
                })
            available_students.sort(key=lambda s: s["label"].lower())
        
        with st.form("enroll_single_form"):
            selected_student = st.selectbox(
                "Select Student",
                options=available_students,
                format_func=lambda opt: opt["label"],
                index=None,
                placeholder="Search or select a student",
                help="Choose a student to enroll in this course"
            )

            submit_enroll = st.form_submit_button("Enroll Student", use_container_width=True)

            if submit_enroll:
                if not selected_student:
                    st.error("Please select a student")
                else:
                    enroll_data = {
                        "student_id": selected_student['id'],
                        "course_id": selected_course['id']
                    }

                    with st.spinner("Enrolling student..."):
                        response = api_post("/enrollments/", enroll_data)

                        if response is not None and response.status_code == 201:
                            st.success(f"Student {selected_student['email']} enrolled successfully!")
                        elif response is not None:
                            error = response_error(response)
                            if "already" in error.lower():
                                st.info("Student is already enrolled in this course.")
                            else:
                                st.error(f"Failed to enroll: {error}")
                        else:
                            st.error("Failed to connect to server")

        st.markdown("---")

        # Bulk enrollment
        st.markdown("##### Bulk Enroll by Email")
        with st.form("enroll_bulk_form"):
            student_emails = st.text_area(
                "Student Emails (one per line)",
                placeholder="student1@example.com\nstudent2@example.com",
                help="Enter student emails, one per line"
            )
            create_accounts = st.checkbox(
                "Create accounts for unknown emails",
                value=False,
                help="If checked, will create accounts for emails not found in the system"
            )

            submit_bulk = st.form_submit_button("Bulk Enroll", use_container_width=True)

            if submit_bulk:
                emails = [e.strip() for e in student_emails.split('\n') if e.strip()]
                if not emails:
                    st.error("Please enter at least one email")
                else:
                    bulk_data = {
                        "course_id": selected_course['id'],
                        "student_emails": emails,
                        "create_accounts": create_accounts
                    }

                    with st.spinner(f"Enrolling {len(emails)} students..."):
                        response = api_post("/enrollments/bulk", bulk_data)

                        if response is not None and response.status_code == 200:
                            result = response.json()
                            st.success(f"Enrolled: {result.get('enrolled', 0)}, Already enrolled: {result.get('already_enrolled', 0)}, Not found: {result.get('not_found', 0)}")
                            if result.get('details'):
                                st.json(result['details'])
                        elif response is not None:
                            error = response_error(response)
                            st.error(f"Failed: {error}")
                        else:
                            st.error("Failed to connect to server")

        # Show current enrollments
        st.markdown("---")
        st.markdown("##### Current Enrollments")

        response = api_get(f"/enrollments/course/{selected_course['id']}")
        if response is not None and response.status_code == 200:
            data = response.json()
            students = data.get('students', [])
            st.write(f"**Total enrolled:** {data.get('total_enrolled', len(students))}")

            if students:
                import pandas as pd
                df = pd.DataFrame(students)
                display_cols = ['student_name', 'student_email', 'enrolled_at', 'face_enrolled']
                available_cols = [c for c in display_cols if c in df.columns]
                if available_cols:
                    st.dataframe(df[available_cols], use_container_width=True)

                st.markdown("##### Remove Enrollment")
                enrollments_by_id = {
                    str(s.get("id")): s
                    for s in students
                    if s.get("id")
                }
                if enrollments_by_id:
                    selected_enrollment_id = st.selectbox(
                        "Select enrollment to remove",
                        options=list(enrollments_by_id.keys()),
                        format_func=lambda eid: (
                            f"{enrollments_by_id[eid].get('student_name', 'Unknown')} "
                            f"({enrollments_by_id[eid].get('student_email', 'N/A')}) | "
                            f"ID:{eid[:8]}"
                        ),
                        key="remove_enrollment_select"
                    )
                    selected_enrollment = enrollments_by_id[selected_enrollment_id]

                    if st.button("Remove Enrollment", key="remove_enrollment_btn", type="secondary"):
                        remove_response = api_delete(f"/enrollments/{selected_enrollment['id']}")
                        if remove_response is not None and remove_response.status_code == 204:
                            st.success("Enrollment removed.")
                            st.rerun()
                        else:
                            st.error(response_error(remove_response, "Couldn't remove enrollment right now."))
                else:
                    st.caption("No removable enrollment IDs available from API response.")
            else:
                st.info("No students enrolled yet")
        else:
            st.info("Could not load enrollments")


# ============================================================================
# TAB 4: SESSION STATUS
# ============================================================================
if active_section == "Manage Sessions":
    st.subheader("Manage Sessions")
    st.markdown("Edit session details, manage lifecycle status, and delete eligible sessions.")

    # Get sessions (paginated to avoid truncation)
    sessions = fetch_all_sessions(page_size=200)

    # Also get active courses to check if session's course is still active
    active_course_ids = {c['id'] for c in fetch_all_courses(is_active=True)}

    if not sessions:
        st.warning("No sessions found. Please create a session first.")
    else:
        session_sort_order = {
            'scheduled': 0,
            'active': 1,
            'closed': 2,
            'cancelled': 3
        }
        sessions = sorted(
            sessions,
            key=lambda session: (
                session_sort_order.get(session.get('status', ''), 99),
                session.get('scheduled_start', '')
            )
        )
        # Use session IDs as selectbox values so duplicate labels do not overwrite each other.
        sessions_by_id = {
            str(s.get("id")): s
            for s in sessions
            if s.get("id")
        }
        session_option_ids = list(sessions_by_id.keys())
        default_session_index = 0
        for index, session_id in enumerate(session_option_ids):
            if sessions_by_id[session_id].get('status') == 'scheduled':
                default_session_index = index
                break
        pending_session_id = str(st.session_state.pop(_GEO_PENDING_MANAGE_SESSION_ID, "") or "").strip()
        pending_action_session_id = str(st.session_state.pop(_PENDING_MANAGE_SESSION_SELECTION, "") or "").strip()
        preferred_session_id = pending_action_session_id or pending_session_id
        if preferred_session_id and preferred_session_id in sessions_by_id:
            st.session_state["manage_sessions_selected_session_id"] = preferred_session_id

        selected_session_id = st.selectbox(
            "Select Session",
            options=session_option_ids,
            index=default_session_index,
            format_func=lambda sid: (
                f"{sessions_by_id[sid].get('course_code', 'N/A')} - "
                f"{sessions_by_id[sid].get('name', 'Unnamed')} "
                f"({sessions_by_id[sid].get('status', 'unknown')}) | "
                f"{sessions_by_id[sid].get('scheduled_start', 'N/A')} | "
                f"ID:{sid[:8]}"
            ),
            help="Activate is only available for sessions that are currently scheduled and whose course is still active."
            ,
            key="manage_sessions_selected_session_id"
        )
        selected_session = dict(sessions_by_id[selected_session_id])
        if selected_session_id:
            detail_response = api_get(f"/sessions/{selected_session_id}")
            if detail_response is not None and detail_response.status_code == 200:
                try:
                    detail_payload = detail_response.json()
                except Exception:
                    detail_payload = None
                if isinstance(detail_payload, dict):
                    selected_session.update(detail_payload)

        def _preserve_manage_session_selection() -> None:
            st.session_state[_PENDING_MANAGE_SESSION_SELECTION] = str(
                selected_session.get("id") or selected_session_id
            )

        st.markdown("---")

        # Check if the course is still active
        course_id = selected_session.get('course_id')
        course_is_active = course_id in active_course_ids

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Current Status:**")
            status = selected_session.get('status', 'unknown')
            status_colors = {
                'scheduled': 'Scheduled',
                'active': 'Active',
                'closed': 'Closed',
                'cancelled': 'Cancelled'
            }
            st.write(status_colors.get(status, f'Unknown: {status}'))

        with col2:
            st.markdown("**Session Summary:**")
            st.write(f"Course: `{selected_session.get('course_code', 'N/A')}`")
            st.write(f"Session ID: `{selected_session.get('id')}`")
            if not course_is_active:
                st.error("Course has been deleted!")

        st.markdown("---")
        st.markdown("##### Edit Session")
        st.caption("You can edit session details except course and session type.")
        can_edit_session = str(status).strip().lower() == "scheduled"
        if not can_edit_session:
            st.info("Only sessions in `scheduled` status can be edited.")

        now_sg = datetime.now(SG_TZ).replace(second=0, microsecond=0)
        default_start_dt = _parse_api_datetime(selected_session.get("scheduled_start"), now_sg)
        default_end_dt = _parse_api_datetime(selected_session.get("scheduled_end"), default_start_dt + timedelta(hours=2))
        default_checkin_open_dt = _parse_api_datetime(
            selected_session.get("checkin_opens_at"),
            default_start_dt - timedelta(minutes=15)
        )
        default_checkin_close_dt = _parse_api_datetime(
            selected_session.get("checkin_closes_at"),
            default_start_dt + timedelta(minutes=30)
        )
        edit_session_key = str(selected_session.get("id") or "unknown")
        form_locked = not can_edit_session
        edit_session_lat_key = f"edit_venue_lat_{edit_session_key}"
        edit_session_lon_key = f"edit_venue_lon_{edit_session_key}"
        if edit_session_lat_key not in st.session_state:
            st.session_state[edit_session_lat_key] = _safe_float(selected_session.get("venue_latitude"), 1.3460885449338553)
        if edit_session_lon_key not in st.session_state:
            st.session_state[edit_session_lon_key] = _safe_float(selected_session.get("venue_longitude"), 103.68122503972508)

        with st.form(f"edit_session_form_{selected_session.get('id')}"):
            st.markdown("##### Venue")
            st.caption("Pick coordinates first. Applying map/current location refreshes the page.")
            edit_venue_left, edit_venue_right = st.columns([2, 1])
            with edit_venue_left:
                _apply_geolocation_to_fields(
                    f"edit_session_{edit_session_key}",
                    f"edit_venue_lat_{edit_session_key}",
                    f"edit_venue_lon_{edit_session_key}",
                )
                render_map_marker_picker(
                    f"edit_session_{edit_session_key}",
                    f"edit_venue_lat_{edit_session_key}",
                    f"edit_venue_lon_{edit_session_key}",
                    _safe_float(st.session_state.get(f"edit_venue_lat_{edit_session_key}"), _safe_float(selected_session.get("venue_latitude"), 1.3460885449338553)),
                    _safe_float(st.session_state.get(f"edit_venue_lon_{edit_session_key}"), _safe_float(selected_session.get("venue_longitude"), 103.68122503972508)),
                )
                render_current_location_picker(
                    f"edit_session_{edit_session_key}",
                    f"edit_venue_lat_{edit_session_key}",
                    f"edit_venue_lon_{edit_session_key}",
                )
            with edit_venue_right:
                updated_venue_name = _text_input_with_state_default(
                    "Venue Name",
                    key=f"edit_venue_name_{edit_session_key}",
                    default=str(selected_session.get("venue_name") or ""),
                    help="Leave empty to use course default",
                    disabled=form_locked,
                )
                updated_venue_lat = _number_input_with_state_default(
                    "Venue Latitude",
                    key=f"edit_venue_lat_{edit_session_key}",
                    default=_safe_float(selected_session.get("venue_latitude"), 1.3460885449338553),
                    format="%.6f",
                    disabled=form_locked,
                )
                updated_venue_lon = _number_input_with_state_default(
                    "Venue Longitude",
                    key=f"edit_venue_lon_{edit_session_key}",
                    default=_safe_float(selected_session.get("venue_longitude"), 103.68122503972508),
                    format="%.6f",
                    disabled=form_locked,
                )

            st.markdown("---")
            st.markdown("##### Session Basics")
            edit_basics_left, edit_basics_right = st.columns([1.4, 1])
            with edit_basics_left:
                updated_session_name = st.text_input(
                    "Session Name *",
                    value=str(selected_session.get("name") or ""),
                    key=f"edit_session_name_{edit_session_key}",
                    disabled=form_locked,
                )
                updated_description = st.text_area(
                    "Description",
                    value=str(selected_session.get("description") or ""),
                    key=f"edit_description_{edit_session_key}",
                    disabled=form_locked,
                )
            with edit_basics_right:
                st.text_input(
                    "Session Type",
                    value=str(selected_session.get("session_type") or "N/A"),
                    disabled=True,
                    help="Session type is set at creation and not editable via API.",
                    key=f"edit_session_type_{edit_session_key}",
                )
                st.caption("All dates and times are in Singapore Time (SGT).")

            st.markdown("##### Session Timing (SGT)")
            edit_timing_col1, edit_timing_col2 = st.columns(2)
            with edit_timing_col1:
                st.markdown("Start")
                edit_start_date_col, edit_start_time_col = st.columns(2)
                with edit_start_date_col:
                    updated_start_date = st.date_input(
                        "Start Date",
                        value=default_start_dt.date(),
                        key=f"edit_start_date_{edit_session_key}",
                        disabled=form_locked,
                    )
                with edit_start_time_col:
                    updated_start_time = st.time_input(
                        "Start Time",
                        value=default_start_dt.replace(tzinfo=None).time(),
                        key=f"edit_start_time_{edit_session_key}",
                        disabled=form_locked,
                    )
            with edit_timing_col2:
                st.markdown("End")
                edit_end_date_col, edit_end_time_col = st.columns(2)
                with edit_end_date_col:
                    updated_end_date = st.date_input(
                        "End Date",
                        value=default_end_dt.date(),
                        key=f"edit_end_date_{edit_session_key}",
                        disabled=form_locked,
                    )
                with edit_end_time_col:
                    updated_end_time = st.time_input(
                        "End Time",
                        value=default_end_dt.replace(tzinfo=None).time(),
                        key=f"edit_end_time_{edit_session_key}",
                        disabled=form_locked,
                    )

            st.markdown("##### Check-in Window (SGT)")
            checkin_col1, checkin_col2 = st.columns(2)
            with checkin_col1:
                st.markdown("Open")
                edit_open_date_col, edit_open_time_col = st.columns(2)
                with edit_open_date_col:
                    updated_checkin_open_date = st.date_input(
                        "Check-in Open Date",
                        value=default_checkin_open_dt.date(),
                        key=f"edit_checkin_open_date_{edit_session_key}",
                        disabled=form_locked,
                    )
                with edit_open_time_col:
                    updated_checkin_open_time = st.time_input(
                        "Check-in Open Time",
                        value=default_checkin_open_dt.replace(tzinfo=None).time(),
                        key=f"edit_checkin_open_time_{edit_session_key}",
                        disabled=form_locked,
                    )
            with checkin_col2:
                st.markdown("Close")
                edit_close_date_col, edit_close_time_col = st.columns(2)
                with edit_close_date_col:
                    updated_checkin_close_date = st.date_input(
                        "Check-in Close Date",
                        value=default_checkin_close_dt.date(),
                        key=f"edit_checkin_close_date_{edit_session_key}",
                        disabled=form_locked,
                    )
                with edit_close_time_col:
                    updated_checkin_close_time = st.time_input(
                        "Check-in Close Time",
                        value=default_checkin_close_dt.replace(tzinfo=None).time(),
                        key=f"edit_checkin_close_time_{edit_session_key}",
                        disabled=form_locked,
                    )

            st.markdown("##### Security Settings")
            settings_col1, settings_col2 = st.columns(2)
            with settings_col1:
                updated_require_liveness = st.checkbox(
                    "Require Liveness Check",
                    value=bool(selected_session.get("require_liveness_check", True)),
                    key=f"edit_require_liveness_{edit_session_key}",
                    disabled=form_locked,
                )
                updated_require_face_match = st.checkbox(
                    "Require Face Match",
                    value=bool(selected_session.get("require_face_match", False)),
                    key=f"edit_require_face_match_{edit_session_key}",
                    disabled=form_locked,
                )
                updated_qr_code_enabled = st.checkbox(
                    "Require QR Code",
                    value=bool(selected_session.get("qr_code_enabled", False)),
                    help="Students must scan the instructor QR before submitting attendance",
                    key=f"edit_qr_enabled_{edit_session_key}",
                    disabled=form_locked,
                )
            with settings_col2:
                updated_geofence_radius = st.number_input(
                    "Geofence Radius (m)",
                    min_value=10,
                    max_value=1000,
                    value=int(_safe_float(selected_session.get("geofence_radius_meters"), 100)),
                    key=f"edit_geofence_{edit_session_key}",
                    disabled=form_locked,
                )
                updated_risk_threshold = st.slider(
                    "Risk Threshold",
                    min_value=0.0,
                    max_value=1.0,
                    step=0.1,
                    value=max(0.0, min(1.0, _safe_float(selected_session.get("risk_threshold"), 0.5))),
                    key=f"edit_risk_threshold_{edit_session_key}",
                    disabled=form_locked,
                )

            submit_edit_session = st.form_submit_button(
                "Save Session Changes",
                type="primary",
                use_container_width=True,
                disabled=not can_edit_session,
            )

            if submit_edit_session:
                if not can_edit_session:
                    st.error("Session edits are only allowed when status is `scheduled`.")
                    st.stop()
                updated_start_dt = datetime.combine(updated_start_date, updated_start_time).replace(tzinfo=SG_TZ)
                updated_end_dt = datetime.combine(updated_end_date, updated_end_time).replace(tzinfo=SG_TZ)
                updated_checkin_open_dt = datetime.combine(updated_checkin_open_date, updated_checkin_open_time).replace(tzinfo=SG_TZ)
                updated_checkin_close_dt = datetime.combine(updated_checkin_close_date, updated_checkin_close_time).replace(tzinfo=SG_TZ)

                edit_errors = []
                if not updated_session_name.strip():
                    edit_errors.append("Session name is required.")
                if updated_end_dt <= updated_start_dt:
                    edit_errors.append("Session end time must be after start time.")
                if updated_checkin_close_dt <= updated_checkin_open_dt:
                    edit_errors.append("Check-in close time must be after open time.")

                if edit_errors:
                    for error in edit_errors:
                        st.error(error)
                else:
                    update_payload = {
                        "name": updated_session_name.strip(),
                        "description": updated_description.strip() or None,
                        "scheduled_start": to_api_datetime(updated_start_dt),
                        "scheduled_end": to_api_datetime(updated_end_dt),
                        "checkin_opens_at": to_api_datetime(updated_checkin_open_dt),
                        "checkin_closes_at": to_api_datetime(updated_checkin_close_dt),
                        "venue_name": updated_venue_name.strip() or None,
                        "venue_latitude": updated_venue_lat,
                        "venue_longitude": updated_venue_lon,
                        "geofence_radius_meters": updated_geofence_radius,
                        "require_liveness_check": updated_require_liveness,
                        "require_face_match": updated_require_face_match,
                        "risk_threshold": updated_risk_threshold,
                        "qr_code_enabled": updated_qr_code_enabled,
                    }

                    update_response = api_patch(f"/sessions/{selected_session.get('id')}", update_payload)
                    if update_response is not None and update_response.status_code == 200:
                        _preserve_manage_session_selection()
                        st.success("Session updated successfully.")
                        st.rerun()
                    elif update_response is not None:
                        st.error(response_error(update_response, "Couldn't update the session right now."))
                    else:
                        st.error("Failed to connect to server while updating session.")

        st.markdown("---")

        # Show warning if course is deleted
        if not course_is_active:
            st.warning("This session belongs to a deleted course. You cannot activate it. Restore the course first or cancel/close this session.")

        st.markdown("##### Change Status")

        # Define valid state transitions
        # scheduled -> active, cancelled
        # active -> closed, cancelled
        # closed -> (none - finalized)
        # cancelled -> (none - terminal state)

        valid_transitions = {
            'scheduled': ['active', 'cancelled'],
            'active': ['closed', 'cancelled'],
            'closed': ['cancelled'], # Allow cancellation from closed (matches backend/spec)
            'cancelled': [] # Terminal state - no transitions allowed
        }

        allowed_next_states = valid_transitions.get(status, [])

        # Additional restriction: cannot activate if course is deleted
        if not course_is_active and 'active' in allowed_next_states:
            allowed_next_states = [s for s in allowed_next_states if s != 'active']

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            can_activate = 'active' in allowed_next_states
            if st.button("Activate", use_container_width=True, type="primary", disabled=not can_activate):
                if can_activate:
                    response = api_patch(
                        f"/sessions/{selected_session['id']}",
                        {"status": "active"}
                    )
                    if response is not None and response.status_code == 200:
                        _preserve_manage_session_selection()
                        st.success("Session activated!")
                        st.rerun()
                    else:
                        error_msg = response_error(response, "Failed to activate session")
                        st.error(error_msg)

        with col2:
            can_close = 'closed' in allowed_next_states
            if st.button("Close", use_container_width=True, disabled=not can_close):
                if can_close:
                    response = api_patch(
                        f"/sessions/{selected_session['id']}",
                        {"status": "closed"}
                    )
                    if response is not None and response.status_code == 200:
                        _preserve_manage_session_selection()
                        st.success("Session closed!")
                        st.rerun()
                    else:
                        error_msg = response_error(response, "Failed to close session")
                        st.error(error_msg)

        with col3:
            can_cancel = 'cancelled' in allowed_next_states
            if st.button("Cancel", use_container_width=True, disabled=not can_cancel):
                if can_cancel:
                    response = api_patch(
                        f"/sessions/{selected_session['id']}",
                        {"status": "cancelled"}
                    )
                    if response is not None and response.status_code == 200:
                        _preserve_manage_session_selection()
                        st.success("Session cancelled!")
                        st.rerun()
                    else:
                        error_msg = response_error(response, "Failed to cancel session")
                        st.error(error_msg)

        with col4:
            # Schedule button is not typically allowed - sessions don't go backward
            # Only show if we want to allow re-scheduling (uncomment if needed)
            st.button("Schedule", use_container_width=True, disabled=True,
                     help="Sessions cannot be moved back to scheduled status")

        # Show explanation of current state
        st.markdown("---")
        if status == 'closed':
            st.info("This session is **closed**. Attendance is finalized, but you may still cancel the session if needed.")
        elif status == 'cancelled':
            st.info("This session is **cancelled**. No further changes are allowed.")
        elif status == 'active':
            st.info("This session is **active**. Students can currently check in. Close it when the check-in period ends.")
        elif status == 'scheduled':
            st.info("This session is **scheduled**. Activate it to open check-in for students.")

        st.markdown("---")
        st.markdown("""
        **Status Transition Rules:**
        - **Scheduled** -> Active (open check-in) or Cancelled
        - **Active** -> Closed (finalize attendance) or Cancelled
        - **Closed** -> Cancelled
        - **Cancelled** -> No changes (terminal state)
        """)

        # Delete button - only for scheduled sessions (matches backend/spec)
        if status == 'scheduled':
            st.warning("""
            **Warning:** Deleting a session is permanent. 
            Only sessions with status `scheduled` can be deleted. Active or closed sessions must be `cancelled` instead.
            """)
            if st.button("Delete Session", use_container_width=True, type="secondary"):
                try:
                    # DELETE request without Content-Type header
                    headers = {}
                    token = st.session_state.get('access_token')
                    if token:
                        headers["Authorization"] = f"Bearer {token}"

                    response = requests.delete(
                        f"{API_BASE_URL}/sessions/{selected_session['id']}",
                        headers=headers,
                        timeout=10
                    )

                    if response.status_code == 204:
                        st.success("Session deleted!")
                        st.rerun()
                    else:
                        error = response_error(response)
                        st.error(f"Failed to delete: {error}")
                except Exception as e:
                    st.error(friendly_error(e, "We couldn't connect to the server. Please try again."))
        elif status in ['active', 'closed', 'cancelled']:
            st.markdown("---")
            st.markdown("##### Delete Restrictions")
            if status == 'cancelled':
                st.warning("Cancelled sessions cannot be deleted. Only scheduled sessions can be deleted.")
            else:
                st.warning("This session cannot be deleted because it has/had active check-ins. Close or cancel it instead.")


# ============================================================================
# TAB 5: MANAGE DEVICES (ADMIN)
# ============================================================================
if active_section == "Manage Devices":
    st.subheader("Device Management")
    st.markdown("View registered devices and revoke stale entries.")
    if current_role != "admin":
        st.error("Restricted access. Device management is admin-only.")
        st.info("Instructors and TAs do not have permission to view or manage devices in this tab.")
        st.stop()
    FEEDBACK_KEY = "device_mgmt_feedback"

    def device_ref(device: dict) -> str:
        raw_id = str(device.get("id") or "").strip()
        if len(raw_id) >= 8:
            return f"DEV-{raw_id[:4].upper()}-{raw_id[-4:].upper()}"
        return "DEV-UNKNOWN"

    def owner_label(device: dict) -> str:
        full_name = str(device.get("full_name") or "").strip()
        email = str(device.get("email") or "").strip()
        if full_name and email:
            return f"{full_name} ({email})"
        if email:
            return email
        user_id = str(device.get("user_id") or "").strip()
        return user_id or "N/A"

    def short_fingerprint(device: dict) -> str:
        fp = str(device.get("device_fingerprint") or "").strip()
        if len(fp) >= 12:
            return f"{fp[:6]}...{fp[-6:]}"
        return fp or "N/A"

    def device_search_blob(device: dict) -> str:
        fields = [
            device_ref(device),
            str(device.get("device_name") or ""),
            str(device.get("platform") or ""),
            str(device.get("full_name") or ""),
            str(device.get("email") or ""),
            str(device.get("user_id") or ""),
            str(device.get("id") or ""),
            str(device.get("device_fingerprint") or ""),
        ]
        return " ".join(fields).lower()

    def set_feedback(level: str, message: str):
        st.session_state[FEEDBACK_KEY] = {"level": level, "message": message}

    feedback = st.session_state.pop(FEEDBACK_KEY, None)
    if isinstance(feedback, dict):
        level = str(feedback.get("level") or "").lower()
        message = str(feedback.get("message") or "").strip()
        if message:
            if level == "success":
                st.success(message)
            elif level == "warning":
                st.warning(message)
            else:
                st.error(message)

    def fetch_my_devices(headers):
        try:
            resp = requests.get(f"{API_BASE_URL}/devices/my-devices", headers=headers, timeout=10)
            if resp.status_code == 200:
                payload = resp.json()
                return (payload if isinstance(payload, list) else payload.get("items", [])), None
            return [], response_error(resp, "Failed to load your devices")
        except Exception:
            return [], "Failed to connect while loading your devices"

    def fetch_all_devices(headers):
        try:
            resp = requests.get(
                f"{API_BASE_URL}/devices/",
                headers=headers,
                timeout=10,
            )
            if resp.status_code == 200:
                payload = resp.json()
                return (payload.get("items", []) if isinstance(payload, dict) else []), None
            return [], response_error(resp, "Failed to load device list")
        except Exception:
            return [], "Failed to connect while loading device list"

    def revoke_device(device_id, headers):
        try:
            delete_headers = {}
            auth = headers.get("Authorization")
            if auth:
                delete_headers["Authorization"] = auth
            resp = requests.delete(
                f"{API_BASE_URL}/devices/{device_id}",
                headers=delete_headers,
                timeout=10
            )
            if resp.status_code == 204:
                return True, None
            return False, response_error(resp, "Failed to revoke device")
        except Exception:
            return False, "Failed to connect while revoking device"

    def update_device(device_id, headers, payload):
        try:
            resp = requests.patch(
                f"{API_BASE_URL}/devices/{device_id}",
                json=payload,
                headers=headers,
                timeout=10,
            )
            return resp
        except Exception:
            return None

    headers = get_headers()
    fetch_error = None
    if current_role == "admin":
        devices, fetch_error = fetch_all_devices(headers)
        if fetch_error:
            st.warning(f"Global device list unavailable: {fetch_error}. Falling back to your own devices.")
            devices, fallback_error = fetch_my_devices(headers)
            if fallback_error:
                fetch_error = f"{fetch_error}; fallback failed: {fallback_error}"
            else:
                fetch_error = None
    else:
        devices, fetch_error = fetch_my_devices(headers)

    if fetch_error:
        st.error(fetch_error)

    visible_devices = devices
    if devices and current_role == "admin":
        st.markdown("##### Find Device")
        col_find_1, col_find_2, col_find_3 = st.columns([2, 1, 1])
        with col_find_1:
            search_term = st.text_input(
                "Search by owner, email, device ref, fingerprint, or name",
                placeholder="e.g. nicholas, DEV-1A2B-3C4D, 5f8a...9bc1",
                key="admin_device_search",
            ).strip().lower()
        with col_find_2:
            active_filter = st.selectbox("Active", options=["All", "Active", "Inactive"], index=0, key="admin_device_active_filter")
        with col_find_3:
            trusted_filter = st.selectbox("Trust", options=["All", "Trusted", "Untrusted"], index=0, key="admin_device_trust_filter")

        visible_devices = []
        for d in devices:
            if search_term and search_term not in device_search_blob(d):
                continue
            if active_filter == "Active" and not bool(d.get("is_active", True)):
                continue
            if active_filter == "Inactive" and bool(d.get("is_active", True)):
                continue
            if trusted_filter == "Trusted" and not bool(d.get("is_trusted", False)):
                continue
            if trusted_filter == "Untrusted" and bool(d.get("is_trusted", False)):
                continue
            visible_devices.append(d)

        st.caption(f"Showing {len(visible_devices)} of {len(devices)} devices")

    if not visible_devices:
        if current_role == "admin":
            st.info("No matching devices found.")
        else:
            st.info("No devices found.")
    else:
        for device in visible_devices:
            device_tag = device_ref(device)
            title_owner = owner_label(device) if current_role == "admin" else ""
            title_left = f"{device.get('device_name', 'Unknown Device')} [{device_tag}]"
            title_right = f"{device.get('platform', 'unknown')} | Trusted: {device.get('is_trusted', False)}"
            title = f"{title_left} - {title_owner} - {title_right}" if title_owner else f"{title_left} ({title_right})"
            with st.expander(title):
                st.write(f"**Device Ref:** `{device_tag}`")
                st.write(f"**ID:** `{device.get('id')}`")
                if current_role == "admin":
                    st.write(f"**Owner:** {owner_label(device)}")
                st.write(f"**User ID:** `{device.get('user_id', 'N/A')}`")
                st.write(f"**Fingerprint:** `{short_fingerprint(device)}`")
                st.write(f"**Platform:** {device.get('platform', 'unknown')}")
                st.write(f"**First Seen:** {device.get('first_seen_at', 'N/A')}")
                st.write(f"**Last Seen:** {device.get('last_seen_at', 'N/A')}")
                st.write(f"**Total Check-ins:** {device.get('total_checkins', 0)}")
                st.write(f"**Active:** {'Yes' if device.get('is_active', True) else 'No'}")
                st.write(f"**Trust Score:** {device.get('trust_score', 'N/A')}")
                st.write(f"**Trusted:** {'Yes' if device.get('is_trusted', False) else 'No'}")
                is_revoked = bool(device.get("revoked_at") or device.get("revocation_reason"))
                st.write(f"**Revoked:** {'Yes' if is_revoked else 'No'}")
                if device.get("revoked_at"):
                    st.write(f"**Revoked At:** {device.get('revoked_at')}")
                if device.get("revocation_reason"):
                    st.write(f"**Revocation Reason:** {device.get('revocation_reason')}")
                with st.form(f"update_device_{device['id']}"):
                    st.markdown("##### Update Device")
                    updated_active = st.checkbox(
                        "Active",
                        value=bool(device.get('is_active', True)),
                        key=f"device_active_{device['id']}",
                        disabled=is_revoked
                    )

                    updated_trusted = None
                    if current_role == "admin":
                        updated_trusted = st.checkbox(
                            "Trusted (admin)",
                            value=bool(device.get('is_trusted', False)),
                            key=f"device_trusted_{device['id']}",
                            disabled=is_revoked
                        )

                    submit_update = st.form_submit_button("Save Device Changes", use_container_width=True, disabled=is_revoked)

                    if submit_update:
                        if is_revoked:
                            set_feedback("error", "Revoked devices cannot be modified.")
                            st.rerun()
                        payload = {}

                        if payload is not None and updated_active != bool(device.get('is_active', True)):
                            payload["is_active"] = updated_active

                        if payload is not None and current_role == "admin" and updated_trusted is not None and updated_trusted != bool(device.get('is_trusted', False)):
                            payload["is_trusted"] = updated_trusted

                        if payload is None:
                            pass
                        elif not payload:
                            st.info("No changes detected.")
                        else:
                            resp = update_device(device['id'], headers, payload)
                            if resp is not None and resp.status_code == 200:
                                set_feedback("success", "Device updated.")
                                st.rerun()
                            else:
                                set_feedback("error", response_error(resp, "Couldn't update the device right now."))
                                st.rerun()

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Revoke Device", key=f"revoke_{device['id']}", disabled=is_revoked):
                        revoked, revoke_error = revoke_device(device['id'], headers)
                        if revoked:
                            set_feedback("success", "Device revoked.")
                            st.rerun()
                        else:
                            set_feedback("error", f"Failed to revoke device: {revoke_error}")
                            st.rerun()
                with col2:
                    st.caption("Use the controls in each device card to update trust/active state or revoke.")



