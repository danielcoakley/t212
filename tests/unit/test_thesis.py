"""Thesis engine tests."""

from __future__ import annotations

from pathlib import Path

from isa_system.db.session import init_db, make_engine, make_session_factory
from isa_system.discovery.models import Candidate
from isa_system.enrichment.enrichment_packet import EnrichmentService, load_fixture_enrichment
from isa_system.scoring.ranking import RankingService
from isa_system.thesis.decision_engine import DecisionEngine, DecisionInput
from isa_system.thesis.models import InvestmentDecision, ThesisStatus
from isa_system.thesis.thesis_generator import ThesisGenerator
from isa_system.thesis.thesis_tracker import ThesisTracker
from isa_system.utils.time import now_utc


def test_buy_now_rule() -> None:
    """BUY_NOW is available only after all strict rules pass."""

    result = DecisionEngine().decide(
        _score(80),
        _packet("MSFT"),
        DecisionInput(
            conviction_score=75,
            confidence_score=70,
            data_quality_score=70,
            current_price=100,
            target_price=130,
            max_buy_price=105,
            stop_or_review_level=90,
            upside_downside_ratio=3,
        ),
    )

    assert result.decision == InvestmentDecision.BUY_NOW


def test_watchlist_wait_entry_rule() -> None:
    """Strong but expensive candidates wait for entry."""

    result = DecisionEngine().decide(
        _score(72),
        _packet("MSFT"),
        DecisionInput(
            conviction_score=70,
            confidence_score=70,
            data_quality_score=70,
            current_price=110,
            target_price=130,
            max_buy_price=100,
            stop_or_review_level=100,
            upside_downside_ratio=1.8,
        ),
    )

    assert result.decision == InvestmentDecision.WATCHLIST_WAIT_ENTRY
    assert result.status == ThesisStatus.WATCHLIST_WAIT_ENTRY


def test_watchlist_wait_catalyst_rule() -> None:
    """Promising candidates without catalyst confirmation stay on watchlist."""

    result = DecisionEngine().decide(
        _score(65),
        _packet("MSFT"),
        DecisionInput(
            conviction_score=65,
            confidence_score=60,
            data_quality_score=60,
            catalyst_confirmation_needed=True,
        ),
    )

    assert result.decision == InvestmentDecision.WATCHLIST_WAIT_CATALYST


def test_reject_rule() -> None:
    """Weak or low-quality candidates are rejected."""

    result = DecisionEngine().decide(
        _score(40),
        None,
        DecisionInput(conviction_score=40, confidence_score=20, data_quality_score=20),
    )

    assert result.decision == InvestmentDecision.REJECT
    assert result.status == ThesisStatus.REJECTED


def test_no_fabricated_price_targets_when_price_missing() -> None:
    """Missing current price means no deterministic target levels are invented."""

    thesis = ThesisGenerator().generate(_score(60), packet=None)

    assert thesis.target_price is None
    assert thesis.max_buy_price is None
    assert "enrichment_packet" in thesis.missing_data_notes


def test_thesis_is_persisted(tmp_path: Path) -> None:
    """Thesis tracker persists and reloads thesis records."""

    engine = make_engine(f"sqlite:///{tmp_path / 'thesis.sqlite3'}")
    init_db(engine)
    tracker = ThesisTracker(session_factory=make_session_factory(engine))
    thesis = ThesisGenerator().generate(_score(72), _packet("MSFT"), max_buy_price=100)

    tracker.save(thesis)
    loaded = tracker.latest_for_symbol("MSFT")

    assert loaded is not None
    assert loaded.id == thesis.id


def test_watchlist_candidates_remain_tracked(tmp_path: Path) -> None:
    """Watchlist decisions can be queried after persistence."""

    engine = make_engine(f"sqlite:///{tmp_path / 'watchlist.sqlite3'}")
    init_db(engine)
    tracker = ThesisTracker(session_factory=make_session_factory(engine))
    thesis = ThesisGenerator().generate(_score(72), _packet("MSFT"), max_buy_price=100)
    tracker.save(thesis)

    watchlist = tracker.list_by_status({ThesisStatus.WATCHLIST_WAIT_ENTRY})

    assert [item.symbol for item in watchlist] == ["MSFT"]


def _score(total: float):
    candidate = Candidate(
        symbol="MSFT",
        source_screener="test",
        source_screeners=["test"],
        discovered_at_utc=now_utc(),
        screener_rank=1,
        raw_fields={},
        cache_key="cache",
    )
    score = RankingService().score_candidate(candidate, _packet("MSFT"))
    return score.model_copy(update={"total_score": total, "data_quality_score": 70.0})


def _packet(symbol: str):
    return EnrichmentService().enrich_symbol(symbol, fixture_data=load_fixture_enrichment(symbol))
