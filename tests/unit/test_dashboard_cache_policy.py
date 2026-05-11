"""Tests for dashboard market-session cache windows."""

from __future__ import annotations

from datetime import UTC, datetime

from isa_system.dashboard.cache_policy import (
    cache_timestamp_detail,
    cache_timestamp_status,
    current_market_cache_window,
    format_cache_age,
)
from isa_system.utils.time import to_london


def test_london_open_cache_window_before_us_open() -> None:
    """London morning uses the London-open cache window."""

    window = current_market_cache_window(datetime(2026, 5, 11, 8, 30, tzinfo=UTC))

    assert window.key == "20260511-london_open"
    assert window.label == "London open cache"
    assert to_london(window.next_refresh_at_utc).hour in {14, 15}


def test_us_open_cache_window_after_us_open() -> None:
    """Afternoon UK time uses the US-open cache window."""

    window = current_market_cache_window(datetime(2026, 5, 11, 14, 0, tzinfo=UTC))

    assert window.key == "20260511-us_open"
    assert window.label == "US open cache"


def test_pre_market_uses_previous_weekday_cache() -> None:
    """Before the London open, the previous weekday cache remains current."""

    window = current_market_cache_window(datetime(2026, 5, 11, 6, 30, tzinfo=UTC))

    assert window.key == "20260508-us_open"
    assert window.opened_at_utc.weekday() == 4


def test_cache_timestamp_helpers_mark_sources_before_window_as_stale() -> None:
    """Source timestamps older than the active window are easy to spot."""

    window = current_market_cache_window(datetime(2026, 5, 11, 8, 30, tzinfo=UTC))
    observed = datetime(2026, 5, 11, 6, 45, tzinfo=UTC)

    assert (
        cache_timestamp_status(observed, window, as_of_utc=datetime(2026, 5, 11, 8, 30, tzinfo=UTC))
        == "Stale"
    )
    assert format_cache_age(observed, datetime(2026, 5, 11, 8, 30, tzinfo=UTC)) == "1h 45m old"
    assert (
        "before the current london open cache opened"
        in cache_timestamp_detail(
            "Test source",
            observed,
            window,
            as_of_utc=datetime(2026, 5, 11, 8, 30, tzinfo=UTC),
        ).lower()
    )
