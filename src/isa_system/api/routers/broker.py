"""Broker read-only and order preview routes."""

from __future__ import annotations

import httpx
from fastapi import APIRouter

from isa_system.services.portfolio_state import (
    BrokerPortfolioSnapshot,
    load_trading212_portfolio,
)
from isa_system.trading212.client import Trading212ReadOnlyClient
from isa_system.trading212.models import (
    BrokerAccountSummary,
    BrokerMode,
    BrokerPosition,
    OrderPreview,
    OrderPreviewRequest,
)
from isa_system.trading212.order_preview import create_order_preview

router = APIRouter(tags=["broker"])


@router.get("/broker/account", response_model=BrokerAccountSummary)
def broker_account() -> BrokerAccountSummary:
    """Return read-only broker account summary or safe unconfigured status."""

    client = Trading212ReadOnlyClient()
    try:
        return client.account_summary()
    except httpx.HTTPError as exc:
        return _account_from_portfolio_snapshot(
            load_trading212_portfolio(force_refresh=True),
            warning=f"Trading 212 account endpoint failed: {exc.__class__.__name__}. "
            "Fell back to read-only portfolio snapshot.",
        )


@router.get("/broker/positions", response_model=list[BrokerPosition])
def broker_positions() -> list[BrokerPosition]:
    """Return read-only broker positions or an empty safe default."""

    try:
        positions = Trading212ReadOnlyClient().positions()
    except httpx.HTTPError:
        return _positions_from_portfolio_snapshot(load_trading212_portfolio(force_refresh=True))
    if positions:
        return positions
    snapshot = load_trading212_portfolio(force_refresh=True)
    return _positions_from_portfolio_snapshot(snapshot) if snapshot.positions else []


@router.post("/orders/preview", response_model=OrderPreview)
def order_preview(request: OrderPreviewRequest) -> OrderPreview:
    """Create a local order preview only."""

    return create_order_preview(request)


def _account_from_portfolio_snapshot(
    snapshot: BrokerPortfolioSnapshot, *, warning: str | None = None
) -> BrokerAccountSummary:
    warnings = list(snapshot.warnings)
    if warning is not None:
        warnings.append(warning)
    return BrokerAccountSummary(
        status=snapshot.status,
        mode=BrokerMode.LIVE if snapshot.environment == "live" else BrokerMode.DEMO,
        currency=snapshot.account_currency,
        total_value=snapshot.total_value,
        cash=snapshot.available_to_trade,
        retrieved_at_utc=snapshot.retrieved_at_utc,
        warnings=warnings,
    )


def _positions_from_portfolio_snapshot(snapshot: BrokerPortfolioSnapshot) -> list[BrokerPosition]:
    return [
        BrokerPosition(
            ticker=position.symbol,
            quantity=position.quantity,
            average_price=position.average_price_paid,
            current_price=position.current_price,
            currency=position.currency,
        )
        for position in snapshot.positions
    ]
