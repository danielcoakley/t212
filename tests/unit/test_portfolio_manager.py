"""Portfolio manager tests."""

from __future__ import annotations

from datetime import timedelta

from isa_system.discovery.models import Candidate
from isa_system.enrichment.enrichment_packet import EnrichmentService, load_fixture_enrichment
from isa_system.portfolio.comparison import PortfolioComparisonService
from isa_system.portfolio.holdings import PortfolioHolding
from isa_system.portfolio.proposal_models import ProposalType
from isa_system.scoring.ranking import RankingService
from isa_system.thesis.models import InvestmentDecision, ThesisStatus
from isa_system.thesis.thesis_generator import ThesisGenerator
from isa_system.utils.time import now_utc


def test_no_trade_when_existing_holdings_remain_superior() -> None:
    """A good candidate does not trigger churn against a superior holding."""

    proposal = _review(
        [_holding("SUPERIOR", conviction=90, upside=25, downside=8)],
        [_thesis("MSFT", InvestmentDecision.BUY_NOW, conviction=75)],
    )[0]

    assert proposal.proposal_type == ProposalType.HOLD


def test_watchlist_if_candidate_good_but_entry_poor() -> None:
    """WATCHLIST_WAIT_ENTRY theses remain researched but unbought."""

    proposal = _review([], [_thesis("MSFT", InvestmentDecision.WATCHLIST_WAIT_ENTRY)])[0]

    assert proposal.proposal_type == ProposalType.WATCHLIST_WAIT_ENTRY


def test_replacement_only_when_candidate_clearly_improves_portfolio() -> None:
    """Candidate replacement requires material superiority."""

    proposal = _review(
        [_holding("WEAK", conviction=45, upside=5, downside=12, status="NEEDS_REVIEW")],
        [_thesis("MSFT", InvestmentDecision.BUY_NOW, conviction=80)],
    )[0]

    assert proposal.proposal_type == ProposalType.REPLACE_WITH_CANDIDATE
    assert proposal.manual_approval_required is True


def test_cooldown_prevents_churn() -> None:
    """Recent trades prevent churn."""

    proposal = _review(
        [_holding("MSFT", conviction=45, last_trade_at_utc=now_utc() - timedelta(days=2))],
        [_thesis("MSFT", InvestmentDecision.BUY_NOW, conviction=80)],
    )[0]

    assert proposal.proposal_type == ProposalType.HOLD
    assert "Cooldown" in proposal.rationale


def test_broken_thesis_triggers_sell_proposal() -> None:
    """Broken holding theses produce sell review proposals."""

    proposal = _review([_holding("BROKEN", status="BROKEN")], [])[0]

    assert proposal.proposal_type == ProposalType.SELL_THESIS_BROKEN


def test_target_reached_triggers_trim_or_sell_proposal() -> None:
    """Target reached holdings produce trim/sell review proposals."""

    proposal = _review([_holding("TARGET", status="TARGET_REACHED")], [])[0]

    assert proposal.proposal_type == ProposalType.SELL_TARGET_REACHED


def test_strategy_sleeve_allocation_respected() -> None:
    """No buy is proposed when strategy sleeve is already full."""

    proposal = _review(
        [_holding("FULL", weight=0.21, sleeve="strategy")],
        [_thesis("MSFT", InvestmentDecision.BUY_NOW, conviction=80)],
        cash=5000,
    )[0]

    assert proposal.proposal_type == ProposalType.WATCHLIST_WAIT_ENTRY
    assert "Strategy sleeve" in proposal.rationale


def _review(holdings, theses, cash=0):
    return PortfolioComparisonService().review(holdings=holdings, theses=theses, cash_gbp=cash)


def _holding(
    symbol: str,
    *,
    conviction: float = 50,
    upside: float | None = 5,
    downside: float | None = 10,
    status: str | None = None,
    weight: float = 0.05,
    sleeve: str = "core",
    last_trade_at_utc=None,
) -> PortfolioHolding:
    return PortfolioHolding(
        symbol=symbol,
        current_weight=weight,
        market_value=1000,
        sleeve=sleeve,
        thesis_status=status,
        conviction_score=conviction,
        expected_upside_pct=upside,
        downside_risk_pct=downside,
        last_trade_at_utc=last_trade_at_utc,
    )


def _thesis(symbol: str, decision: InvestmentDecision, conviction: float = 70):
    thesis = ThesisGenerator().generate(_score(conviction), _packet("MSFT"))
    return thesis.model_copy(
        update={
            "symbol": symbol,
            "decision": decision,
            "status": ThesisStatus.WATCHLIST_WAIT_ENTRY,
            "conviction_score": conviction,
            "upside_downside_ratio": 3.0,
        }
    )


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
