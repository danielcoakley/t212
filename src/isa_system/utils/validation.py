"""Validation helpers for data ingestion and transformations."""

from __future__ import annotations

import pandas as pd

from isa_system.utils.time import ensure_utc_series


def validate_unique_sorted_timestamps(df: pd.DataFrame, ts_col: str) -> pd.DataFrame:
    """Validate non-null, unique, sorted UTC timestamps."""

    if ts_col not in df.columns:
        raise ValueError(f"Missing timestamp column: {ts_col}")
    out = df.copy()
    out[ts_col] = ensure_utc_series(out[ts_col])
    if out[ts_col].duplicated().any():
        raise ValueError("Duplicate timestamps are not allowed.")
    if not out[ts_col].is_monotonic_increasing:
        raise ValueError("Timestamps must be sorted in ascending order.")
    return out


def require_columns(df: pd.DataFrame, columns: set[str]) -> None:
    """Raise when a DataFrame is missing required columns."""

    missing = columns.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
