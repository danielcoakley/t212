"""Tests for timezone helpers."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from isa_system.utils.time import ensure_utc, to_london


def test_naive_timestamp_rejected() -> None:
    """Naive timestamps are not allowed in storage."""

    with pytest.raises(ValueError):
        ensure_utc(datetime(2026, 5, 10, 12, 0, 0))


def test_london_dst_conversion() -> None:
    """UTC storage converts correctly around London DST."""

    london = to_london(datetime(2026, 7, 1, 12, 0, tzinfo=UTC))
    assert london.tzname() == "BST"
    assert london.hour == 13
