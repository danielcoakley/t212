"""Deep research review gate routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from isa_system.services.deep_research import (
    DeepResearchReview,
    build_deep_research_input,
    latest_deep_research_review,
    run_deep_research,
)
from isa_system.services.instrument_validation import validate_recommendation_instruments
from isa_system.services.market_scan import load_odp_market_scan_universe
from isa_system.services.portfolio_state import load_trading212_portfolio
from isa_system.services.recommendation_handoff import build_recommendation_handoff
from isa_system.services.recommendations import build_recommendations

router = APIRouter(prefix="/research-reviews", tags=["research-reviews"])


class RunResearchReviewRequest(BaseModel):
    """Request to run deep research for one current candidate."""

    symbol: str = Field(description="Broker or research symbol from the recommendation table.")


@router.post("/run", response_model=DeepResearchReview)
def run_review(request: RunResearchReviewRequest) -> DeepResearchReview:
    """Run and persist a deep research review for one candidate."""

    recommendations = _recommendations()
    item = next(
        (
            row
            for row in recommendations.recommendations
            if request.symbol.upper()
            in {row.candidate.symbol.upper(), row.candidate.research_symbol.upper()}
        ),
        None,
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Candidate was not found in recommendations.")
    validation = validate_recommendation_instruments(recommendations)
    instrument_rows = {row.research_symbol.upper(): row for row in validation.rows}
    handoff = build_recommendation_handoff(recommendations, instrument_validation=validation)
    handoff_rows = {row.research_symbol.upper(): row for row in handoff.rows}
    key = item.candidate.research_symbol.upper()
    handoff_row = handoff_rows.get(key)
    deep_request = build_deep_research_input(
        item,
        instrument_row=instrument_rows.get(key),
        blockers=handoff_row.blockers if handoff_row is not None else [],
    )
    return run_deep_research(deep_request)


@router.get("/latest", response_model=DeepResearchReview)
def latest_review(
    symbol: Annotated[str, Query(description="Broker or research symbol.")],
) -> DeepResearchReview:
    """Return the latest persisted review for a symbol."""

    review = latest_deep_research_review(symbol)
    if review is None:
        raise HTTPException(status_code=404, detail="No deep research review exists for symbol.")
    return review


def _recommendations():
    snapshot = load_trading212_portfolio()
    universe = load_odp_market_scan_universe()
    return build_recommendations(
        snapshot,
        candidates=[],
        include_default_candidates=True,
        default_candidates=universe.symbols,
        include_llm_rationale=False,
    )
