"""Read-only broker portfolio state service."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Literal

import httpx
from pydantic import BaseModel

from isa_system.data.providers.base import ProviderNotConfigured
from isa_system.data.providers.trading212 import Trading212Client, Trading212Settings
from isa_system.settings import Settings, get_settings
from isa_system.utils.time import now_utc

CACHE_TTL_SECONDS = 15
_SNAPSHOT_CACHE: BrokerPortfolioSnapshot | None = None
_SNAPSHOT_CACHE_AT_UTC: datetime | None = None


class BrokerPosition(BaseModel):
    """Normalised read-only broker position row."""

    symbol: str
    broker_ticker: str
    name: str | None = None
    isin: str | None = None
    currency: str | None = None
    quantity: float
    average_price_paid: float | None = None
    current_price: float | None = None
    current_value: float | None = None
    unrealised_profit_loss: float | None = None


class BrokerPortfolioSnapshot(BaseModel):
    """Read-only broker account and positions snapshot."""

    status: Literal["live", "demo", "not_configured", "error"]
    environment: str
    retrieved_at_utc: datetime
    account_currency: str | None = None
    total_value: float | None = None
    available_to_trade: float | None = None
    reserved_for_orders: float | None = None
    positions: list[BrokerPosition]
    warnings: list[str]


def trading212_settings_from_app(settings: Settings | None = None) -> Trading212Settings:
    """Build Trading 212 client settings without exposing secrets."""

    app_settings = settings or get_settings()
    api_key = (
        app_settings.trading212_api_key.get_secret_value()
        if app_settings.trading212_api_key
        else None
    )
    api_secret = (
        app_settings.trading212_api_secret.get_secret_value()
        if app_settings.trading212_api_secret
        else None
    )
    environment: Literal["demo", "live"] = (
        "live" if app_settings.trading212_environment == "live" else "demo"
    )
    return Trading212Settings(
        api_key=api_key,
        api_secret=api_secret,
        environment=environment,
    )


def load_trading212_portfolio(
    settings: Settings | None = None, *, force_refresh: bool = False
) -> BrokerPortfolioSnapshot:
    """Load live or demo Trading 212 account state using read-only endpoints."""

    if settings is None and not force_refresh:
        cached = _cached_snapshot()
        if cached is not None:
            return cached

    client_settings = trading212_settings_from_app(settings)
    retrieved_at_utc = now_utc()
    if not client_settings.configured:
        snapshot = BrokerPortfolioSnapshot(
            status="not_configured",
            environment=client_settings.environment,
            retrieved_at_utc=retrieved_at_utc,
            positions=[],
            warnings=[
                "Trading 212 credentials were not found. Put them in env.local or .env.local."
            ],
        )
        _store_snapshot(snapshot, settings)
        return snapshot

    client = Trading212Client(client_settings)
    try:
        account = client.account_summary()
        positions = client.positions()
    except ProviderNotConfigured:
        snapshot = BrokerPortfolioSnapshot(
            status="not_configured",
            environment=client_settings.environment,
            retrieved_at_utc=retrieved_at_utc,
            positions=[],
            warnings=["Trading 212 credentials are not configured."],
        )
        _store_snapshot(snapshot, settings)
        return snapshot
    except httpx.HTTPStatusError as exc:
        return BrokerPortfolioSnapshot(
            status="error",
            environment=client_settings.environment,
            retrieved_at_utc=retrieved_at_utc,
            positions=[],
            warnings=[f"Trading 212 read failed with HTTP {exc.response.status_code}."],
        )
    except httpx.HTTPError as exc:
        return BrokerPortfolioSnapshot(
            status="error",
            environment=client_settings.environment,
            retrieved_at_utc=retrieved_at_utc,
            positions=[],
            warnings=[f"Trading 212 read failed: {exc.__class__.__name__}."],
        )

    cash = account.cash or {}
    snapshot = BrokerPortfolioSnapshot(
        status=client_settings.environment,
        environment=client_settings.environment,
        retrieved_at_utc=now_utc(),
        account_currency=account.currency,
        total_value=account.total_value,
        available_to_trade=_float_or_none(cash.get("availableToTrade")),
        reserved_for_orders=_float_or_none(cash.get("reservedForOrders")),
        positions=[
            _normalise_position(position.model_dump(by_alias=True)) for position in positions
        ],
        warnings=[],
    )
    _store_snapshot(snapshot, settings)
    return snapshot


def clear_portfolio_cache() -> None:
    """Clear the in-process broker snapshot cache."""

    global _SNAPSHOT_CACHE, _SNAPSHOT_CACHE_AT_UTC
    _SNAPSHOT_CACHE = None
    _SNAPSHOT_CACHE_AT_UTC = None


def _cached_snapshot() -> BrokerPortfolioSnapshot | None:
    """Return a recent cached broker snapshot when available."""

    if _SNAPSHOT_CACHE is None or _SNAPSHOT_CACHE_AT_UTC is None:
        return None
    if now_utc() - _SNAPSHOT_CACHE_AT_UTC > timedelta(seconds=CACHE_TTL_SECONDS):
        return None
    return _SNAPSHOT_CACHE


def _store_snapshot(snapshot: BrokerPortfolioSnapshot, settings: Settings | None) -> None:
    """Store a broker snapshot when using global app settings."""

    if settings is not None or snapshot.status == "error":
        return
    global _SNAPSHOT_CACHE, _SNAPSHOT_CACHE_AT_UTC
    _SNAPSHOT_CACHE = snapshot
    _SNAPSHOT_CACHE_AT_UTC = now_utc()


def _normalise_position(payload: dict[str, Any]) -> BrokerPosition:
    """Normalise a Trading 212 position payload."""

    instrument = payload.get("instrument") or {}
    wallet = payload.get("walletImpact") or {}
    broker_ticker = payload.get("ticker") or instrument.get("ticker") or "UNKNOWN"
    return BrokerPosition(
        symbol=str(broker_ticker),
        broker_ticker=str(broker_ticker),
        name=instrument.get("name"),
        isin=instrument.get("isin"),
        currency=instrument.get("currency"),
        quantity=float(payload.get("quantity") or 0.0),
        average_price_paid=_float_or_none(payload.get("averagePricePaid")),
        current_price=_float_or_none(payload.get("currentPrice")),
        current_value=_float_or_none(wallet.get("currentValue")),
        unrealised_profit_loss=_float_or_none(wallet.get("unrealizedProfitLoss")),
    )


def _float_or_none(value: Any) -> float | None:
    """Coerce provider numeric values defensively."""

    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
