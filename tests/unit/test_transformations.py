"""Tests for ingestion transformations."""

from __future__ import annotations

import pandas as pd
import pytest

from isa_system.data.ingestion.prices import normalise_price_bars


def test_duplicate_timestamps_rejected() -> None:
    """Duplicate timestamps per symbol are rejected."""

    rows = [
        {
            "symbol": "AAPL",
            "ts_utc": pd.Timestamp("2026-01-01", tz="UTC"),
            "open": 1,
            "high": 1,
            "low": 1,
            "close": 1,
            "adj_close": 1,
            "volume": 1,
            "source": "test",
        },
        {
            "symbol": "AAPL",
            "ts_utc": pd.Timestamp("2026-01-01", tz="UTC"),
            "open": 1,
            "high": 1,
            "low": 1,
            "close": 1,
            "adj_close": 1,
            "volume": 1,
            "source": "test",
        },
    ]
    with pytest.raises(ValueError):
        normalise_price_bars(pd.DataFrame(rows))
