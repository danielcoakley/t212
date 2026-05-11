"""Read-only valuation routes for current holdings."""

from __future__ import annotations

from fastapi import APIRouter

from isa_system.services.portfolio_state import load_trading212_portfolio
from isa_system.services.valuation import HoldingsValuationResponse, value_current_holdings

router = APIRouter(prefix="/valuation", tags=["valuation"])


@router.get("/holdings", response_model=HoldingsValuationResponse)
def holdings_valuation() -> HoldingsValuationResponse:
    """Return offline-safe valuation analytics for the configured broker holdings."""

    snapshot = load_trading212_portfolio()
    return value_current_holdings(snapshot)
