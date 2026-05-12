"""Local Trading 212 order preview generation."""

from __future__ import annotations

from isa_system.trading212.models import OrderPreview, OrderPreviewRequest
from isa_system.utils.hashing import sha256_digest
from isa_system.utils.time import now_utc


def create_order_preview(request: OrderPreviewRequest) -> OrderPreview:
    """Create a local order preview without touching Trading 212."""

    side = request.side.upper()
    quantity = (
        round(request.estimated_trade_value / request.current_price, 6)
        if request.current_price and request.current_price > 0
        else None
    )
    estimated_fx = (
        0.0 if request.currency.upper() in {"GBP", "GBX"} else request.estimated_trade_value * 0.002
    )
    estimated_sdrt = (
        request.estimated_trade_value * 0.005 if side == "BUY" and _uk_stampable(request) else 0.0
    )
    duplicate_hash = sha256_digest(
        {
            "symbol": request.symbol.upper(),
            "side": side,
            "estimated_trade_value": round(request.estimated_trade_value, 2),
            "target_weight": request.target_weight,
        }
    )
    warnings = [
        "Local preview only; no live Trading 212 order submission exists.",
        "Manual approval is required before any external broker action.",
    ]
    return OrderPreview(
        preview_id=duplicate_hash[:20],
        symbol=request.symbol.upper(),
        side=side,
        quantity=quantity,
        estimated_trade_value=request.estimated_trade_value,
        estimated_fx_impact=round(estimated_fx, 2),
        estimated_sdrt=round(estimated_sdrt, 2),
        cash_buffer_effect=-request.estimated_trade_value
        if side == "BUY"
        else request.estimated_trade_value,
        post_trade_target_weight=request.post_trade_target_weight or request.target_weight,
        risk_warnings=warnings,
        manual_approval_required=True,
        duplicate_order_hash=duplicate_hash,
        created_at_utc=now_utc(),
    )


def _uk_stampable(request: OrderPreviewRequest) -> bool:
    return request.currency.upper() in {"GBP", "GBX"} or request.symbol.upper().endswith(".L")
