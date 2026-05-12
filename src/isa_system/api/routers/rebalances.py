"""Rebalance preview and submit routes."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from isa_system.api.schemas import RebalancePreviewRequest
from isa_system.domain.models import TargetWeight
from isa_system.portfolio.costs import CostModel
from isa_system.portfolio.rebalancer import build_rebalance_plan
from isa_system.services.deep_research import latest_deep_research_reviews
from isa_system.services.instrument_validation import validate_recommendation_instruments
from isa_system.services.market_scan import load_broker_market_scan_universe
from isa_system.services.paper_persistence import (
    PersistedPaperCycle,
    load_paper_cycle,
    persist_pilot_paper_workflow,
)
from isa_system.services.paper_simulation import PaperSimulationSnapshot, simulate_paper_fills
from isa_system.services.pilot_workflow import (
    PilotPaperWorkflowSummary,
    build_pilot_paper_workflow,
)
from isa_system.services.portfolio_state import load_trading212_portfolio
from isa_system.services.rebalance_preview import (
    RebalancePreviewSnapshot,
    build_preview_from_holdings,
)
from isa_system.services.recommendation_handoff import build_recommendation_handoff
from isa_system.services.recommendation_preview import (
    RecommendationPreviewResponse,
    build_preview_from_recommendation_handoff,
)
from isa_system.services.recommendations import build_recommendations
from isa_system.services.valuation import value_current_holdings

router = APIRouter()


class RecommendationsPreviewRequest(BaseModel):
    """Selected recommendation rows to preview size."""

    symbols: list[str] = Field(min_length=1)
    total_equity_gbp: float | None = Field(default=None, gt=0)


@router.post("/rebalances/preview")
def preview(request: RebalancePreviewRequest) -> dict[str, object]:
    """Create a starter rebalance preview."""

    plan = build_rebalance_plan(
        run_id=request.run_id,
        current_weights={"TSCO.L": 0.02},
        targets=[
            TargetWeight("TSCO.L", 0.04),
            TargetWeight("AAPL", 0.05),
            TargetWeight("MSFT", 0.05),
        ],
        prices={"TSCO.L": Decimal("2.90"), "AAPL": Decimal("190"), "MSFT": Decimal("420")},
        total_equity_gbp=Decimal(str(request.total_equity_gbp)),
        cost_model=CostModel(),
    )
    return {
        "run_id": plan.run_id,
        "batch_hash": plan.batch_hash,
        "estimated_total_cost": str(plan.estimated_total_cost),
        "turnover": plan.turnover,
        "warnings": list(plan.warnings),
        "trades": [trade.__dict__ | {"side": trade.side.value} for trade in plan.trades],
    }


@router.get("/rebalances/live-preview", response_model=RebalancePreviewSnapshot)
def live_preview() -> RebalancePreviewSnapshot:
    """Return a preview-only plan from the current read-only broker snapshot."""

    snapshot = load_trading212_portfolio()
    valuation = value_current_holdings(snapshot)
    return build_preview_from_holdings(snapshot, valuation)


@router.post(
    "/rebalances/from-recommendations/preview",
    response_model=RecommendationPreviewResponse,
)
def preview_from_recommendations(
    request: RecommendationsPreviewRequest,
) -> RecommendationPreviewResponse:
    """Build preview-only sizing from selected research-gated recommendations."""

    return _recommendation_preview_from_request(request)


@router.post(
    "/rebalances/from-recommendations/pilot-workflow",
    response_model=PilotPaperWorkflowSummary,
)
def pilot_workflow_from_recommendations(
    request: RecommendationsPreviewRequest,
) -> PilotPaperWorkflowSummary:
    """Return a schema-light paper workflow summary without side effects."""

    preview_snapshot = _recommendation_preview_from_request(request)
    return build_pilot_paper_workflow(preview_snapshot)


@router.post(
    "/rebalances/from-recommendations/paper-cycle",
    response_model=PersistedPaperCycle,
)
def persist_paper_cycle_from_recommendations(
    request: RecommendationsPreviewRequest,
) -> PersistedPaperCycle:
    """Persist selected recommendation preview rows as local paper evidence."""

    preview_snapshot = _recommendation_preview_from_request(request)
    workflow = build_pilot_paper_workflow(preview_snapshot)
    return persist_pilot_paper_workflow(workflow)


@router.get("/rebalances/paper-cycles/{cycle_id}", response_model=PersistedPaperCycle)
def get_paper_cycle(cycle_id: str) -> PersistedPaperCycle:
    """Reload a persisted paper cycle by deterministic cycle ID."""

    cycle = load_paper_cycle(cycle_id)
    if cycle is None:
        raise HTTPException(status_code=404, detail="Paper cycle not found.")
    return cycle


def _recommendation_preview_from_request(
    request: RecommendationsPreviewRequest,
) -> RecommendationPreviewResponse:
    """Build recommendation preview context for read-only workflow routes."""

    snapshot = load_trading212_portfolio()
    universe = load_broker_market_scan_universe()
    recommendations = build_recommendations(
        snapshot,
        candidates=[],
        include_default_candidates=True,
        default_candidates=universe.symbols,
        include_llm_rationale=False,
    )
    validation = validate_recommendation_instruments(recommendations)
    reviews = latest_deep_research_reviews(
        [item.candidate.research_symbol for item in recommendations.recommendations]
    )
    handoff = build_recommendation_handoff(
        recommendations,
        instrument_validation=validation,
        research_reviews=reviews,
    )
    equity = (
        Decimal(str(request.total_equity_gbp)) if request.total_equity_gbp is not None else None
    )
    return build_preview_from_recommendation_handoff(
        selected_symbols=request.symbols,
        snapshot=snapshot,
        handoff=handoff,
        total_equity_gbp=equity,
    )


@router.get("/rebalances/paper-simulation", response_model=PaperSimulationSnapshot)
def paper_simulation() -> PaperSimulationSnapshot:
    """Return local paper fill simulation from the current preview plan."""

    snapshot = load_trading212_portfolio()
    valuation = value_current_holdings(snapshot)
    preview_snapshot = build_preview_from_holdings(snapshot, valuation)
    return simulate_paper_fills(preview_snapshot)
