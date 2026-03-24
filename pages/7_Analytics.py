"""SAIV Instructor Dashboard - Analytics Page
Extended analytics with Matplotlib, Plotly, and Prometheus data.
"""

import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
import sys
import importlib

# Ensure dashboard project root is importable when this page is analyzed directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

auth_state = importlib.import_module("lib.auth_state")
API_BASE_URL = auth_state.API_BASE_URL
get_auth_headers = auth_state.get_auth_headers
require_auth = auth_state.require_auth

st.set_page_config(page_title="Analytics - SAIV Dashboard", layout="wide")

PROMETHEUS_URL = "http://prometheus:9090" # Internal Docker hostname


def get_headers():
    return get_auth_headers()


def prom_query(promql: str) -> list[dict]:
    """Query Prometheus instant endpoint."""
    try:
        resp = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": promql},
            timeout=5,
        )
        if resp.status_code == 200:
            return resp.json().get("data", {}).get("result", [])
    except Exception:
        pass
    return []


def prom_range_query(promql: str, start: str, end: str, step: str = "5m") -> list[dict]:
    """Query Prometheus range endpoint."""
    try:
        resp = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query_range",
            params={"query": promql, "start": start, "end": end, "step": step},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json().get("data", {}).get("result", [])
    except Exception:
        pass
    return []


def fetch_all_checkins(headers: dict) -> pd.DataFrame:
    """Fetch all check-ins from the backend (paged)."""
    rows = []
    limit = 200
    offset = 0
    while True:
        resp = requests.get(
            f"{API_BASE_URL}/checkins/?limit={limit}&offset={offset}",
            headers=headers,
            timeout=15,
        )
        if resp.status_code != 200:
            break
        data = resp.json()
        items = data.get("items", [])
        rows.extend(items)
        if len(items) < limit:
            break
        offset += limit
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    if "checked_in_at" in df.columns:
        df["checked_in_at"] = pd.to_datetime(df["checked_in_at"], utc=True)
    return df


def fetch_devices(headers: dict) -> pd.DataFrame:
    """Fetch all registered devices (admin only)."""
    try:
        resp = requests.get(
            f"{API_BASE_URL}/devices/?limit=500",
            headers=headers,
            timeout=10,
        )
        if resp.status_code == 200:
            return pd.DataFrame(resp.json().get("items", []))
    except Exception:
        pass
    return pd.DataFrame()


def matplotlib_risk_histogram(df: pd.DataFrame) -> BytesIO:
    """Risk score histogram rendered with Matplotlib."""
    fig, ax = plt.subplots(figsize=(8, 4), facecolor="#1e293b")
    ax.set_facecolor("#1e293b")

    risk_scores = df["risk_score"].dropna().astype(float)

    n, bins, patches = ax.hist(risk_scores, bins=20, range=(0, 1), edgecolor="#334155")
    # Colour bars by risk zone
    for patch, left in zip(patches, bins[:-1]):
        if left < 0.3:
            patch.set_facecolor("#22c55e")
        elif left < 0.5:
            patch.set_facecolor("#eab308")
        elif left < 0.7:
            patch.set_facecolor("#f97316")
        else:
            patch.set_facecolor("#ef4444")

    ax.set_xlabel("Risk Score", color="#94a3b8")
    ax.set_ylabel("Check-ins", color="#94a3b8")
    ax.set_title("Risk Score Distribution", color="#f8fafc", fontsize=13)
    ax.tick_params(colors="#94a3b8")
    for spine in ax.spines.values():
        spine.set_edgecolor("#334155")

    legend_patches = [
        mpatches.Patch(color="#22c55e", label="Low (<0.3)"),
        mpatches.Patch(color="#eab308", label="Medium (0.3-0.5)"),
        mpatches.Patch(color="#f97316", label="High (0.5-0.7)"),
        mpatches.Patch(color="#ef4444", label="Critical (>0.7)"),
    ]
    ax.legend(handles=legend_patches, facecolor="#1e293b", labelcolor="#94a3b8", fontsize=8)

    fig.tight_layout()
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor="#1e293b")
    plt.close(fig)
    buf.seek(0)
    return buf


