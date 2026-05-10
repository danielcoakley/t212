"""Earnings and catalyst features."""

from __future__ import annotations

import pandas as pd


def no_buy_blackout(
    events: pd.DataFrame, as_of_utc: pd.Timestamp, days_before: int = 5, days_after: int = 2
) -> set[str]:
    """Return symbols inside an earnings or major-event no-buy window."""

    if events.empty:
        return set()
    as_of = pd.Timestamp(as_of_utc).tz_convert("UTC")
    out = events.copy()
    out["event_ts_utc"] = pd.to_datetime(out.get("event_ts_utc", out["available_at_utc"]), utc=True)
    lower = as_of - pd.Timedelta(days=days_after)
    upper = as_of + pd.Timedelta(days=days_before)
    return set(out.loc[(out["event_ts_utc"] >= lower) & (out["event_ts_utc"] <= upper), "symbol"])
