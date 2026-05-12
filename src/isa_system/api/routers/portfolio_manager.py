"""Portfolio manager and rationale-based rebalance proposal routes."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from isa_system.portfolio.holdings import PortfolioHolding
from isa_system.portfolio.proposal_models import RebalanceProposal
from isa_system.portfolio.rebalance import propose_rebalance_actions
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot, load_trading212_portfolio
from isa_system.thesis.lifecycle import ThesisLifecycleService
from isa_system.thesis.thesis_tracker import ThesisTracker

router = APIRouter(tags=["portfolio-manager"])

_HOLDINGS: list[PortfolioHolding] = []
_LATEST_PROPOSALS: list[RebalanceProposal] = []


class PortfolioReviewRequest(BaseModel):
    """Request for portfolio review and rebalance proposal generation."""

    model_config = ConfigDict(extra="forbid")

    cash_gbp: float = 0.0


@router.post("/portfolio/review", response_model=list[RebalanceProposal])
def portfolio_review(request: PortfolioReviewRequest | None = None) -> list[RebalanceProposal]:
    """Review holdings against thesis watchlist without creating orders."""

    return _generate_proposals(request or PortfolioReviewRequest())


@router.get("/portfolio/holdings", response_model=list[PortfolioHolding])
def portfolio_holdings() -> list[PortfolioHolding]:
    """Return current in-process holdings context."""

    return _HOLDINGS


@router.post("/portfolio/holdings/load-example", response_model=list[PortfolioHolding])
def load_example_holdings() -> list[PortfolioHolding]:
    """Load a small example holding set for offline demos."""

    global _HOLDINGS
    _HOLDINGS = [
        PortfolioHolding(
            symbol="LEGACY",
            company_name="Legacy Holding",
            quantity=10,
            average_price=100,
            current_price=105,
            market_value=1050,
            target_weight=0.05,
            current_weight=0.05,
            sleeve="strategy",
            thesis_status="NEEDS_REVIEW",
            conviction_score=55,
            expected_upside_pct=8,
            downside_risk_pct=10,
            notes="Example review holding.",
        )
    ]
    return _HOLDINGS


@router.post("/portfolio/holdings/load-broker", response_model=list[PortfolioHolding])
def load_broker_holdings() -> list[PortfolioHolding]:
    """Load current read-only broker holdings into portfolio review context."""

    global _HOLDINGS
    snapshot = load_trading212_portfolio(force_refresh=True)
    _HOLDINGS = _holdings_from_broker_snapshot(snapshot)
    return _HOLDINGS


@router.post("/watchlist/review", response_model=list[str])
def watchlist_review() -> list[str]:
    """Return current watchlist thesis symbols."""

    lifecycle = ThesisLifecycleService()
    theses = ThesisTracker().list_by_status(lifecycle.watchlist_statuses)
    return [thesis.symbol for thesis in theses]


@router.post("/rebalance/propose", response_model=list[RebalanceProposal])
def rebalance_propose(request: PortfolioReviewRequest | None = None) -> list[RebalanceProposal]:
    """Generate latest rebalance proposals for manual review."""

    return _generate_proposals(request or PortfolioReviewRequest())


@router.get("/rebalance/latest", response_model=list[RebalanceProposal])
def rebalance_latest() -> list[RebalanceProposal]:
    """Return latest generated rebalance proposals."""

    return _LATEST_PROPOSALS


@router.get("/portfolio/actions/latest", response_model=list[RebalanceProposal])
def latest_portfolio_actions() -> list[RebalanceProposal]:
    """Return latest portfolio action proposals."""

    return _LATEST_PROPOSALS


def _generate_proposals(request: PortfolioReviewRequest) -> list[RebalanceProposal]:
    global _LATEST_PROPOSALS
    lifecycle = ThesisLifecycleService()
    tracker = ThesisTracker()
    theses = tracker.list_by_status(lifecycle.watchlist_statuses | lifecycle.active_statuses)
    _LATEST_PROPOSALS = propose_rebalance_actions(_HOLDINGS, theses, cash_gbp=request.cash_gbp)
    return _LATEST_PROPOSALS


def _holdings_from_broker_snapshot(snapshot: BrokerPortfolioSnapshot) -> list[PortfolioHolding]:
    total_value = snapshot.total_value or sum(
        position.current_value or _fallback_market_value(position.quantity, position.current_price)
        for position in snapshot.positions
    )
    holdings: list[PortfolioHolding] = []
    for position in snapshot.positions:
        current_price = position.current_price or position.average_price_paid or 0.0
        market_value = position.current_value or _fallback_market_value(
            position.quantity, current_price
        )
        holdings.append(
            PortfolioHolding(
                symbol=position.symbol,
                company_name=position.name,
                quantity=position.quantity,
                average_price=position.average_price_paid or 0.0,
                current_price=current_price,
                market_value=market_value,
                current_weight=(market_value / total_value) if total_value else 0.0,
                sleeve="core",
                thesis_status="NEEDS_REVIEW",
                notes="Loaded from Trading 212 read-only broker context.",
            )
        )
    return holdings


def _fallback_market_value(quantity: float, current_price: float | None) -> float:
    return quantity * current_price if current_price is not None else 0.0
