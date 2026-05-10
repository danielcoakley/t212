"""Tests for point-in-time joins."""

from __future__ import annotations

import pandas as pd
import pytest

from isa_system.data.schemas.pti import asof_join_facts, reject_future_information


def test_asof_join_uses_latest_available_fact() -> None:
    """As-of join does not look past available_at_utc."""

    facts = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "fact_name": "eps",
                "value": 1.0,
                "available_at_utc": pd.Timestamp("2026-01-01", tz="UTC"),
            },
            {
                "symbol": "AAPL",
                "fact_name": "eps",
                "value": 2.0,
                "available_at_utc": pd.Timestamp("2026-02-01", tz="UTC"),
            },
        ]
    )
    requests = pd.DataFrame(
        [{"symbol": "AAPL", "fact_name": "eps", "as_of_utc": pd.Timestamp("2026-01-15", tz="UTC")}]
    )
    joined = asof_join_facts(requests, facts)
    assert joined.loc[0, "value"] == 1.0


def test_future_information_rejected() -> None:
    """Future facts are rejected when asked."""

    facts = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "fact_name": "eps",
                "value": 2.0,
                "available_at_utc": pd.Timestamp("2026-02-01", tz="UTC"),
            }
        ]
    )
    with pytest.raises(ValueError):
        reject_future_information(facts, pd.Timestamp("2026-01-01", tz="UTC"))
