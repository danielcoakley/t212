"""Local paper broker simulator."""

from __future__ import annotations

from decimal import Decimal

from isa_system.domain.models import FillEvent
from isa_system.execution.order_models import OrderBatch
from isa_system.utils.time import now_utc


class PaperBroker:
    """Simulate immediate fills at reference prices."""

    def fill_batch(
        self, batch: OrderBatch, reference_prices: dict[str, Decimal]
    ) -> list[FillEvent]:
        """Fill all orders where a reference price is available."""

        fills: list[FillEvent] = []
        for order in batch.orders:
            price = order.limit_price or reference_prices.get(order.symbol)
            if price is None:
                continue
            fills.append(
                FillEvent(
                    symbol=order.symbol,
                    filled_at_utc=now_utc(),
                    quantity=order.quantity,
                    price=price,
                    fees=Decimal("0"),
                    broker_order_id=f"paper-{batch.strategy_run_id}-{order.symbol}",
                )
            )
        return fills
