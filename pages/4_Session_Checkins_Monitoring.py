"""SAIV Instructor Dashboard - Session Check-ins Monitoring
"""

import streamlit as st
from lib import stat_sessions
from lib.ui_theme import apply_theme
from lib.ui_components import add_component_css


st.set_page_config(
    page_title="Session Check-ins Monitoring - SAIV Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_theme()
add_component_css()


if __name__ == "__main__":
    stat_sessions.main(embedded=False)
else:
    stat_sessions.main(embedded=False)
