"""Tests for dashboard market-session cache windows."""

from __future__ import annotations

from datetime import UTC, datetime

from isa_system.dashboard.cache_policy import current_market_cache_window
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
