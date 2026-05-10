"""Hard filters for signal candidates."""

from __future__ import annotations

import pandas as pd


def apply_hard_filters(
    candidates: pd.DataFrame, *, min_price: float = 1.0, min_adv_gbp: float = 0.0
) -> pd.DataFrame:
    """Apply liquidity and price filters."""

    if candidates.empty:
        return candidates.copy()
    out = candidates.copy()
    price = out.get("price", pd.Series(float("inf"), index=out.index))
    adv = out.get("adv_gbp", pd.Series(float("inf"), index=out.index))
    return out[(price >= min_price) & (adv >= min_adv_gbp)].reset_index(drop=True)
