"""Robust heuristic long-only optimiser."""

from __future__ import annotations

import pandas as pd

from isa_system.domain.models import TargetWeight
from isa_system.portfolio.constraints import cap_and_normalise


def optimise_from_ranks(
    ranked: pd.DataFrame,
    *,
    max_positions: int,
    max_single_name_weight: float,
    cash_buffer: float,
) -> list[TargetWeight]:
    """Select top-ranked names and produce capped equal weights."""

    if ranked.empty:
        return []
    selected = ranked.head(max_positions)
    base = 1.0 / max(len(selected), 1)
    weights = [
        TargetWeight(
            symbol=str(row["symbol"]),
            weight=base,
            sector=str(row.get("sector", "Unknown")),
            country=str(row.get("country", "")),
        )
        for row in selected.to_dict("records")
    ]
    return cap_and_normalise(
        weights, max_single_name_weight=max_single_name_weight, cash_buffer=cash_buffer
    )
