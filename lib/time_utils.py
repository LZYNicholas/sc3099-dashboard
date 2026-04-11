from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

import pandas as pd

SG_TZ = ZoneInfo("Asia/Singapore")


def now_sgt() -> datetime:
    return datetime.now(SG_TZ)


def to_utc_iso_range_start(d: date | None) -> str | None:
    if d is None:
        return None
    local_dt = datetime.combine(d, time.min, tzinfo=SG_TZ)
    return local_dt.astimezone(timezone.utc).isoformat()


def to_utc_iso_range_end(d: date | None) -> str | None:
    if d is None:
        return None
    local_dt = datetime.combine(d, time.max, tzinfo=SG_TZ)
    return local_dt.astimezone(timezone.utc).isoformat()


def format_sgt(value, fmt: str = "%Y-%m-%d %H:%M SGT") -> str:
    ts = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(ts):
        return ""
    return ts.tz_convert(SG_TZ).strftime(fmt)
