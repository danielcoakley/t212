"""Read-only recommendation routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from isa_system.services.portfolio_state import load_trading212_portfolio
from isa_system.services.recommendation_handoff import (
    RecommendationHandoffResponse,
    build_recommendation_handoff,
)
from isa_system.services.recommendations import RecommendationsResponse, build_recommendations

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("", response_model=RecommendationsResponse)
def recommendations(
    candidates: Annotated[
        list[str] | None,
        Query(
            description=(
                "Optional watchlist symbols. Repeat the query parameter or pass comma-separated "
                "symbols, for example candidates=AAPL&candidates=TSCO.L."
            )
        ),
    ] = None,
    include_defaults: Annotated[
        bool,
        Query(description="Include the default wider-market scan list."),
    ] = True,
    include_llm: Annotated[
        bool,
        Query(description="Attach optional OpenAI rationale when configured."),
    ] = False,
) -> RecommendationsResponse:
    """Return review-only trade recommendations for holdings and market candidates."""

    snapshot = load_trading212_portfolio()
    return build_recommendations(
        snapshot,
        candidates=candidates,
        include_default_candidates=include_defaults,
        include_llm_rationale=include_llm,
    )


@router.get("/handoff", response_model=RecommendationHandoffResponse)
def recommendation_handoff(
    candidates: Annotated[
        list[str] | None,
        Query(
            description=(
                "Optional watchlist symbols. Repeat the query parameter or pass comma-separated "
                "symbols, for example candidates=AAPL&candidates=TSCO.L."
            )
        ),
    ] = None,
    include_defaults: Annotated[
        bool,
        Query(description="Include the default wider-market scan list."),
    ] = True,
) -> RecommendationHandoffResponse:
    """Return review-only preview hand-off readiness for recommendations."""

    snapshot = load_trading212_portfolio()
    response = build_recommendations(
        snapshot,
        candidates=candidates,
        include_default_candidates=include_defaults,
        include_llm_rationale=False,
    )
    return build_recommendation_handoff(response)
