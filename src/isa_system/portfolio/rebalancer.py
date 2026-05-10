"""Rebalance preview generation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from isa_system.domain.enums import OrderSide
from isa_system.domain.models import RebalancePlan, TargetWeight, Trade
from isa_system.portfolio.costs import CostModel, InstrumentCostFlags
from isa_system.utils.hashing import sha256_digest
from isa_system.utils.time import now_utc


def build_rebalance_plan(
    *,
    run_id: str,
    current_weights: dict[str, float],
    targets: list[TargetWeight],
    prices: dict[str, Decimal],
    total_equity_gbp: Decimal,
    cost_model: CostModel,
    trading_day: date | None = None,
) -> RebalancePlan:
    """Build a deterministic current-vs-target preview."""

    _ = trading_day
    target_map = {item.symbol: item.weight for item in targets}
    symbols = sorted(set(current_weights) | set(target_map))
    trades: list[Trade] = []
    warnings: list[str] = []
    turnover = 0.0
    for symbol in symbols:
        current = Decimal(str(current_weights.get(symbol, 0.0)))
        target = Decimal(str(target_map.get(symbol, 0.0)))
        diff = target - current
        if abs(diff) < Decimal("0.0001"):
            continue
        price = prices.get(symbol)
        if price is None or price <= 0:
            warnings.append(f"Missing price for {symbol}; trade vetoed.")
            continue
        notional = (abs(diff) * total_equity_gbp).quantize(Decimal("0.0001"))
        quantity = (notional / price).quantize(Decimal("0.000001"))
        side = OrderSide.BUY if diff > 0 else OrderSide.SELL
        flags = InstrumentCostFlags(
            currency="GBP", country="GB", sdrt_applicable=symbol.endswith(".L")
        )
        cost = cost_model.estimate(notional, side=side.value, instrument=flags)
        trades.append(
            Trade(
                symbol=symbol,
                side=side,
                quantity=quantity,
                estimated_price=price,
                estimated_notional=notional,
                estimated_cost=cost,
                reason="target_weight_diff",
            )
        )
        turnover += float(abs(diff))
    batch_hash = sha256_digest([trade.__dict__ for trade in trades])
    return RebalancePlan(
        run_id=run_id,
        as_of_utc=now_utc(),
        current_weights=current_weights,
        target_weights=target_map,
        trades=tuple(trades),
        estimated_total_cost=sum((trade.estimated_cost for trade in trades), Decimal("0")),
        turnover=turnover,
        warnings=tuple(warnings),
        vetoes=tuple(warnings),
        batch_hash=batch_hash,
    )
