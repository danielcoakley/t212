"""Ranking service for candidate opportunity scores."""

from __future__ import annotations

from datetime import timedelta

from isa_system.discovery.models import Candidate
from isa_system.enrichment.enrichment_packet import CandidateEnrichmentPacket
from isa_system.scoring.composite_score import CompositeScore
from isa_system.scoring.explanations import build_score_explanation
from isa_system.scoring.factor_scores import score_factors
from isa_system.utils.time import now_utc


class RankingService:
    """Score, rank, and select top candidates."""

    def score_candidate(
        self,
        candidate: Candidate,
        packet: CandidateEnrichmentPacket | None,
    ) -> CompositeScore:
        """Create a composite score for one candidate."""

        factor_scores = score_factors(packet)
        base_score = sum(factor.weighted_score for factor in factor_scores)
        data_quality_score = _data_quality_score(packet)
        boosts: list[str] = []
        penalties: list[str] = []

        total = base_score
        if candidate.screener_appearance_count > 1:
            total += candidate.multi_screener_boost
            boosts.append(
                f"Appeared in {candidate.screener_appearance_count} screeners "
                f"(+{candidate.multi_screener_boost:.1f})."
            )

        if data_quality_score < 60:
            penalty = round((60 - data_quality_score) * 0.25, 2)
            total -= penalty
            penalties.append(f"Missing/weak data quality penalty (-{penalty:.1f}).")

        if packet is None:
            total -= 10
            penalties.append("No enrichment packet available (-10.0).")
        elif now_utc() - packet.retrieved_at_utc > timedelta(days=7):
            total -= 10
            penalties.append("Stale enrichment data penalty (-10.0).")

        score = CompositeScore(
            symbol=candidate.symbol,
            total_score=round(max(0.0, min(100.0, total)), 2),
            factor_scores=factor_scores,
            data_quality_score=data_quality_score,
            boosts=boosts,
            penalties=penalties,
            explanation="",
            scored_at_utc=now_utc(),
        )
        return score.model_copy(update={"explanation": build_score_explanation(score)})

    def rank(
        self,
        candidates: list[Candidate],
        packets_by_symbol: dict[str, CandidateEnrichmentPacket],
    ) -> list[CompositeScore]:
        """Score and rank candidates by opportunity score."""

        scores = [
            self.score_candidate(candidate, packets_by_symbol.get(candidate.symbol))
            for candidate in candidates
        ]
        return sorted(scores, key=lambda score: (-score.total_score, score.symbol))

    def top_n(
        self,
        candidates: list[Candidate],
        packets_by_symbol: dict[str, CandidateEnrichmentPacket],
        *,
        limit: int = 10,
    ) -> list[CompositeScore]:
        """Return top N ranked candidates."""

        return self.rank(candidates, packets_by_symbol)[:limit]


def _data_quality_score(packet: CandidateEnrichmentPacket | None) -> float:
    if packet is None:
        return 0.0
    value = packet.data_quality.get("score")
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
