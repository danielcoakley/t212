"""Read-only operator report routes."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from isa_system.api.deps import ControlState, get_state
from isa_system.services.deep_research import latest_deep_research_reviews
from isa_system.services.instrument_validation import validate_recommendation_instruments
from isa_system.services.market_scan import load_broker_market_scan_universe
from isa_system.services.operator_report import (
    OperatorReportSummary,
    build_management_report_status,
    build_operator_report,
)
from isa_system.services.paper_persistence import load_paper_cycle
from isa_system.services.pilot_workflow import build_pilot_paper_workflow
from isa_system.services.portfolio_state import load_trading212_portfolio
from isa_system.services.recommendation_handoff import build_recommendation_handoff
from isa_system.services.recommendation_preview import build_preview_from_recommendation_handoff
from isa_system.services.recommendations import build_recommendations
from isa_system.settings import get_settings

router = APIRouter(prefix="/operator-report", tags=["operator-report"])


class OperatorReportRequest(BaseModel):
    """Optional selected symbols for preview and paper report sections."""

    symbols: list[str] = Field(default_factory=list)
    total_equity_gbp: float | None = Field(default=None, gt=0)
    paper_cycle_id: str | None = Field(default=None, min_length=1)


@router.post("", response_model=OperatorReportSummary)
def operator_report(
    request: OperatorReportRequest,
    state: ControlState = Depends(get_state),
) -> OperatorReportSummary:
    """Return a side-effect-free report shell from current local read-only context."""

    settings = get_settings()
    snapshot = load_trading212_portfolio()
    universe = load_broker_market_scan_universe()
    recommendations = build_recommendations(
        snapshot,
        candidates=[],
        include_default_candidates=True,
        default_candidates=universe.symbols,
        include_llm_rationale=False,
    )
    recommendations.warnings.extend(universe.warnings)
    validation = validate_recommendation_instruments(recommendations)
    research_reviews = latest_deep_research_reviews(
        [item.candidate.research_symbol for item in recommendations.recommendations]
    )
    handoff = build_recommendation_handoff(
        recommendations,
        instrument_validation=validation,
        research_reviews=research_reviews,
    )
    preview = None
    pilot_workflow = None
    persisted_paper_cycle = (
        load_paper_cycle(request.paper_cycle_id) if request.paper_cycle_id else None
    )
    if request.symbols:
        equity = (
            Decimal(str(request.total_equity_gbp)) if request.total_equity_gbp is not None else None
        )
        preview = build_preview_from_recommendation_handoff(
            selected_symbols=request.symbols,
            snapshot=snapshot,
            handoff=handoff,
            total_equity_gbp=equity,
        )
        pilot_workflow = build_pilot_paper_workflow(preview)

    return build_operator_report(
        account_snapshot=snapshot,
        recommendations=recommendations,
        handoff=handoff,
        research_reviews=research_reviews,
        preview=preview,
        pilot_workflow=pilot_workflow,
        persisted_paper_cycle=persisted_paper_cycle,
        requested_paper_cycle_id=request.paper_cycle_id,
        management=build_management_report_status(settings, state=state),
    )
