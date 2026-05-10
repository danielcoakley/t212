"""Macro ingestion helpers."""

from __future__ import annotations

import pandas as pd

from isa_system.utils.time import ensure_utc_series


def normalise_macro_series(raw: pd.DataFrame) -> pd.DataFrame:
    """Normalise macro rows for regime filters."""

    if raw.empty:
        return raw.copy()
    out = raw.copy()
    out["ts_utc"] = ensure_utc_series(out["ts_utc"])
    return out.sort_values(["series_id", "ts_utc"])