def matplotlib_heatmap(df: pd.DataFrame) -> BytesIO:
    """Attendance heatmap: day of week × hour of day."""
    df2 = df.copy()
    df2["dow"] = df2["checked_in_at"].dt.day_of_week # 0=Mon
    df2["hour"] = df2["checked_in_at"].dt.hour

    heat = df2.groupby(["dow", "hour"]).size().unstack(fill_value=0)
    # Ensure all hours/days are present
    heat = heat.reindex(range(7), fill_value=0)
    heat = heat.reindex(columns=range(24), fill_value=0)

    day_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    fig, ax = plt.subplots(figsize=(12, 3.5), facecolor="#1e293b")
    ax.set_facecolor("#1e293b")

    im = ax.imshow(heat.values, cmap="YlOrRd", aspect="auto")
    ax.set_xticks(range(24))
    ax.set_xticklabels([f"{h:02d}:00" for h in range(24)], rotation=45, ha="right", fontsize=7, color="#94a3b8")
    ax.set_yticks(range(7))
    ax.set_yticklabels(day_labels, color="#94a3b8")
    ax.set_title("Check-in Heatmap (Day × Hour)", color="#f8fafc", fontsize=13)

    cbar = fig.colorbar(im, ax=ax)
    cbar.ax.yaxis.set_tick_params(color="#94a3b8")
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color="#94a3b8")

    fig.tight_layout()
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor="#1e293b")
    plt.close(fig)
    buf.seek(0)
    return buf


