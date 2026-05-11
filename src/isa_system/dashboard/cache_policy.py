"""Dashboard market-session cache policy."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from isa_system.utils.time import LONDON, now_utc, require_utc, to_london

NEW_YORK = ZoneInfo("America/New_York")
LONDON_OPEN = time(8, 0)
US_OPEN = time(9, 30)


class MarketCacheWindow(BaseModel):
    """Current dashboard cache window."""

    key: str
    label: str
    opened_at_utc: datetime
    next_refresh_at_utc: datetime
    manual_refresh_hint: str


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
