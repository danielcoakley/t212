"""Long-only portfolio constraints."""

from __future__ import annotations

from collections import defaultdict

from isa_system.domain.models import TargetWeight


def enforce_long_only(weights: list[TargetWeight]) -> list[TargetWeight]:
    """Reject negative weights."""

    if any(item.weight < 0 for item in weights):
        raise ValueError("Long-only portfolios cannot contain negative target weights.")
    return weights


def cap_and_normalise(
    weights: list[TargetWeight],
    *,
    max_single_name_weight: float,
    cash_buffer: float,
) -> list[TargetWeight]:
    """Cap target weights and normalise inside the investable sleeve."""

    enforce_long_only(weights)
    capped = [
        TargetWeight(
            item.symbol, min(item.weight, max_single_name_weight), item.sector, item.country
        )
        for item in weights
    ]
    total = sum(item.weight for item in capped)
    if total <= 0:
        return []
    investable = max(0.0, 1.0 - cash_buffer)
    return [
        TargetWeight(item.symbol, item.weight / total * investable, item.sector, item.country)
        for item in capped
    ]


def sector_weights(weights: list[TargetWeight]) -> dict[str, float]:
    """Aggregate weights by sector."""

    totals: defaultdict[str, float] = defaultdict(float)
    for item in weights:
        totals[item.sector or "Unknown"] += item.weight
    return dict(totals)
