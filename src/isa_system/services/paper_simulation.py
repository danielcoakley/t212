"""Paper-mode fill simulation derived from preview-only rebalance rows."""

from __future__ import annotations

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from pydantic import BaseModel

from isa_system.services.rebalance_preview import RebalancePreviewSnapshot
from isa_system.utils.hashing import sha256_digest
from isa_system.utils.time import now_utc


class PaperFillPreview(BaseModel):
    """One simulated paper fill row for operator review."""

    symbol: str
    side: Literal["BUY", "SELL"]
    quantity: Decimal
    fill_price_account: Decimal
    notional: Decimal
    estimated_fees: Decimal
    status: Literal["simulated", "skipped"]
    note: str


class PaperSimulationSnapshot(BaseModel):
    """Preview-only paper simulation result."""

    generated_at_utc: datetime
    source_batch_hash: str
    simulation_hash: str
    fill_count: int
    estimated_notional: Decimal
    estimated_fees: Decimal
    fills: list[PaperFillPreview]
    warnings: list[str]


def simulate_paper_fills(preview: RebalancePreviewSnapshot) -> PaperSimulationSnapshot:
    """Simulate paper fills for preview rows without persisting or touching the broker."""

    fills: list[PaperFillPreview] = []
    warnings = [
        "Paper simulation only: no order is sent to Trading 212 and no fill is persisted.",
        "Fill price is derived from account-currency preview notional per estimated quantity.",
    ]
    for row in preview.rows:
        if row.status != "preview_blocked" or row.side == "HOLD" or row.estimated_quantity is None:
            continue
        quantity = abs(row.estimated_quantity)
        if quantity <= 0:
            continue
        fill_price = _money(row.estimated_notional / quantity)
        fills.append(
            PaperFillPreview(
                symbol=row.symbol,
                side=row.side,
                quantity=quantity,
                fill_price_account=fill_price,
                notional=row.estimated_notional,
                estimated_fees=row.costs.total,
                status="simulated",
                note="Would fill immediately in local paper mode using preview assumptions.",
            )
        )
    simulation_hash = sha256_digest([fill.model_dump(mode="json") for fill in fills])
    return PaperSimulationSnapshot(
        generated_at_utc=now_utc(),
        source_batch_hash=preview.batch_hash,
        simulation_hash=simulation_hash,
        fill_count=len(fills),
        estimated_notional=_money(sum((fill.notional for fill in fills), Decimal("0"))),
        estimated_fees=_money(sum((fill.estimated_fees for fill in fills), Decimal("0"))),
        fills=fills,
        warnings=warnings,
    )


def _money(value: Decimal) -> Decimal:
    """Quantise money-like Decimal values."""

    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
