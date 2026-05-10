"""Universe construction helpers."""

from __future__ import annotations

import pandas as pd


def filter_isa_universe(
    instruments: pd.DataFrame, allowed_types: set[str], allowed_currencies: set[str]
) -> pd.DataFrame:
    """Filter instruments to long-only ISA-compatible candidates."""

    if instruments.empty:
        return instruments.copy()
    out = instruments.copy()
    return out[
        out["type"].isin(allowed_types) & out["currency"].isin(allowed_currencies)
    ].reset_index(drop=True)
