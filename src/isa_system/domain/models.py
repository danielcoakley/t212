"""Typed domain models for instruments, data, signals, orders, and risk."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from isa_system.domain.enums import (
    AssetType,
    OrderSide,
    OrderType,
    RuntimeMode,
    TimestampPrecision,
)
from isa_system.utils.time import ensure_utc


@dataclass(frozen=True)
class Instrument:
    """Tradable instrument in the ISA universe."""

    symbol: str
    name: str
    isin: str | None
    currency: str
    country: str
    asset_type: AssetType
    exchange: str | None = None
    sector: str | None = None
    trading212_ticker: str | None = None
    isa_eligible: bool = True
    sdrt_applicable: bool = False


@dataclass(frozen=True)
class PriceBar:
    """Daily or intraday price bar with UTC timestamp."""

    symbol: str
    ts_utc: datetime
    open: float
    high: float
    low: float
    close: float
    adj_close: float
    volume: float
    source: str

    def __post_init__(self) -> None:
        ensure_utc(self.ts_utc)


@dataclass(frozen=True)
class CorporateAction:
    """Corporate action record used for adjusted-return logic."""

    symbol: str
    effective_date: date
    action_type: str
    value: float
    retrieved_at_utc: datetime
    source_name: str

    def __post_init__(self) -> None:
        ensure_utc(self.retrieved_at_utc)


@dataclass(frozen=True)
class FundamentalFact:
    """Point-in-time fundamental fact."""

    symbol: str
    fact_name: str
    value: float | str | None
    effective_date: date
    available_at_utc: datetime
    source_name: str
    source_document_id: str
    retrieved_at_utc: datetime
    filed_at_utc: datetime | None = None
    published_at_utc: datetime | None = None
    timestamp_precision: TimestampPrecision = TimestampPrecision.UNKNOWN

    def __post_init__(self) -> None:
        ensure_utc(self.available_at_utc)
        ensure_utc(self.retrieved_at_utc)
        if self.filed_at_utc is not None:
            ensure_utc(self.filed_at_utc)
        if self.published_at_utc is not None:
            ensure_utc(self.published_at_utc)


@dataclass(frozen=True)
class EventRecord:
    """Official or convenience event record."""

    symbol: str
    event_type: str
    event_date: date
    available_at_utc: datetime
    source_name: str
    source_document_id: str
    url: str | None = None
    retrieved_at_utc: datetime | None = None
    timestamp_precision: TimestampPrecision = TimestampPrecision.UNKNOWN

    def __post_init__(self) -> None:
        ensure_utc(self.available_at_utc)
        if self.retrieved_at_utc is not None:
            ensure_utc(self.retrieved_at_utc)


@dataclass(frozen=True)
class FactorSnapshot:
    """Factor scores for one instrument as of a rebalance time."""

    symbol: str
    as_of_utc: datetime
    scores: dict[str, float]
    diagnostics: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        ensure_utc(self.as_of_utc)


@dataclass(frozen=True)
class Signal:
    """Ranked trading signal."""

    symbol: str
    as_of_utc: datetime
    score: float
    rank: int
    rationale: str
    vetoed: bool = False
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        ensure_utc(self.as_of_utc)


@dataclass(frozen=True)
class TargetWeight:
    """Target portfolio weight for a symbol."""

    symbol: str
    weight: float
    sector: str | None = None
    country: str | None = None


@dataclass(frozen=True)
class Trade:
    """Trade intent produced by the rebalancer."""

    symbol: str
    side: OrderSide
    quantity: Decimal
    estimated_price: Decimal
    estimated_notional: Decimal
    estimated_cost: Decimal
    reason: str


@dataclass(frozen=True)
class RebalancePlan:
    """Preview output for a rebalance run."""

    run_id: str
    as_of_utc: datetime
    current_weights: dict[str, float]
    target_weights: dict[str, float]
    trades: tuple[Trade, ...]
    estimated_total_cost: Decimal
    turnover: float
    warnings: tuple[str, ...]
    vetoes: tuple[str, ...]
    batch_hash: str

    def __post_init__(self) -> None:
        ensure_utc(self.as_of_utc)


@dataclass(frozen=True)
class BrokerOrder:
    """Broker order model used by adapters."""

    symbol: str
    broker_ticker: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    limit_price: Decimal | None = None
    client_order_id: str | None = None


@dataclass(frozen=True)
class FillEvent:
    """Fill event from a broker or paper simulator."""

    symbol: str
    filled_at_utc: datetime
    quantity: Decimal
    price: Decimal
    fees: Decimal
    broker_order_id: str | None

    def __post_init__(self) -> None:
        ensure_utc(self.filled_at_utc)


@dataclass(frozen=True)
class RiskCheckResult:
    """Result of a pre-trade risk check."""

    name: str
    passed: bool
    message: str
    severity: str = "error"
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModeState:
    """Current execution mode and live arming state."""

    mode: RuntimeMode
    live_armed: bool
    kill_switch_enabled: bool
    updated_at_utc: datetime

    def __post_init__(self) -> None:
        ensure_utc(self.updated_at_utc)
