"""Synthetic datasets for offline tests and smoke runs."""

from __future__ import annotations

import numpy as np
import pandas as pd


def synthetic_prices(symbols: list[str] | None = None, periods: int = 320) -> pd.DataFrame:
    """Generate deterministic daily adjusted prices."""

    symbols = symbols or ["TSCO.L", "SHEL.L", "AAPL", "MSFT"]
    dates = pd.bdate_range("2023-01-02", periods=periods, tz="UTC")
    rows = []
    for idx, symbol in enumerate(symbols):
        rng = np.random.default_rng(100 + idx)
        returns = rng.normal(0.0005 + idx * 0.00005, 0.012, len(dates))
        prices = 100 * np.cumprod(1 + returns)
        for ts, price in zip(dates, prices, strict=True):
            rows.append(
                {
                    "symbol": symbol,
                    "ts_utc": ts,
                    "open": price * 0.995,
                    "high": price * 1.01,
                    "low": price * 0.99,
                    "close": price,
                    "adj_close": price,
                    "volume": 1_000_000 + idx * 100_000,
                    "source": "synthetic",
                }
            )
    return pd.DataFrame(rows)


def synthetic_fundamentals(symbols: list[str] | None = None) -> pd.DataFrame:
    """Generate deterministic factor inputs."""

    symbols = symbols or ["TSCO.L", "SHEL.L", "AAPL", "MSFT"]
    return pd.DataFrame(
        {
            "symbol": symbols,
            "gross_margin": [0.07, 0.28, 0.45, 0.68],
            "operating_margin": [0.04, 0.16, 0.30, 0.40],
            "return_on_assets": [0.05, 0.08, 0.22, 0.25],
            "leverage": [0.45, 0.30, 0.18, 0.12],
            "earnings_yield": [0.06, 0.08, 0.035, 0.03],
            "fcf_yield": [0.05, 0.07, 0.04, 0.035],
            "book_to_price": [0.30, 0.45, 0.12, 0.08],
            "dividend_growth_3y": [0.02, 0.03, 0.05, 0.08],
            "dividend_stability": [0.8, 0.7, 0.9, 0.95],
            "payout_safety": [0.6, 0.65, 0.8, 0.85],
            "sector": ["Consumer Staples", "Energy", "Technology", "Technology"],
            "country": ["GB", "GB", "US", "US"],
            "price": [2.9, 28.0, 190.0, 420.0],
            "adv_gbp": [10_000_000, 25_000_000, 500_000_000, 500_000_000],
        }
    )
