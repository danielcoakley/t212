"""Order manager with local idempotency safeguards."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from isa_system.db.crud import reserve_idempotency_key
from isa_system.execution.order_models import OrderBatch
from isa_system.utils.hashing import make_idempotency_key, sha256_digest


class DuplicateOrderError(RuntimeError):
    """Raised when a duplicate local order batch is blocked."""


class OrderManager:
    """Create and reserve safe order batch submissions."""

    def __init__(self, environment: str) -> None:
        self.environment = environment

    def payload_hash(self, batch: OrderBatch) -> str:
        """Return the canonical hash for a batch payload."""

        return sha256_digest([order.model_dump(mode="json") for order in batch.orders])

    def idempotency_key(self, batch: OrderBatch, trading_day: date) -> str:
        """Return the local idempotency key for a batch."""

        return make_idempotency_key(
            strategy_run_id=batch.strategy_run_id,
            environment=self.environment,
            payload=[order.model_dump(mode="json") for order in batch.orders],
            trading_date=trading_day,
        )

    def reserve_for_submit(
        self,
        session: Session,
        batch: OrderBatch,
        trading_day: date,
        order_batch_id: str | None = None,
    ) -> str:
        """Reserve the batch idempotency key or raise on duplicate."""

        key = self.idempotency_key(batch, trading_day)
        ok = reserve_idempotency_key(
            session, key=key, payload_hash=self.payload_hash(batch), order_batch_id=order_batch_id
        )
        if not ok:
            raise DuplicateOrderError("Duplicate order batch blocked before broker submission.")
        return key
