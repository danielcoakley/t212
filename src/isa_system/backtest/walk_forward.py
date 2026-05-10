"""Walk-forward harness placeholder."""

from __future__ import annotations

import pandas as pd


def walk_forward_splits(
    dates: pd.Series, train_days: int, test_days: int
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Return simple rolling train/test boundary pairs."""

    unique = pd.Series(pd.to_datetime(dates, utc=True).sort_values().unique())
    splits = []
    start = 0
    while start + train_days + test_days <= len(unique):
        splits.append(
            (
                pd.Timestamp(unique.iloc[start + train_days - 1]),
                pd.Timestamp(unique.iloc[start + train_days + test_days - 1]),
            )
        )
        start += test_days
    return splits
