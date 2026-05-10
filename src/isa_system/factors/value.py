"""Value factor definitions."""

from __future__ import annotations

import pandas as pd

from isa_system.factors.normalise import zscore


def compute_value(fundamentals: pd.DataFrame) -> pd.DataFrame:
    """Compute a starter value score from available yield proxies."""

    if fundamentals.empty:
        return pd.DataFrame(columns=["symbol", "value"])
    out = fundamentals.copy()
    for column in ["earnings_yield", "fcf_yield", "book_to_price"]:
        if column not in out:
            out[column] = 0.0
    out["value"] = (
        zscore(out["earnings_yield"]) + zscore(out["fcf_yield"]) + zscore(out["book_to_price"])
    ) / 3.0
    return out[["symbol", "value"]]
