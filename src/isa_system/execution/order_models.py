"""Execution order models."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from isa_system.domain.enums import OrderSide, OrderType, RuntimeMode


class OrderIntent(BaseModel):
    """Order intent before broker submission."""

    model_config = ConfigDict(use_enum_values=False)

    symbol: str
    broker_ticker: str
    side: OrderSide
    order_type: OrderType = OrderType.LIMIT
    quantity: Decimal = Field(gt=Decimal("0"))
    limit_price: Decimal | None = None
    time_validity: str = "DAY"


class OrderBatch(BaseModel):
    """Batch of order intents from one rebalance run."""

    strategy_run_id: str
    mode: RuntimeMode
    orders: list[OrderIntent]
    config_hash: str


class OrderBatchPreview(BaseModel):
    """Preview payload with hash and warnings."""

    batch_hash: str
    idempotency_key: str
    warnings: list[str]
    orders: list[OrderIntent]