def main():
    require_auth()

    st.title("Advanced Analytics")
    st.markdown("Deep-dive analytics powered by backend data and Prometheus metrics.")

    headers = get_headers()

    # ── Time range picker ─────────────────────────────────────────────────────
    days = st.sidebar.selectbox("Time Range", [7, 14, 30, 90], index=0, format_func=lambda x: f"Last {x} days")
    end_ts = datetime.utcnow()
    start_ts = end_ts - timedelta(days=days)

    # ── Fetch check-in data ───────────────────────────────────────────────────
    with st.spinner("Loading check-in data…"):
        df_all = fetch_all_checkins(headers)

    if df_all.empty:
        st.info("No check-in data available yet.")
        return

    # Filter to selected time range
    if "checked_in_at" in df_all.columns:
        df = df_all[df_all["checked_in_at"] >= pd.Timestamp(start_ts, tz="UTC")].copy()
    else:
        df = df_all.copy()

    # ── 1. Risk Score Distribution (Matplotlib) ───────────────────────────────
    st.subheader("Risk Score Distribution")
    col_hist, col_pie = st.columns([3, 2])

    with col_hist:
        if "risk_score" in df.columns and not df["risk_score"].dropna().empty:
            buf = matplotlib_risk_histogram(df)
            st.image(buf)
        else:
            st.info("No risk score data.")

    with col_pie:
        if "risk_score" in df.columns:
            scores = df["risk_score"].dropna().astype(float)
            low = (scores < 0.3).sum()
            med = ((scores >= 0.3) & (scores < 0.5)).sum()
            high = ((scores >= 0.5) & (scores < 0.7)).sum()
            crit = (scores >= 0.7).sum()
            labels = ["Low", "Medium", "High", "Critical"]
            values = [low, med, high, crit]
            colors = ["#22c55e", "#eab308", "#f97316", "#ef4444"]
            fig = go.Figure(data=[go.Pie(
                labels=labels, values=values,
                marker_colors=colors, hole=0.45,
                textinfo="label+percent",
            )])
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                legend=dict(font=dict(color="#94a3b8")),
                margin=dict(t=10, b=10, l=10, r=10),
            )
            st.plotly_chart(fig, use_container_width=True)

    # ── 2. Check-in Status Breakdown ─────────────────────────────────────────
    st.subheader("Check-in Status Breakdown")
    if "status" in df.columns:
        status_counts = df["status"].value_counts().reset_index()
        status_counts.columns = ["Status", "Count"]
        color_map = {
            "approved": "#22c55e", "flagged": "#eab308",
            "rejected": "#ef4444", "pending": "#6366f1", "appealed": "#06b6d4",
        }
        fig = px.bar(
            status_counts, x="Status", y="Count",
            color="Status", color_discrete_map=color_map,
            labels={"Count": "Check-ins"},
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(tickfont=dict(color="#94a3b8")),
            yaxis=dict(tickfont=dict(color="#94a3b8")),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── 3. Daily Check-in Trend ───────────────────────────────────────────────
    st.subheader("Daily Check-in Trend")
    if "checked_in_at" in df.columns:
        df_daily = df.groupby(df["checked_in_at"].dt.date).size().reset_index()
        df_daily.columns = ["Date", "Check-ins"]
        fig = px.area(
            df_daily, x="Date", y="Check-ins",
            line_shape="spline", color_discrete_sequence=["#6366f1"],
        )
        fig.update_traces(fill="tozeroy", fillcolor="rgba(99,102,241,0.15)")
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(tickfont=dict(color="#94a3b8"), gridcolor="#334155"),
            yaxis=dict(tickfont=dict(color="#94a3b8"), gridcolor="#334155"),
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── 4. Attendance Heatmap (Matplotlib) ───────────────────────────────────
    st.subheader("Attendance Heatmap (Day × Hour)")
    if "checked_in_at" in df.columns and not df.empty:
        buf = matplotlib_heatmap(df)
        st.image(buf)
    else:
        st.info("Not enough data for heatmap.")

    # ── 5. Distance from Venue Distribution ──────────────────────────────────
    st.subheader("Check-in Distance from Venue")
    if "distance_from_venue_meters" in df.columns:
        dist = df["distance_from_venue_meters"].dropna().astype(float)
        fig = px.histogram(
            df, x="distance_from_venue_meters", nbins=30,
            labels={"distance_from_venue_meters": "Distance (m)"},
            color_discrete_sequence=["#22d3ee"],
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(tickfont=dict(color="#94a3b8"), gridcolor="#334155"),
            yaxis=dict(tickfont=dict(color="#94a3b8"), gridcolor="#334155"),
        )
        st.plotly_chart(fig, use_container_width=True)

        c1, c2, c3 = st.columns(3)
        c1.metric("Median distance", f"{dist.median():.1f} m")
        c2.metric("90th percentile", f"{dist.quantile(0.9):.1f} m")
        c3.metric("Max recorded", f"{dist.max():.1f} m")

    # ── 6. Liveness Pass Rate ────────────────────────────────────────────────
    st.subheader("️ Liveness & Risk Signals")
    if "liveness_passed" in df.columns:
        total = len(df)
        passed = df["liveness_passed"].sum()
        rate = (passed / total * 100) if total > 0 else 0
        c1, c2, c3 = st.columns(3)
        c1.metric("Liveness Pass Rate", f"{rate:.1f}%")
        if "risk_score" in df.columns:
            c2.metric("Avg Risk Score", f"{df['risk_score'].mean():.3f}")
            c3.metric("High-risk Check-ins", int((df["risk_score"] >= 0.5).sum()))

    # ── 7. Device Analytics ──────────────────────────────────────────────────
    st.subheader("Device Trust Distribution")
    with st.spinner("Loading device data…"):
        df_dev = fetch_devices(headers)

    if not df_dev.empty and "is_trusted" in df_dev.columns:
        trusted = df_dev["is_trusted"].sum()
        untrusted = len(df_dev) - trusted
        active = df_dev.get("is_active", pd.Series(dtype=bool)).sum() if "is_active" in df_dev.columns else 0

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Registered Devices", len(df_dev))
        c2.metric("Trusted Devices", int(trusted))
        c3.metric("Active Devices", int(active))

        col_a, col_b = st.columns(2)
        with col_a:
            fig = go.Figure(data=[go.Pie(
                labels=["Trusted", "Pending Trust"],
                values=[trusted, untrusted],
                marker_colors=["#22c55e", "#eab308"],
                hole=0.45,
                textinfo="label+percent",
            )])
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                legend=dict(font=dict(color="#94a3b8")),
                margin=dict(t=10, b=10, l=10, r=10),
                title=dict(text="Trust Status", font=dict(color="#f8fafc")),
            )
            st.plotly_chart(fig, use_container_width=True)

        with col_b:
            if "trust_score" in df_dev.columns:
                ts_counts = df_dev["trust_score"].value_counts().reset_index()
                ts_counts.columns = ["Trust Score", "Count"]
                fig = px.bar(
                    ts_counts, x="Trust Score", y="Count",
                    color="Trust Score",
                    color_discrete_map={"high": "#22c55e", "medium": "#eab308", "low": "#ef4444"},
                )
                fig.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=dict(tickfont=dict(color="#94a3b8")),
                    yaxis=dict(tickfont=dict(color="#94a3b8")),
                    showlegend=False,
                    title=dict(text="Trust Score Breakdown", font=dict(color="#f8fafc")),
                )
                st.plotly_chart(fig, use_container_width=True)

    # ── 8. Prometheus Metrics Section ────────────────────────────────────────
    st.markdown("---")
    st.subheader("Live Prometheus Metrics")
    st.caption("Querying the Prometheus time-series database for real-time operational signals.")

    prom_available = False

    checkin_results = prom_query("sum(saiv_checkin_total) by (status)")
    if checkin_results:
        prom_available = True
        st.markdown("**Check-in totals (from Prometheus)**")
        rows = [
            {"Status": r["metric"].get("status", "unknown"), "Total": float(r["value"][1])}
            for r in checkin_results
        ]
        df_prom = pd.DataFrame(rows)
        st.dataframe(df_prom, use_container_width=True, hide_index=True)

    start_iso = start_ts.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_iso = end_ts.strftime("%Y-%m-%dT%H:%M:%SZ")
    range_step = "1h" if days <= 7 else "4h"

    risk_range = prom_range_query(
        "saiv_checkin_risk_score_sum / saiv_checkin_risk_score_count",
        start_iso, end_iso, range_step,
    )
    if risk_range:
        prom_available = True
        ts_rows = [
            {"time": datetime.utcfromtimestamp(float(v[0])), "avg_risk": float(v[1])}
            for series in risk_range for v in series["values"]
            if v[1] not in ("NaN", "Inf", "-Inf")
        ]
        if ts_rows:
            df_risk_ts = pd.DataFrame(ts_rows)
            fig = px.line(
                df_risk_ts, x="time", y="avg_risk",
                labels={"time": "Time", "avg_risk": "Average Risk Score"},
                title="Avg Risk Score Over Time (Prometheus)",
                color_discrete_sequence=["#ef4444"],
            )
            fig.add_hline(y=0.5, line_dash="dash", line_color="#eab308", annotation_text="Threshold 0.5")
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(tickfont=dict(color="#94a3b8"), gridcolor="#334155"),
                yaxis=dict(tickfont=dict(color="#94a3b8"), gridcolor="#334155", range=[0, 1]),
                title_font_color="#f8fafc",
            )
            st.plotly_chart(fig, use_container_width=True)

    if not prom_available:
        st.info(
            "Prometheus is not reachable from this container. "
            "Start the full stack with `npm run stack:up` and open Grafana at "
            "**http://localhost:3001** (admin / saiv_grafana) for real-time dashboards."
        )


if __name__ == "__main__":
    main()
