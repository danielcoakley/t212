"""Sector mapping and sector-neutral scoring helpers."""

from __future__ import annotations

import pandas as pd

from isa_system.factors.normalise import zscore


def sector_neutralise(df: pd.DataFrame, score_col: str, sector_col: str = "sector") -> pd.Series:
    """Z-score scores within each sector."""

    if df.empty:
        return pd.Series(dtype=float)
    return df.groupby(sector_col)[score_col].transform(zscore)
