"""
Reusable chart components using Plotly
"""

import plotly.graph_objects as go
import plotly.express as px
from typing import List, Dict, Any
import pandas as pd

def create_attendance_trend_chart(data: List[Dict[str, Any]], title: str = "Attendance Trend") -> go.Figure:
    """
    Create line chart for attendance trends

    Args:
        data: List of data points with 'date' and 'attendance_rate' keys
        title: Chart title

    Returns:
        Plotly figure
    """
    if not data:
        fig = go.Figure()
        fig.add_annotation(
            text="No data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        return fig

    df = pd.DataFrame(data)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['date'],
        y=df['attendance_rate'],
        mode='lines+markers',
        name='Attendance Rate',
        line=dict(color='#1f77b4', width=3),
        marker=dict(size=8),
        hovertemplate='<b>Date:</b> %{x}<br><b>Attendance:</b> %{y:.1f}%<extra></extra>'
    ))

    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Attendance Rate (%)",
        hovermode='x unified',
        template='plotly_white',
        height=400,
        yaxis=dict(range=[0, 100])
    )

    return fig

def create_risk_distribution_chart(data: Dict[str, int], title: str = "Risk Distribution") -> go.Figure:
    """
    Create pie chart for risk distribution

    Args:
        data: Dictionary with risk levels as keys and counts as values
        title: Chart title

    Returns:
        Plotly figure
    """
    if not data or sum(data.values()) == 0:
        fig = go.Figure()
        fig.add_annotation(
            text="No data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        return fig

    colors = {
        'Low': '#28a745',
        'Medium': '#ffc107',
        'High': '#dc3545'
    }

    fig = go.Figure(data=[go.Pie(
        labels=list(data.keys()),
        values=list(data.values()),
        marker=dict(colors=[colors.get(k, '#6c757d') for k in data.keys()]),
        hovertemplate='<b>%{label}</b><br>Count: %{value}<br>Percentage: %{percent}<extra></extra>'
    )])

    fig.update_layout(
        title=title,
        template='plotly_white',
        height=400
    )

    return fig

def create_checkin_timeline_chart(data: List[Dict[str, Any]], title: str = "Check-in Timeline") -> go.Figure:
    """
    Create bar chart for check-in timeline

    Args:
        data: List of check-ins with 'timestamp' and 'status' keys
        title: Chart title

    Returns:
        Plotly figure
    """
    if not data:
        fig = go.Figure()
        fig.add_annotation(
            text="No check-ins yet",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        return fig

    df = pd.DataFrame(data)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['minute'] = df['timestamp'].dt.floor('min')

    # Count check-ins per minute
    timeline = df.groupby('minute').size().reset_index(name='count')

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=timeline['minute'],
        y=timeline['count'],
        marker_color='#1f77b4',
        hovertemplate='<b>Time:</b> %{x}<br><b>Check-ins:</b> %{y}<extra></extra>'
    ))

    fig.update_layout(
        title=title,
        xaxis_title="Time",
        yaxis_title="Number of Check-ins",
        template='plotly_white',
        height=400,
        showlegend=False
    )

    return fig

def create_status_distribution_chart(data: Dict[str, int], title: str = "Status Distribution") -> go.Figure:
    """
    Create bar chart for status distribution

    Args:
        data: Dictionary with statuses as keys and counts as values
        title: Chart title

    Returns:
        Plotly figure
    """
    if not data:
        fig = go.Figure()
        fig.add_annotation(
            text="No data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        return fig

    colors = {
        'approved': '#28a745',
        'pending': '#ffc107',
        'rejected': '#dc3545',
        'flagged': '#ff6b6b'
    }

    statuses = list(data.keys())
    counts = list(data.values())
    bar_colors = [colors.get(s.lower(), '#6c757d') for s in statuses]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=statuses,
        y=counts,
        marker_color=bar_colors,
        text=counts,
        textposition='auto',
        hovertemplate='<b>%{x}</b><br>Count: %{y}<extra></extra>'
    ))

    fig.update_layout(
        title=title,
        xaxis_title="Status",
        yaxis_title="Count",
        template='plotly_white',
        height=400,
        showlegend=False
    )

    return fig

