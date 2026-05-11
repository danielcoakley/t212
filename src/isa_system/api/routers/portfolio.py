"""Read-only live portfolio analytics routes."""

from __future__ import annotations

from fastapi import APIRouter

from isa_system.services.portfolio_analytics import (
    PortfolioAnalyticsSummary,
    summarise_portfolio,
)
from isa_system.services.portfolio_state import load_trading212_portfolio

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("/summary", response_model=PortfolioAnalyticsSummary)
def portfolio_summary() -> PortfolioAnalyticsSummary:
    """Return read-only analytics for the configured broker portfolio."""

    snapshot = load_trading212_portfolio()
    return summarise_portfolio(snapshot)
