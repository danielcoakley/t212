"""Rebalance scheduling helpers."""

from __future__ import annotations

import pandas as pd


def scheduled_rebalance_dates(
    start: str, periods: int, frequency: str = "W-FRI"
) -> pd.DatetimeIndex:
    """Return scheduled rebalance timestamps in UTC."""

    return pd.date_range(start=start, periods=periods, freq=frequency, tz="UTC")