def create_daily_activity_chart(data: List[Dict[str, Any]], title: str = "Daily Activity") -> go.Figure:
    """
    Create multi-line chart for daily activity

    Args:
        data: List of daily data with 'date', 'checkins', 'sessions' keys
        title: Chart title

    Returns:
        Plotly figure
    """
    if not data:
        fig = go.Figure()
        fig.add_annotation(
            text="No data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        return fig

    df = pd.DataFrame(data)

    fig = go.Figure()

    # Add check-ins trace
    fig.add_trace(go.Scatter(
        x=df['date'],
        y=df['checkins'],
        mode='lines+markers',
        name='Check-ins',
        line=dict(color='#1f77b4', width=2),
        marker=dict(size=6),
        hovertemplate='<b>Date:</b> %{x}<br><b>Check-ins:</b> %{y}<extra></extra>'
    ))

    # Add sessions trace
    fig.add_trace(go.Scatter(
        x=df['date'],
        y=df['sessions'],
        mode='lines+markers',
        name='Sessions',
        line=dict(color='#ff7f0e', width=2),
        marker=dict(size=6),
        hovertemplate='<b>Date:</b> %{x}<br><b>Sessions:</b> %{y}<extra></extra>'
    ))

    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Count",
        hovermode='x unified',
        template='plotly_white',
        height=400,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )

    return fig

def create_session_comparison_chart(data: List[Dict[str, Any]], title: str = "Session Comparison") -> go.Figure:
    """
    Create grouped bar chart comparing sessions

    Args:
        data: List of sessions with 'session_name', 'expected', 'actual' keys
        title: Chart title

    Returns:
        Plotly figure
    """
    if not data:
        fig = go.Figure()
        fig.add_annotation(
            text="No data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        return fig

    df = pd.DataFrame(data)

    fig = go.Figure()

    fig.add_trace(go.Bar(
        name='Expected',
        x=df['session_name'],
        y=df['expected'],
        marker_color='#1f77b4',
        hovertemplate='<b>%{x}</b><br>Expected: %{y}<extra></extra>'
    ))

    fig.add_trace(go.Bar(
        name='Actual',
        x=df['session_name'],
        y=df['actual'],
        marker_color='#2ca02c',
        hovertemplate='<b>%{x}</b><br>Actual: %{y}<extra></extra>'
    ))

    fig.update_layout(
        title=title,
        xaxis_title="Session",
        yaxis_title="Attendance",
        barmode='group',
        template='plotly_white',
        height=400,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )

    return fig

def create_distance_histogram(distances: List[float], title: str = "Distance Distribution") -> go.Figure:
    """
    Create histogram for check-in distances

    Args:
        distances: List of distances in meters
        title: Chart title

    Returns:
        Plotly figure
    """
    if not distances:
        fig = go.Figure()
        fig.add_annotation(
            text="No data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        return fig

    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=distances,
        nbinsx=30,
        marker_color='#1f77b4',
        hovertemplate='<b>Distance Range:</b> %{x}<br><b>Count:</b> %{y}<extra></extra>'
    ))

    fig.update_layout(
        title=title,
        xaxis_title="Distance (meters)",
        yaxis_title="Frequency",
        template='plotly_white',
        height=400,
        showlegend=False
    )

    return fig

def create_heatmap_chart(data: pd.DataFrame, title: str = "Activity Heatmap") -> go.Figure:
    """
    Create heatmap chart

    Args:
        data: DataFrame with index as rows and columns as columns
        title: Chart title

    Returns:
        Plotly figure
    """
    if data.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        return fig

    fig = go.Figure(data=go.Heatmap(
        z=data.values,
        x=data.columns,
        y=data.index,
        colorscale='Blues',
        hovertemplate='<b>%{y}</b><br>%{x}<br>Value: %{z}<extra></extra>'
    ))

    fig.update_layout(
        title=title,
        template='plotly_white',
        height=400
    )

    return fig
