"""Signal-facing routes for the web dashboard."""

from __future__ import annotations

from fastapi import APIRouter

from isa_system.services.market_scan import load_odp_market_scan_universe
from isa_system.services.portfolio_state import load_trading212_portfolio
from isa_system.services.recommendations import build_recommendations

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("/daily")
def daily_signals() -> dict[str, object]:
    """Return the current explainable signal candidates."""

    snapshot = load_trading212_portfolio()
    universe = load_odp_market_scan_universe()
    recommendations = build_recommendations(
        snapshot,
        candidates=None,
        include_default_candidates=True,
        default_candidates=universe.symbols,
        include_llm_rationale=False,
    )
    return {
        "provider": recommendations.provider,
        "warnings": [*recommendations.warnings, *universe.warnings],
        "signals": [item.model_dump(mode="json") for item in recommendations.recommendations],
    }
