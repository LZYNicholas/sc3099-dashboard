import streamlit as st


def apply_theme() -> None:
    st.markdown(
        """
        <style>
          :root {
            --bg: #f4f7fb;
            --panel: #ffffff;
            --panel-soft: #f8fafc;
            --border: #d6e0ea;
            --text: #132a3f;
            --muted: #5b6f84;
            --primary: #0f6fb2;
            --primary-strong: #0a568a;
            --accent: #f59f00;
            --success: #2f9e44;
            --danger: #d9480f;
          }

          .stApp {
            background:
              radial-gradient(1200px 400px at -10% -15%, #dff2ff 0%, rgba(223,242,255,0) 50%),
              radial-gradient(900px 280px at 120% -10%, #fff1d6 0%, rgba(255,241,214,0) 45%),
              var(--bg);
            color: var(--text);
          }

          .block-container {
            padding-top: 1.1rem !important;
            padding-bottom: 2rem !important;
          }

          h1, h2, h3 {
            color: var(--text) !important;
            letter-spacing: 0.2px;
          }

          div[data-testid="stMetric"] {
            background: linear-gradient(180deg, #ffffff 0%, #f9fbfe 100%);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 0.55rem 0.75rem;
            box-shadow: 0 6px 16px rgba(15, 47, 77, 0.06);
          }

          div[data-testid="stDataFrame"], div[data-testid="stTable"] {
            border: 1px solid var(--border);
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 5px 14px rgba(15, 47, 77, 0.06);
          }

          div[data-testid="stTabs"] button[role="tab"] {
            border-radius: 10px !important;
            border: 1px solid var(--border) !important;
            background: #fff !important;
            color: var(--muted) !important;
            font-weight: 600 !important;
          }

          div[data-testid="stTabs"] button[aria-selected="true"] {
            background: linear-gradient(180deg, #eaf6ff 0%, #dff0ff 100%) !important;
            color: var(--primary-strong) !important;
            border-color: #b4d7f0 !important;
          }

          .stButton > button, .stDownloadButton > button, .stFormSubmitButton > button, div[data-testid="stLinkButton"] a {
            border-radius: 10px !important;
            border: 1px solid #0b629b !important;
            background: linear-gradient(180deg, #1080cd 0%, #0f6fb2 100%) !important;
            color: #ffffff !important;
            font-weight: 650 !important;
            width: 100% !important;
            min-height: 42px !important;
            padding: 0.55rem 0.9rem !important;
            line-height: 1.2 !important;
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            transition: all 0.16s ease;
            box-shadow: 0 6px 14px rgba(16, 112, 178, 0.25);
          }

          .stButton > button:hover, .stDownloadButton > button:hover, .stFormSubmitButton > button:hover, div[data-testid="stLinkButton"] a:hover {
            transform: translateY(-1px);
            background: linear-gradient(180deg, #0f6fb2 0%, #0a568a 100%) !important;
          }

          div[data-testid="stAlert"] {
            border-radius: 10px;
            border-width: 1px !important;
          }

          .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div {
            border-radius: 10px !important;
            border-color: var(--border) !important;
          }

          section[data-testid="stSidebar"] {
            border-right: 1px solid var(--border);
            background: linear-gradient(180deg, #0f2234 0%, #132a3f 100%);
          }

          section[data-testid="stSidebar"] * {
            color: #dfe9f3 !important;
          }

          section[data-testid="stSidebar"] .stButton > button {
            background: linear-gradient(180deg, #f5a524 0%, #eb8f00 100%) !important;
            border: 1px solid #d97e00 !important;
            color: #10253a !important;
            box-shadow: 0 4px 12px rgba(245, 165, 36, 0.35);
            min-height: 40px !important;
            padding: 0.5rem 0.8rem !important;
          }

          /* Hide default "App" item in Streamlit page navigation. */
          section[data-testid="stSidebar"] [data-testid="stSidebarNav"] ul li:first-child {
            display: none !important;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )
