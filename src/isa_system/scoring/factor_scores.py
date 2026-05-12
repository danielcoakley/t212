"""Factor score models and deterministic factor scoring."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from isa_system.enrichment.enrichment_packet import CandidateEnrichmentPacket

FACTOR_WEIGHTS: dict[str, float] = {
    "growth": 0.20,
    "quality": 0.15,
    "valuation": 0.15,
    "momentum": 0.15,
    "catalyst": 0.15,
    "balance_sheet": 0.10,
    "sentiment": 0.05,
    "sector_theme": 0.05,
}


class FactorScore(BaseModel):
    """Score for one factor."""

    model_config = ConfigDict(extra="forbid")

    name: str
    score: float
    weight: float
    weighted_score: float
    explanation: str


def score_factors(packet: CandidateEnrichmentPacket | None) -> list[FactorScore]:
    """Score all factors for a candidate enrichment packet."""

    raw_scores = {
        "growth": _growth_score(packet),
        "quality": _quality_score(packet),
        "valuation": _valuation_score(packet),
        "momentum": _momentum_score(packet),
        "catalyst": _catalyst_score(packet),
        "balance_sheet": _balance_sheet_score(packet),
        "sentiment": _sentiment_score(packet),
        "sector_theme": _sector_theme_score(packet),
    }
    return [
        FactorScore(
            name=name,
            score=score,
            weight=FACTOR_WEIGHTS[name],
            weighted_score=round(score * FACTOR_WEIGHTS[name], 2),
            explanation=explanation,
        )
        for name, (score, explanation) in raw_scores.items()
    ]


def weights_sum_to_one() -> bool:
    """Return whether configured weights sum to 100%."""

    return round(sum(FACTOR_WEIGHTS.values()), 10) == 1.0


def _growth_score(packet: CandidateEnrichmentPacket | None) -> tuple[float, str]:
    fundamentals = _fundamentals(packet)
    revenue_growth = _float(fundamentals.get("revenue_growth"))
    eps_growth = _float(fundamentals.get("eps_growth"))
    if revenue_growth is None and eps_growth is None:
        return 40.0, "Growth data missing; applied conservative base score."
    inputs = [value for value in (revenue_growth, eps_growth) if value is not None]
    score = 50.0 + min(35.0, sum(inputs) / len(inputs) * 100)
    return _bounded(score), "Growth scored from available revenue/EPS growth."


def _quality_score(packet: CandidateEnrichmentPacket | None) -> tuple[float, str]:
    fundamentals = _fundamentals(packet)
    gross_margin = _float(fundamentals.get("gross_margin"))
    if gross_margin is None:
        return 45.0, "Quality data missing; applied conservative base score."
    score = 45.0 + min(35.0, gross_margin * 50)
    return _bounded(score), "Quality scored from available margin data."


def _valuation_score(packet: CandidateEnrichmentPacket | None) -> tuple[float, str]:
    valuation = packet.valuation if packet and packet.valuation else {}
    pe_ratio = _float(valuation.get("pe_ratio") or valuation.get("trailing_pe"))
    if pe_ratio is None:
        return 45.0, "Valuation data missing; applied conservative base score."
    if pe_ratio <= 0:
        return 30.0, "Valuation appears unreliable or loss-making."
    if pe_ratio <= 25:
        return 80.0, "Valuation appears reasonable."
    if pe_ratio <= 45:
        return 65.0, "Valuation is elevated but not extreme."
    if pe_ratio <= 70:
        return 45.0, "Valuation is stretched."
    return 30.0, "Extreme valuation penalty applied."


def _momentum_score(packet: CandidateEnrichmentPacket | None) -> tuple[float, str]:
    summary = packet.price_history_summary if packet and packet.price_history_summary else {}
    return_pct = _float(summary.get("return_pct"))
    if return_pct is None:
        return 45.0, "Momentum data missing; applied conservative base score."
    if return_pct > 120:
        return 45.0, "Parabolic momentum penalty applied."
    score = 50.0 + max(-25.0, min(30.0, return_pct))
    return _bounded(score), "Momentum scored from available price-history return."


def _catalyst_score(packet: CandidateEnrichmentPacket | None) -> tuple[float, str]:
    if packet and packet.catalysts:
        return 65.0, "Catalyst data available."
    return 45.0, "No catalyst data available."


def _balance_sheet_score(packet: CandidateEnrichmentPacket | None) -> tuple[float, str]:
    fundamentals = _fundamentals(packet)
    debt_to_equity = _float(fundamentals.get("debt_to_equity"))
    if debt_to_equity is None:
        return 45.0, "Balance-sheet leverage data missing."
    if debt_to_equity <= 0.5:
        return 80.0, "Balance sheet appears conservative."
    if debt_to_equity <= 1.5:
        return 60.0, "Balance sheet leverage appears manageable."
    return 35.0, "Balance-sheet leverage penalty applied."


def _sentiment_score(packet: CandidateEnrichmentPacket | None) -> tuple[float, str]:
    sentiment = packet.sentiment if packet and packet.sentiment else {}
    score = _float(sentiment.get("score"))
    if score is None:
        return 45.0, "Sentiment data unavailable and low weighted."
    return _bounded(score), "Sentiment score consumed from enrichment packet."


def _sector_theme_score(packet: CandidateEnrichmentPacket | None) -> tuple[float, str]:
    if packet and packet.sector:
        if packet.sector.lower() in {"technology", "healthcare", "industrials"}:
            return 60.0, "Sector has a positive default tailwind score."
        return 50.0, "Sector tailwind is neutral."
    return 45.0, "Sector data missing."


def _fundamentals(packet: CandidateEnrichmentPacket | None) -> dict[str, Any]:
    if packet and packet.fundamentals:
        return packet.fundamentals
    return {}


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bounded(score: float) -> float:
    return round(max(0.0, min(100.0, score)), 2)
