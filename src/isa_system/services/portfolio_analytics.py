"""Pure read-only portfolio analytics for broker snapshots."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from pydantic import BaseModel, Field

from isa_system.services.portfolio_state import BrokerPortfolioSnapshot, BrokerPosition
from isa_system.utils.time import require_utc


class PositionAnalytics(BaseModel):
    """Position-level analytics derived from a broker snapshot."""

    symbol: str
    name: str | None = None
    currency: str | None = None
    quantity: float
    current_value: float | None = None
    weight: float | None = None
    unrealised_profit_loss: float | None = None


class CurrencyExposure(BaseModel):
    """Currency exposure derived from known position market values."""

    currency: str
    current_value: float
    weight: float


class ConcentrationMetrics(BaseModel):
    """Simple concentration metrics for visible portfolio risk."""

    position_count: int
    max_position_weight: float | None = None
    top_five_weight: float | None = None
    herfindahl_index: float | None = Field(
        default=None,
        description="Sum of squared position weights; higher values mean more concentration.",
    )


class PortfolioAnalyticsSummary(BaseModel):
    """Read-only portfolio analytics summary for the control plane and dashboard."""

    status: str
    environment: str
    retrieved_at_utc: datetime
    account_currency: str | None = None
    total_value: float | None = None
    invested_value: float
    available_to_trade: float | None = None
    reserved_for_orders: float | None = None
    cash_fraction: float | None = None
    unrealised_profit_loss_total: float
    concentration: ConcentrationMetrics
    currency_exposure: list[CurrencyExposure]
    top_positions: list[PositionAnalytics]
    warnings: list[str]


def summarise_portfolio(
    snapshot: BrokerPortfolioSnapshot, *, top_n: int = 10
) -> PortfolioAnalyticsSummary:
    """Build deterministic analytics from a read-only broker portfolio snapshot."""

    warnings = list(snapshot.warnings)
    positions_with_values = [
        position for position in snapshot.positions if position.current_value is not None
    ]
    missing_value_symbols = [
        position.symbol for position in snapshot.positions if position.current_value is None
    ]
    if missing_value_symbols:
        warnings.append(
            "Missing current_value for broker positions: "
            + ", ".join(sorted(missing_value_symbols))
            + ". These positions are excluded from value-weighted analytics."
        )

    invested_value = _sum_known(position.current_value for position in positions_with_values)
    total_value = _total_value(snapshot, invested_value, warnings)
    position_analytics = [
        _position_analytics(position, total_value) for position in snapshot.positions
    ]
    known_position_analytics = [
        position for position in position_analytics if position.current_value is not None
    ]
    top_positions = sorted(
        known_position_analytics,
        key=lambda position: position.current_value or 0.0,
        reverse=True,
    )[:top_n]

    return PortfolioAnalyticsSummary(
        status=snapshot.status,
        environment=snapshot.environment,
        retrieved_at_utc=require_utc(snapshot.retrieved_at_utc),
        account_currency=snapshot.account_currency,
        total_value=total_value,
        invested_value=invested_value,
        available_to_trade=snapshot.available_to_trade,
        reserved_for_orders=snapshot.reserved_for_orders,
        cash_fraction=_fraction(snapshot.available_to_trade, total_value),
        unrealised_profit_loss_total=_sum_known(
            position.unrealised_profit_loss for position in snapshot.positions
        ),
        concentration=_concentration(known_position_analytics),
        currency_exposure=_currency_exposure(positions_with_values, total_value),
        top_positions=top_positions,
        warnings=warnings,
    )


def _total_value(
    snapshot: BrokerPortfolioSnapshot, invested_value: float, warnings: list[str]
) -> float | None:
    """Use broker total value when available, otherwise derive a cautious fallback."""

    if snapshot.total_value is not None:
        return snapshot.total_value
    cash_parts = [
        value
        for value in (snapshot.available_to_trade, snapshot.reserved_for_orders)
        if value is not None
    ]
    if not cash_parts and invested_value == 0.0:
        warnings.append("Broker total value is missing and no valued positions were available.")
        return None
    warnings.append("Broker total value is missing; analytics use a derived read-only estimate.")
    return invested_value + sum(cash_parts)


def _position_analytics(position: BrokerPosition, total_value: float | None) -> PositionAnalytics:
    """Return analytics for a single broker position."""

    return PositionAnalytics(
        symbol=position.symbol,
        name=position.name,
        currency=position.currency,
        quantity=position.quantity,
        current_value=position.current_value,
        weight=_fraction(position.current_value, total_value),
        unrealised_profit_loss=position.unrealised_profit_loss,
    )


def _concentration(positions: list[PositionAnalytics]) -> ConcentrationMetrics:
    """Calculate concentration from positions with known weights."""

    weights = sorted(
        [position.weight for position in positions if position.weight is not None],
        reverse=True,
    )
    return ConcentrationMetrics(
        position_count=len(positions),
        max_position_weight=weights[0] if weights else None,
        top_five_weight=sum(weights[:5]) if weights else None,
        herfindahl_index=sum(weight * weight for weight in weights) if weights else None,
    )


def _currency_exposure(
    positions: list[BrokerPosition], total_value: float | None
) -> list[CurrencyExposure]:
    """Aggregate known market values by trading currency."""

    totals: dict[str, float] = {}
    for position in positions:
        if position.current_value is None:
            continue
        currency = position.currency or "UNKNOWN"
        totals[currency] = totals.get(currency, 0.0) + position.current_value
    return [
        CurrencyExposure(
            currency=currency,
            current_value=value,
            weight=_fraction(value, total_value) or 0.0,
        )
        for currency, value in sorted(totals.items())
    ]


def _sum_known(values: Iterable[float | None]) -> float:
    """Sum known numeric values from a generator or iterable."""

    return sum(value for value in values if value is not None)


def _fraction(numerator: float | None, denominator: float | None) -> float | None:
    """Return a safe fraction for positive denominators."""

    if numerator is None or denominator is None or denominator <= 0:
        return None
    return numerator / denominator
