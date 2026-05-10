"""Event ingestion and blackout helpers."""

from __future__ import annotations

import pandas as pd

from isa_system.utils.time import ensure_utc_series


def merge_event_sources(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Merge event metadata and de-duplicate by source document id."""

    if not frames:
        return pd.DataFrame(
            columns=["symbol", "event_type", "available_at_utc", "source_document_id"]
        )
    out = pd.concat(frames, ignore_index=True)
    out["available_at_utc"] = ensure_utc_series(out["available_at_utc"])
    return out.drop_duplicates(subset=["source_name", "source_document_id"]).sort_values(
        "available_at_utc"
    )


def event_blackout_symbols(
    events: pd.DataFrame, as_of_utc: pd.Timestamp, window_days: int
) -> set[str]:
    """Return symbols with events near the as-of timestamp."""

    if events.empty:
        return set()
    out = events.copy()
    out["available_at_utc"] = ensure_utc_series(out["available_at_utc"])
    delta = (out["available_at_utc"] - pd.Timestamp(as_of_utc).tz_convert("UTC")).abs()
    return set(out.loc[delta <= pd.Timedelta(days=window_days), "symbol"])
