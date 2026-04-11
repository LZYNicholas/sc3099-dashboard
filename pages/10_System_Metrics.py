"""SAIV Dashboard - System Metrics"""

import os
import streamlit as st
import streamlit.components.v1 as components
from urllib.parse import quote_plus
from lib.auth_state import require_auth
from lib.ui_theme import apply_theme

st.set_page_config(page_title="System Metrics - SAIV Dashboard", layout="wide", initial_sidebar_state="expanded")
apply_theme()
require_auth()

st.title("System Metrics")
st.caption("Live infrastructure and API monitoring via Grafana.")

grafana_base = os.getenv("GRAFANA_URL", "http://localhost:3001").rstrip("/")
dashboard_uid = os.getenv("GRAFANA_DASHBOARD_UID", "").strip()
org_id = os.getenv("GRAFANA_ORG_ID", "1").strip() or "1"
time_window = st.selectbox("Time Window", options=["5m", "15m", "1h", "6h", "24h", "7d"], index=2)

if dashboard_uid:
    grafana_url = (
        f"{grafana_base}/d/{quote_plus(dashboard_uid)}"
        f"?orgId={quote_plus(org_id)}&from=now-{quote_plus(time_window)}&to=now&kiosk"
    )
else:
    grafana_url = f"{grafana_base}/?orgId={quote_plus(org_id)}&kiosk"

st.link_button("Open Grafana in New Tab", grafana_url, use_container_width=True)

try:
    components.iframe(grafana_url, height=900, scrolling=True)
except Exception:
    st.warning("Unable to embed Grafana in this environment. Use the button above.")
