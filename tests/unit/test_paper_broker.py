"""Tests for the paper broker."""

from __future__ import annotations

from decimal import Decimal

from isa_system.domain.enums import OrderSide, RuntimeMode
from isa_system.execution.order_models import OrderBatch, OrderIntent
from isa_system.execution.paper_broker import PaperBroker


def test_paper_broker_fills() -> None:
    """Paper broker returns deterministic fills."""

    batch = OrderBatch(
        strategy_run_id="paper",
        mode=RuntimeMode.PAPER,
        config_hash="hash",
        orders=[
            OrderIntent(
                symbol="AAPL",
                broker_ticker="AAPL_US_EQ",
                side=OrderSide.BUY,
                quantity=Decimal("1"),
                limit_price=Decimal("100"),
            )
        ],
    )
    fills = PaperBroker().fill_batch(batch, {"AAPL": Decimal("100")})
    assert fills[0].price == Decimal("100")
