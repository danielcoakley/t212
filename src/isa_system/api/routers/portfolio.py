"""Read-only live portfolio analytics routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from isa_system.services.portfolio_analytics import (
    PortfolioAnalyticsSummary,
    summarise_portfolio,
)
from isa_system.services.portfolio_state import load_trading212_portfolio
from isa_system.services.stock_valuation import (
    DeepValuationRun,
    DeepValuationRunRequest,
    run_selected_stock_valuations,
)
from isa_system.services.valuation import value_current_holdings
from isa_system.settings import get_settings

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("/summary", response_model=PortfolioAnalyticsSummary)
def portfolio_summary() -> PortfolioAnalyticsSummary:
    """Return read-only analytics for the configured broker portfolio."""

    snapshot = load_trading212_portfolio()
    return summarise_portfolio(snapshot)


@router.post("/deep-valuation", response_model=DeepValuationRun)
def portfolio_deep_valuation(request: DeepValuationRunRequest) -> DeepValuationRun:
    """Run GPT valuation for explicitly selected stocks only."""

    if not [symbol for symbol in request.symbols if str(symbol).strip()]:
        raise HTTPException(
            status_code=400,
            detail="Select at least one stock before running deep valuation.",
        )
    settings = get_settings()
    snapshot = load_trading212_portfolio(force_refresh=True)
    valuation = value_current_holdings(snapshot)
    try:
        return run_selected_stock_valuations(
            request.symbols,
            snapshot=snapshot,
            valuation=valuation,
            settings=settings,
            maximum_depth=request.maximum_depth,
            source_heavy=request.source_heavy,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
