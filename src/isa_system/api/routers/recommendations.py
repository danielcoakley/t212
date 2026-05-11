"""Read-only recommendation routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from isa_system.services.instrument_validation import (
    InstrumentValidationResponse,
    validate_recommendation_instruments,
)
from isa_system.services.market_scan import MarketScanUniverse, load_market_scan_universe
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
    scan_universe = load_market_scan_universe()
    response = build_recommendations(
        snapshot,
        candidates=candidates,
        include_default_candidates=include_defaults,
        default_candidates=scan_universe.symbols,
        include_llm_rationale=include_llm,
    )
    response.warnings.extend(scan_universe.warnings)
    return response


@router.get("/scan-universe", response_model=MarketScanUniverse)
def scan_universe() -> MarketScanUniverse:
    """Return the configured wider-market scan universe."""

    return load_market_scan_universe()


def _recommendations_for_validation(
    candidates: list[str] | None, include_defaults: bool
) -> RecommendationsResponse:
    """Build recommendations using the configured scan universe."""

    snapshot = load_trading212_portfolio()
    universe = load_market_scan_universe()
    return build_recommendations(
        snapshot,
        candidates=candidates,
        include_default_candidates=include_defaults,
        default_candidates=universe.symbols,
        include_llm_rationale=False,
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

    response = _recommendations_for_validation(candidates, include_defaults)
    instrument_validation = validate_recommendation_instruments(response)
    return build_recommendation_handoff(response, instrument_validation=instrument_validation)


@router.get("/instrument-validation", response_model=InstrumentValidationResponse)
def recommendation_instrument_validation(
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
) -> InstrumentValidationResponse:
    """Return read-only Trading 212 instrument metadata validation for recommendations."""

    response = _recommendations_for_validation(candidates, include_defaults)
    return validate_recommendation_instruments(response)
