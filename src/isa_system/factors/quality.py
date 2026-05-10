"""Quality factor definitions."""

from __future__ import annotations

import pandas as pd

from isa_system.factors.normalise import zscore


def compute_quality(fundamentals: pd.DataFrame) -> pd.DataFrame:
    """Compute a starter profitability and balance-sheet quality score."""

    if fundamentals.empty:
        return pd.DataFrame(columns=["symbol", "quality"])
    out = fundamentals.copy()
    for column in ["gross_margin", "operating_margin", "return_on_assets", "leverage"]:
        if column not in out:
            out[column] = 0.0
    out["quality"] = (
        zscore(out["gross_margin"])
        + zscore(out["operating_margin"])
        + zscore(out["return_on_assets"])
        - zscore(out["leverage"])
    ) / 4.0
    return out[["symbol", "quality"]]
