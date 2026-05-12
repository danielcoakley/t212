"""Deterministic investment thesis generation."""

from __future__ import annotations

from datetime import timedelta

from isa_system.enrichment.enrichment_packet import CandidateEnrichmentPacket
from isa_system.scoring.composite_score import CompositeScore
from isa_system.thesis.decision_engine import DecisionEngine, DecisionInput
from isa_system.thesis.models import Thesis
from isa_system.utils.hashing import sha256_digest
from isa_system.utils.time import now_utc


class ThesisGenerator:
    """Generate thesis drafts from provided score and enrichment data."""

    def __init__(self, decision_engine: DecisionEngine | None = None) -> None:
        self.decision_engine = decision_engine or DecisionEngine()

    def generate(
        self,
        score: CompositeScore,
        packet: CandidateEnrichmentPacket | None,
        *,
        max_buy_price: float | None = None,
        catalyst_confirmation_needed: bool = False,
        portfolio_improves: bool = True,
    ) -> Thesis:
        """Generate a deterministic thesis without fabricating unavailable data."""

        created_at = now_utc()
        current_price = packet.price if packet else None
        data_quality_score = score.data_quality_score
        conviction_score = min(100.0, max(0.0, score.total_score))
        confidence_score = min(100.0, max(0.0, data_quality_score))
        target_price = round(current_price * 1.3, 2) if current_price is not None else None
        downside_case_price = round(current_price * 0.85, 2) if current_price is not None else None
        stop_or_review_level = round(current_price * 0.9, 2) if current_price is not None else None
        preferred_entry_price = (
            round(current_price * 0.98, 2) if current_price is not None else None
        )
        max_buy_price = (
            max_buy_price
            if max_buy_price is not None
            else round(current_price * 1.05, 2)
            if current_price is not None
            else None
        )
        upside_to_target_pct = _pct(current_price, target_price)
        downside_to_review_pct = _pct(current_price, stop_or_review_level)
        upside_downside_ratio = _upside_downside_ratio(
            current_price,
            target_price,
            stop_or_review_level,
        )
        valuation_extreme = any(
            "Extreme valuation" in factor.explanation for factor in score.factor_scores
        )
        technical_positive = _factor_score(score, "momentum") >= 50
        decision = self.decision_engine.decide(
            score,
            packet,
            DecisionInput(
                conviction_score=conviction_score,
                confidence_score=confidence_score,
                data_quality_score=data_quality_score,
                current_price=current_price,
                target_price=target_price,
                max_buy_price=max_buy_price,
                stop_or_review_level=stop_or_review_level,
                upside_downside_ratio=upside_downside_ratio,
                valuation_extreme=valuation_extreme,
                technical_setup_positive=technical_positive,
                catalyst_confirmation_needed=catalyst_confirmation_needed,
                portfolio_improves=portfolio_improves,
            ),
        )
        missing_notes = list(packet.missing_sections) if packet else ["enrichment_packet"]

        return Thesis(
            id=sha256_digest({"symbol": score.symbol, "created_at_utc": created_at})[:20],
            symbol=score.symbol,
            company_name=packet.company_name if packet else None,
            status=decision.status,
            decision=decision.decision,
            one_line_thesis=_one_line(score, packet),
            business_summary=_business_summary(packet),
            growth_case=_factor_explanation(score, "growth"),
            quality_case=_factor_explanation(score, "quality"),
            valuation_case=_factor_explanation(score, "valuation"),
            technical_setup=_factor_explanation(score, "momentum"),
            sentiment_context=_factor_explanation(score, "sentiment"),
            catalyst_path="; ".join(catalyst["description"] for catalyst in packet.catalysts)
            if packet and packet.catalysts
            else "No confirmed catalyst data available.",
            key_risks=[
                "This is a research record, not investment advice.",
                "External provider data may be stale, incomplete, or unavailable.",
            ],
            entry_conditions=["Human review required before any portfolio action."],
            exit_conditions=[
                "Review if target reached, thesis breaks, or risk/reward deteriorates."
            ],
            invalidation_triggers=[
                "Material deterioration in fundamentals, valuation, or catalysts."
            ],
            target_price=target_price,
            downside_case_price=downside_case_price,
            preferred_entry_price=preferred_entry_price,
            max_buy_price=max_buy_price,
            stop_or_review_level=stop_or_review_level,
            conviction_score=round(conviction_score, 2),
            confidence_score=round(confidence_score, 2),
            data_quality_score=round(data_quality_score, 2),
            current_price=current_price,
            upside_to_target_pct=upside_to_target_pct,
            downside_to_review_pct=downside_to_review_pct,
            upside_downside_ratio=upside_downside_ratio,
            catalyst_status="AVAILABLE" if packet and packet.catalysts else "MISSING",
            next_review_date=created_at + timedelta(days=30),
            created_at_utc=created_at,
            updated_at_utc=created_at,
            rationale=decision.rationale,
            missing_data_notes=missing_notes,
        )


def _one_line(score: CompositeScore, packet: CandidateEnrichmentPacket | None) -> str:
    name = packet.company_name if packet and packet.company_name else score.symbol
    return f"{name} is a rule-based research candidate scoring {score.total_score:.1f}/100."


def _business_summary(packet: CandidateEnrichmentPacket | None) -> str:
    if not packet:
        return "Business summary unavailable because enrichment data is missing."
    bits = [value for value in (packet.company_name, packet.sector, packet.industry) if value]
    return " / ".join(bits) if bits else "Business summary unavailable from provided data."


def _factor_explanation(score: CompositeScore, factor_name: str) -> str:
    for factor in score.factor_scores:
        if factor.name == factor_name:
            return factor.explanation
    return "Factor was not scored."


def _factor_score(score: CompositeScore, factor_name: str) -> float:
    for factor in score.factor_scores:
        if factor.name == factor_name:
            return factor.score
    return 0.0


def _pct(current: float | None, future: float | None) -> float | None:
    if current is None or current == 0 or future is None:
        return None
    return round(((future - current) / current) * 100, 2)


def _upside_downside_ratio(
    current: float | None,
    target: float | None,
    review_level: float | None,
) -> float | None:
    if current is None or target is None or review_level is None:
        return None
    upside = target - current
    downside = current - review_level
    if downside <= 0:
        return None
    return round(upside / downside, 2)
