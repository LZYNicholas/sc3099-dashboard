import streamlit as st


def hero(title: str, subtitle: str, eyebrow: str | None = None) -> None:
    eyebrow_html = f'<div class="ui-eyebrow">{eyebrow}</div>' if eyebrow else ""
    st.markdown(
        f"""
        <div class="ui-hero">
          {eyebrow_html}
          <h1>{title}</h1>
          <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_header(title: str, subtitle: str | None = None) -> None:
    subtitle_html = f"<p>{subtitle}</p>" if subtitle else ""
    st.markdown(
        f"""
        <div class="ui-section-header">
          <h3>{title}</h3>
          {subtitle_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def add_component_css() -> None:
    st.markdown(
        """
        <style>
          .ui-hero {
            background: linear-gradient(120deg, #0f6fb2 0%, #0d5f99 45%, #174b75 100%);
            color: #f8fcff;
            border-radius: 16px;
            padding: 1.05rem 1.15rem;
            margin-bottom: 1rem;
            box-shadow: 0 10px 24px rgba(8, 58, 94, 0.25);
            border: 1px solid rgba(255,255,255,0.16);
          }
          .ui-hero h1 {
            margin: 0;
            font-size: 1.75rem;
            color: #ffffff !important;
          }
          .ui-hero p {
            margin: 0.35rem 0 0 0;
            color: #dcecf8;
            font-size: 0.95rem;
          }
          .ui-eyebrow {
            display: inline-block;
            font-size: 0.72rem;
            letter-spacing: 0.45px;
            text-transform: uppercase;
            font-weight: 700;
            color: #b9ddf6;
            margin-bottom: 0.28rem;
          }
          .ui-section-header h3 {
            margin: 0 0 0.1rem 0;
          }
          .ui-section-header p {
            margin: 0 0 0.6rem 0;
            color: #5b6f84;
          }
          .ui-card {
            background: #ffffff;
            border: 1px solid #d6e0ea;
            border-radius: 13px;
            padding: 0.8rem 0.85rem;
            box-shadow: 0 6px 14px rgba(15, 47, 77, 0.06);
            margin-bottom: 0.7rem;
          }
          .ui-card h4 {
            margin: 0 0 0.25rem 0;
            font-size: 1rem;
            color: #16314b;
          }
          .ui-card p {
            margin: 0;
            color: #5b6f84;
            font-size: 0.9rem;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )
