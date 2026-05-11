"""Dashboard market-session cache policy."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from isa_system.utils.time import LONDON, now_utc, require_utc, to_london

NEW_YORK = ZoneInfo("America/New_York")
LONDON_OPEN = time(8, 0)
US_OPEN = time(9, 30)
FRESHNESS_CLOCK_TOLERANCE = timedelta(minutes=5)


class MarketCacheWindow(BaseModel):
    """Current dashboard cache window."""

    key: str
    label: str
    opened_at_utc: datetime
    next_refresh_at_utc: datetime
    manual_refresh_hint: str


def format_cache_age(observed_at_utc: datetime, as_of_utc: datetime | None = None) -> str:
    """Return a compact operator-facing age label for a cache/source timestamp."""

    observed = require_utc(observed_at_utc)
    as_of = require_utc(as_of_utc or now_utc())
    age = as_of - observed
    if age < -FRESHNESS_CLOCK_TOLERANCE:
        return "ahead of local clock"
    if age.total_seconds() < 0:
        return "less than 5m old"
    return _format_duration(age)


def cache_timestamp_status(
    observed_at_utc: datetime,
    window: MarketCacheWindow,
    *,
    as_of_utc: datetime | None = None,
) -> str:
    """Classify whether a source timestamp belongs to the current cache window."""

    observed = require_utc(observed_at_utc)
    as_of = require_utc(as_of_utc or now_utc())
    opened_at = require_utc(window.opened_at_utc)
    next_refresh = require_utc(window.next_refresh_at_utc)
    if observed > as_of + FRESHNESS_CLOCK_TOLERANCE or as_of < opened_at:
        return "Check clock"
    if as_of >= next_refresh or observed < opened_at:
        return "Stale"
    return "Fresh"


def cache_timestamp_detail(
    label: str,
    observed_at_utc: datetime,
    window: MarketCacheWindow,
    *,
    as_of_utc: datetime | None = None,
) -> str:
    """Return concise freshness language for one source timestamp."""

    observed = require_utc(observed_at_utc)
    as_of = require_utc(as_of_utc or now_utc())
    opened_at = require_utc(window.opened_at_utc)
    next_refresh = require_utc(window.next_refresh_at_utc)
    observed_london = _format_london(observed)
    if observed > as_of + FRESHNESS_CLOCK_TOLERANCE:
        return f"{label} timestamp {observed_london} is ahead of the current clock."
    if as_of < opened_at:
        return f"{window.label} opens at {_format_london(opened_at)}, after the current clock."
    if as_of >= next_refresh:
        return (
            f"{label} timestamp {observed_london}; refresh was due at "
            f"{_format_london(next_refresh)}."
        )
    if observed < opened_at:
        return (
            f"{label} timestamp {observed_london} is before the current "
            f"{window.label.lower()} opened."
        )
    return f"{label} timestamp {observed_london} sits inside the current cache window."


def current_market_cache_window(as_of_utc: datetime | None = None) -> MarketCacheWindow:
    """Return the latest twice-daily market cache window."""

    as_of = require_utc(as_of_utc or now_utc())
    anchors = _candidate_anchors(as_of)
    opened_at_utc, label = max((anchor, label) for anchor, label in anchors if anchor <= as_of)
    future_anchors = sorted(anchor for anchor, _ in anchors if anchor > as_of)
    next_refresh = future_anchors[0] if future_anchors else opened_at_utc + timedelta(days=1)
    opened_london = to_london(opened_at_utc)
    return MarketCacheWindow(
        key=f"{opened_london:%Y%m%d}-{label}",
        label=_display_label(label),
        opened_at_utc=opened_at_utc,
        next_refresh_at_utc=next_refresh,
        manual_refresh_hint=(
            "Cached data refreshes automatically around the London open and US open. "
            "Use manual refresh when broker state or market context needs an immediate update."
        ),
    )


def _candidate_anchors(as_of_utc: datetime) -> list[tuple[datetime, str]]:
    london_day = to_london(as_of_utc).date()
    rows: list[tuple[datetime, str]] = []
    for offset in range(-4, 5):
        day = london_day + timedelta(days=offset)
        if day.weekday() >= 5:
            continue
        rows.append(
            (
                datetime.combine(day, LONDON_OPEN, tzinfo=LONDON).astimezone(UTC),
                "london_open",
            )
        )
        rows.append(
            (
                datetime.combine(day, US_OPEN, tzinfo=NEW_YORK).astimezone(UTC),
                "us_open",
            )
        )
    return rows


def _display_label(label: str) -> str:
    return {
        "london_open": "London open cache",
        "us_open": "US open cache",
    }[label]


def _format_duration(delta: timedelta) -> str:
    total_minutes = max(0, int(delta.total_seconds() // 60))
    days, remainder = divmod(total_minutes, 24 * 60)
    hours, minutes = divmod(remainder, 60)
    if days:
        return f"{days}d {hours}h old"
    if hours:
        return f"{hours}h {minutes}m old"
    return f"{minutes}m old"


def _format_london(value: datetime) -> str:
    return f"{to_london(value):%Y-%m-%d %H:%M %Z}"
