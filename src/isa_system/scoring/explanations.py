"""Scoring explanation helpers."""

from __future__ import annotations

from isa_system.scoring.composite_score import CompositeScore


def build_score_explanation(score: CompositeScore) -> str:
    """Build a concise ranking explanation for a candidate."""

    factor_bits = ", ".join(
        f"{factor.name} {factor.score:.0f}" for factor in score.factor_scores[:4]
    )
    return (
        f"{score.symbol} scored {score.total_score:.1f}/100. "
        f"Key factors: {factor_bits}. "
        f"Data quality {score.data_quality_score:.1f}/100."
    )
