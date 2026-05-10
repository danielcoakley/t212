"""Price ingestion transformations."""

from __future__ import annotations

import pandas as pd

from isa_system.utils.validation import require_columns, validate_unique_sorted_timestamps

PRICE_COLUMNS = {
    "symbol",
    "ts_utc",
    "open",
    "high",
    "low",
    "close",
    "adj_close",
    "volume",
    "source",
}


def normalise_price_bars(raw: pd.DataFrame) -> pd.DataFrame:
    """Normalise provider bars and enforce UTC timestamp ordering."""

    require_columns(raw, PRICE_COLUMNS)
    frames = []
    for _, group in raw.sort_values(["symbol", "ts_utc"]).groupby("symbol", sort=False):
        frames.append(validate_unique_sorted_timestamps(group.reset_index(drop=True), "ts_utc"))
    return pd.concat(frames, ignore_index=True) if frames else raw.copy()
