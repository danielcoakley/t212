"""Timezone helpers that enforce UTC storage and London display time."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pandas as pd

LONDON = ZoneInfo("Europe/London")


def now_utc() -> datetime:
    """Return the current timezone-aware UTC timestamp."""

    return datetime.now(tz=UTC)


def ensure_utc(value: datetime | pd.Timestamp) -> datetime:
    """Return a timezone-aware UTC datetime or raise for naive input."""

    if isinstance(value, pd.Timestamp):
        if value.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware UTC.")
        return value.tz_convert("UTC").to_pydatetime()
    if value.tzinfo is None:
        raise ValueError("Timestamp must be timezone-aware UTC.")
    return value.astimezone(UTC)


def parse_utc(value: str) -> datetime:
    """Parse an ISO timestamp and return timezone-aware UTC."""

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return ensure_utc(parsed)


def require_utc(value: datetime) -> datetime:
    """Validate that a datetime is explicitly UTC."""

    utc_value = ensure_utc(value)
    if utc_value.tzinfo != UTC:
        raise ValueError("Timestamp must be stored in UTC.")
    return utc_value


def to_london(value: datetime | pd.Timestamp) -> datetime:
    """Convert a UTC timestamp for user-facing Europe/London display."""

    return ensure_utc(value).astimezone(LONDON)


def ensure_utc_series(series: pd.Series) -> pd.Series:
    """Validate and normalise a pandas timestamp series to UTC."""

    converted = pd.to_datetime(series, utc=True, errors="raise")
    if converted.isna().any():
        raise ValueError("Timestamp series contains missing values.")
    return converted
