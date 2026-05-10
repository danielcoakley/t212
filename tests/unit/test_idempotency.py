"""Tests for duplicate-order prevention."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from isa_system.db.base import Base
from isa_system.db.session import make_engine, make_session_factory
from isa_system.domain.enums import OrderSide, OrderType, RuntimeMode
from isa_system.execution.order_manager import DuplicateOrderError, OrderManager
from isa_system.execution.order_models import OrderBatch, OrderIntent


def test_duplicate_order_batch_blocked() -> None:
    """The same order batch cannot be reserved twice."""

    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = make_session_factory(engine)
    batch = OrderBatch(
        strategy_run_id="run-1",
        mode=RuntimeMode.LIVE,
        config_hash="abc",
        orders=[
            OrderIntent(
                symbol="AAPL",
                broker_ticker="AAPL_US_EQ",
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=Decimal("1"),
                limit_price=Decimal("100"),
            )
        ],
    )
    manager = OrderManager(environment="demo")
    with factory() as session:
        manager.reserve_for_submit(session, batch, date(2026, 5, 10))
        session.commit()
    with factory() as session, pytest.raises(DuplicateOrderError):
        manager.reserve_for_submit(session, batch, date(2026, 5, 10))
