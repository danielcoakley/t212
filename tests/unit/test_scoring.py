"""Scoring service tests."""

from __future__ import annotations

from datetime import timedelta

from isa_system.discovery.models import Candidate
from isa_system.enrichment.enrichment_packet import EnrichmentService, load_fixture_enrichment
from isa_system.scoring.factor_scores import weights_sum_to_one
from isa_system.scoring.ranking import RankingService
from isa_system.utils.time import now_utc


def test_score_weights_sum_to_100_percent() -> None:
    """Configured factor weights must sum to 100%."""

    assert weights_sum_to_one()


def test_missing_data_penalty() -> None:
    """Missing enrichment data materially penalizes opportunity score."""

    candidate = _candidate("MSFT")

    score = RankingService().score_candidate(candidate, packet=None)

    assert score.total_score < 45
    assert any("No enrichment" in penalty for penalty in score.penalties)


def test_stale_data_penalty() -> None:
    """Stale enrichment packets receive a penalty."""

    candidate = _candidate("MSFT")
    packet = _packet("MSFT").model_copy(update={"retrieved_at_utc": now_utc() - timedelta(days=10)})

    score = RankingService().score_candidate(candidate, packet)

    assert any("Stale" in penalty for penalty in score.penalties)


def test_multi_screener_boost() -> None:
    """Candidates appearing in multiple screeners receive a visible boost."""

    candidate = _candidate("MSFT", appearances=3, boost=10)
    packet = _packet("MSFT")

    score = RankingService().score_candidate(candidate, packet)

    assert any("Appeared in 3 screeners" in boost for boost in score.boosts)
    assert score.total_score > 60


def test_top_10_selection_and_ranking_explanations() -> None:
    """Ranking returns top candidates with explanations."""

    candidates = [_candidate(f"SYM{index}") for index in range(12)]
    packets = {candidate.symbol: _packet(candidate.symbol) for candidate in candidates}

    top10 = RankingService().top_n(candidates, packets, limit=10)

    assert len(top10) == 10
    assert all(score.explanation for score in top10)
    assert top10 == sorted(top10, key=lambda score: (-score.total_score, score.symbol))


def _candidate(symbol: str, appearances: int = 1, boost: float = 0) -> Candidate:
    return Candidate(
        symbol=symbol,
        source_screener="test",
        source_screeners=["test"] * appearances,
        screener_appearance_count=appearances,
        multi_screener_boost=boost,
        discovered_at_utc=now_utc(),
        screener_rank=1,
        raw_fields={},
        cache_key=f"cache-{symbol}",
    )


def _packet(symbol: str):
    return EnrichmentService().enrich_symbol(symbol, fixture_data=load_fixture_enrichment(symbol))
