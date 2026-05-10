"""Dividend growth and stability factors."""

from __future__ import annotations

import pandas as pd

from isa_system.factors.normalise import zscore


def compute_dividend_growth(dividends: pd.DataFrame) -> pd.DataFrame:
    """Compute a starter dividend score from growth and stability fields."""

    if dividends.empty:
        return pd.DataFrame(columns=["symbol", "dividend_growth"])
    out = dividends.copy()
    for column in ["dividend_growth_3y", "dividend_stability", "payout_safety"]:
        if column not in out:
            out[column] = 0.0
    out["dividend_growth"] = (
        zscore(out["dividend_growth_3y"])
        + zscore(out["dividend_stability"])
        + zscore(out["payout_safety"])
    ) / 3.0
    return out[["symbol", "dividend_growth"]]
