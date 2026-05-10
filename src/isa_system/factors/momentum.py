"""Momentum factor definitions using adjusted closes."""

from __future__ import annotations

import pandas as pd


def compute_momentum(prices: pd.DataFrame, skip_days: int = 5) -> pd.DataFrame:
    """Compute 1m, 3m, 6m, and 12m momentum excluding recent days."""

    if prices.empty:
        return pd.DataFrame(columns=["symbol", "date", "momentum"])
    out = prices.sort_values(["symbol", "ts_utc"]).copy()
    rows = []
    for symbol, group in out.groupby("symbol"):
        adjusted = group["adj_close"].astype(float)
        shifted = adjusted.shift(skip_days)
        m1 = shifted / adjusted.shift(21 + skip_days) - 1.0
        m3 = shifted / adjusted.shift(63 + skip_days) - 1.0
        m6 = shifted / adjusted.shift(126 + skip_days) - 1.0
        m12 = shifted / adjusted.shift(252 + skip_days) - 1.0
        vol = adjusted.pct_change().rolling(63).std()
        frame = pd.DataFrame(
            {
                "symbol": symbol,
                "date": group["ts_utc"].values,
                "momentum_1m": m1,
                "momentum_3m": m3,
                "momentum_6m": m6,
                "momentum_12m": m12,
                "volatility_63d": vol,
            }
        )
        frame["momentum"] = frame[
            ["momentum_1m", "momentum_3m", "momentum_6m", "momentum_12m"]
        ].mean(axis=1, skipna=True)
        rows.append(frame)
    return pd.concat(rows, ignore_index=True)


def trend_filter(prices: pd.DataFrame, window: int = 200) -> pd.DataFrame:
    """Return a simple moving-average trend filter."""

    out = prices.sort_values(["symbol", "ts_utc"]).copy()
    out["moving_average"] = out.groupby("symbol")["adj_close"].transform(
        lambda s: s.rolling(window).mean()
    )
    out["in_uptrend"] = out["adj_close"] > out["moving_average"]
    return out
