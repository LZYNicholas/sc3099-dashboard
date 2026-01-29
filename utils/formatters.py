"""
Formatting utilities for the dashboard
"""

from datetime import datetime
from typing import Optional
import streamlit as st

def format_datetime(dt_str: Optional[str], format: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    Format datetime string

    Args:
        dt_str: ISO format datetime string
        format: Output format string

    Returns:
        Formatted datetime string
    """
    if not dt_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        return dt.strftime(format)
    except:
        return dt_str

def format_date(dt_str: Optional[str]) -> str:
    """Format datetime as date only"""
    return format_datetime(dt_str, "%Y-%m-%d")

def format_time(dt_str: Optional[str]) -> str:
    """Format datetime as time only"""
    return format_datetime(dt_str, "%H:%M:%S")

def format_datetime_relative(dt_str: Optional[str]) -> str:
    """Format datetime as relative time (e.g., '2 hours ago')"""
    if not dt_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        now = datetime.now(dt.tzinfo)
        diff = now - dt

        seconds = diff.total_seconds()
        if seconds < 60:
            return "Just now"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        else:
            days = int(seconds / 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"
    except:
        return dt_str

def format_percentage(value: float, decimals: int = 1) -> str:
    """Format value as percentage"""
    if value is None:
        return "N/A"
    return f"{value:.{decimals}f}%"

def format_distance(meters: Optional[float]) -> str:
    """
    Format distance in meters

    Args:
        meters: Distance in meters

    Returns:
        Formatted distance string
    """
    if meters is None:
        return "N/A"
    if meters < 1000:
        return f"{meters:.0f}m"
    else:
        return f"{meters/1000:.2f}km"

def format_risk_score(score: Optional[float]) -> str:
    """
    Format risk score with color

    Args:
        score: Risk score (0-1)

    Returns:
        Formatted risk score
    """
    if score is None:
        return "N/A"
    return f"{score:.2f}"

def get_risk_color(score: Optional[float]) -> str:
    """
    Get color for risk score

    Args:
        score: Risk score (0-1)

    Returns:
        Color name
    """
    if score is None:
        return "gray"
    if score < 0.3:
        return "green"
    elif score < 0.6:
        return "orange"
    else:
        return "red"

def status_badge(status: str) -> str:
    """
    Create colored badge for status

    Args:
        status: Status string

    Returns:
        HTML for colored badge
    """
    status_lower = status.lower()
    if status_lower == "approved":
        badge_class = "success-badge"
    elif status_lower == "pending":
        badge_class = "warning-badge"
    elif status_lower in ["rejected", "flagged"]:
        badge_class = "danger-badge"
    else:
        badge_class = "info-badge"

    return f'<span class="{badge_class}">{status.upper()}</span>'

def risk_badge(score: Optional[float]) -> str:
    """
    Create colored badge for risk score

    Args:
        score: Risk score (0-1)

    Returns:
        HTML for colored badge
    """
    if score is None:
        return '<span class="info-badge">N/A</span>'

    if score < 0.3:
        badge_class = "success-badge"
        label = "LOW"
    elif score < 0.6:
        badge_class = "warning-badge"
        label = "MEDIUM"
    else:
        badge_class = "danger-badge"
        label = "HIGH"

    return f'<span class="{badge_class}">{label} ({score:.2f})</span>'

def format_duration(seconds: Optional[int]) -> str:
    """
    Format duration in seconds

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted duration string
    """
    if seconds is None:
        return "N/A"

    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}m {secs}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"

def format_number(value: Optional[float], decimals: int = 0) -> str:
    """Format number with thousand separators"""
    if value is None:
        return "N/A"
    if decimals == 0:
        return f"{int(value):,}"
    else:
        return f"{value:,.{decimals}f}"

def truncate_text(text: str, max_length: int = 50, suffix: str = "...") -> str:
    """Truncate text to maximum length"""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix

def format_file_size(bytes: int) -> str:
    """Format file size in bytes to human readable"""
    if bytes < 1024:
        return f"{bytes} B"
    elif bytes < 1024 * 1024:
        return f"{bytes / 1024:.1f} KB"
    elif bytes < 1024 * 1024 * 1024:
        return f"{bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes / (1024 * 1024 * 1024):.1f} GB"

def get_status_icon(status: str) -> str:
    """Get emoji icon for status"""
    status_lower = status.lower()
    icons = {
        "approved": "✅",
        "pending": "⏳",
        "rejected": "❌",
        "flagged": "🚩",
        "active": "🟢",
        "inactive": "⚪",
        "completed": "✓",
        "in_progress": "⏳"
    }
    return icons.get(status_lower, "")

def format_boolean(value: Optional[bool], true_text: str = "Yes", false_text: str = "No") -> str:
    """Format boolean value as text"""
    if value is None:
        return "N/A"
    return true_text if value else false_text

def format_list(items: list, separator: str = ", ", max_items: int = 5) -> str:
    """Format list as string"""
    if not items:
        return "None"
    if len(items) <= max_items:
        return separator.join(str(item) for item in items)
    else:
        shown = separator.join(str(item) for item in items[:max_items])
        return f"{shown} and {len(items) - max_items} more"
