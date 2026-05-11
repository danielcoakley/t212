"""Preview-only rebalance planning for the local operator dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from pydantic import BaseModel, Field

from isa_system.domain.enums import RuntimeMode
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot, BrokerPosition
from isa_system.services.valuation import HoldingsValuationResponse
from isa_system.settings import Settings, get_settings
from isa_system.utils.hashing import sha256_digest
from isa_system.utils.time import now_utc

GBP_CURRENCIES = {"GBP", "GBX"}


class RebalancePreviewSettings(BaseModel):
    """Configurable preview assumptions kept deliberately account-size neutral."""

    algo_sleeve_weight: float = Field(default=0.20, ge=0.0, le=1.0)
    core_sleeve_weight: float = Field(default=0.80, ge=0.0, le=1.0)
    cash_buffer_weight: float = Field(default=0.01, ge=0.0, le=0.50)
    max_algo_positions: int = Field(default=5, ge=1, le=50)
    max_single_name_weight: float = Field(default=0.30, ge=0.01, le=1.0)
    min_trade_notional_gbp: Decimal = Decimal("25")
    commission_bps: Decimal = Decimal("0")
    slippage_bps: Decimal = Decimal("15")
    fx_spread_bps: Decimal = Decimal("15")
    uk_sdrt_rate: Decimal = Decimal("0.005")
    ptm_levy_threshold_gbp: Decimal = Decimal("10000")
    ptm_levy_gbp: Decimal = Decimal("1.50")


class PreviewCostBreakdown(BaseModel):
    """Estimated transaction-cost components in account currency."""

    commission: Decimal
    slippage: Decimal
    fx_cost: Decimal
    sdrt: Decimal
    ptm_levy: Decimal
    total: Decimal


class RebalancePreviewRow(BaseModel):
    """One current-vs-target row for the preview table."""

    symbol: str
    name: str | None = None
    currency: str | None = None
    current_weight: float
    target_weight: float
    current_value: Decimal
    target_value: Decimal
    drift_value: Decimal
    side: Literal["BUY", "SELL", "HOLD"]
    estimated_quantity: Decimal | None = None
    estimated_notional: Decimal
    costs: PreviewCostBreakdown
    status: Literal["preview_blocked", "below_min_trade", "hold"]
    rationale: str
    warnings: list[str]


class RebalanceRiskCheck(BaseModel):
    """Risk or guardrail row displayed before any order path can proceed."""

    name: str
    passed: bool
    severity: str
    message: str


class RebalancePreviewSnapshot(BaseModel):
    """Preview-only rebalance snapshot for dashboard and API use."""

    mode: RuntimeMode
    run_id: str
    generated_at_utc: datetime
    account_currency: str | None
    total_equity: Decimal
    algo_sleeve_weight: float
    core_sleeve_weight: float
    cash_buffer_weight: float
    expected_turnover: Decimal
    expected_turnover_weight: float
    estimated_total_cost: Decimal
    batch_hash: str
    rows: list[RebalancePreviewRow]
    risk_checks: list[RebalanceRiskCheck]
    warnings: list[str]


@dataclass(frozen=True)
class _PositionInput:
    symbol: str
    name: str | None
    currency: str | None
    quantity: Decimal
    current_value: Decimal
    current_weight: float


def build_preview_from_holdings(
    broker_snapshot: BrokerPortfolioSnapshot,
    valuation_snapshot: HoldingsValuationResponse,
    *,
    settings: Settings | None = None,
    preview_settings: RebalancePreviewSettings | None = None,
) -> RebalancePreviewSnapshot:
    """Build a deterministic preview-only target plan from live read-only holdings."""

    app_settings = settings or get_settings()
    assumptions = preview_settings or RebalancePreviewSettings()
    positions = _position_inputs(broker_snapshot)
    total_equity = _total_equity(broker_snapshot, positions)
    warnings = list(broker_snapshot.warnings)
    if total_equity <= 0:
        warnings.append("Broker total equity is unavailable; rebalance preview cannot trade.")

    target_weights = _target_weights(positions, valuation_snapshot, assumptions)
    rows = [
        _preview_row(position, target_weights.get(position.symbol, 0.0), total_equity, assumptions)
        for position in positions
    ]
    estimated_total_cost = _money(sum((row.costs.total for row in rows), Decimal("0")))
    expected_turnover = _money(sum((row.estimated_notional for row in rows), Decimal("0")))
    expected_turnover_weight = float(expected_turnover / total_equity) if total_equity > 0 else 0.0
    risk_checks = _risk_checks(app_settings, rows, assumptions)
    batch_hash = sha256_digest([row.model_dump(mode="json") for row in rows])
    return RebalancePreviewSnapshot(
        mode=RuntimeMode.PREVIEW,
        run_id=f"dashboard-preview-{now_utc():%Y%m%dT%H%M%SZ}",
        generated_at_utc=now_utc(),
        account_currency=broker_snapshot.account_currency,
        total_equity=total_equity,
        algo_sleeve_weight=assumptions.algo_sleeve_weight,
        core_sleeve_weight=assumptions.core_sleeve_weight,
        cash_buffer_weight=assumptions.cash_buffer_weight,
        expected_turnover=expected_turnover,
        expected_turnover_weight=expected_turnover_weight,
        estimated_total_cost=estimated_total_cost,
        batch_hash=batch_hash,
        rows=rows,
        risk_checks=risk_checks,
        warnings=warnings,
    )


def _target_weights(
    positions: list[_PositionInput],
    valuation_snapshot: HoldingsValuationResponse,
    assumptions: RebalancePreviewSettings,
) -> dict[str, float]:
    """Blend current core weights with a simple ranked algo sleeve."""

    if not positions:
        return {}
    invested_total = sum(position.current_value for position in positions)
    if invested_total <= 0:
        return {position.symbol: 0.0 for position in positions}

    investable_weight = max(0.0, 1.0 - assumptions.cash_buffer_weight)
    core_weight = min(assumptions.core_sleeve_weight, investable_weight)
    algo_weight = min(assumptions.algo_sleeve_weight, max(0.0, investable_weight - core_weight))
    core_targets = {
        position.symbol: float(position.current_value / invested_total) * core_weight
        for position in positions
    }
    ranked_symbols = _ranked_symbols(valuation_snapshot)
    selected = [symbol for symbol in ranked_symbols if symbol in core_targets][
        : assumptions.max_algo_positions
    ]
    if not selected:
        selected = [position.symbol for position in positions[: assumptions.max_algo_positions]]
    algo_each = algo_weight / len(selected) if selected else 0.0
    targets = dict(core_targets)
    for symbol in selected:
        targets[symbol] = targets.get(symbol, 0.0) + algo_each
    return {
        symbol: min(weight, assumptions.max_single_name_weight)
        for symbol, weight in targets.items()
    }


def _ranked_symbols(snapshot: HoldingsValuationResponse) -> list[str]:
    """Rank holdings by a transparent starter score using valuation/technical fields."""

    scored: list[tuple[str, float]] = []
    for holding in snapshot.holdings:
        momentum_values = [
            value
            for value in [
                holding.technicals.momentum_1m,
                holding.technicals.momentum_3m,
                holding.technicals.momentum_6m,
                holding.technicals.momentum_12m,
            ]
            if value is not None
        ]
        momentum = sum(momentum_values) / len(momentum_values) if momentum_values else 0.0
        value_score = _inverse_or_zero(holding.valuation.trailing_pe)
        value_score += _inverse_or_zero(holding.valuation.forward_pe)
        value_score += _inverse_or_zero(holding.valuation.price_to_book)
        dividend = holding.valuation.dividend_yield or 0.0
        scored.append((holding.symbol, momentum + value_score + dividend))
    return [symbol for symbol, _ in sorted(scored, key=lambda item: item[1], reverse=True)]


def _preview_row(
    position: _PositionInput,
    target_weight: float,
    total_equity: Decimal,
    assumptions: RebalancePreviewSettings,
) -> RebalancePreviewRow:
    """Build one preview row with costs and guardrail status."""

    target_value = _money(total_equity * Decimal(str(target_weight)))
    drift = _money(target_value - position.current_value)
    notional = abs(drift)
    side: Literal["BUY", "SELL", "HOLD"]
    if notional < assumptions.min_trade_notional_gbp:
        side = "HOLD"
    else:
        side = "BUY" if drift > 0 else "SELL"
    status: Literal["preview_blocked", "below_min_trade", "hold"] = (
        "hold" if side == "HOLD" and notional == 0 else "below_min_trade"
    )
    if side != "HOLD":
        status = "preview_blocked"
    costs = _costs(notional, side, position.currency, assumptions)
    quantity = _estimated_quantity(position, drift) if side != "HOLD" else None
    warnings = _row_warnings(position, side, assumptions)
    return RebalancePreviewRow(
        symbol=position.symbol,
        name=position.name,
        currency=position.currency,
        current_weight=position.current_weight,
        target_weight=target_weight,
        current_value=position.current_value,
        target_value=target_value,
        drift_value=drift,
        side=side,
        estimated_quantity=quantity,
        estimated_notional=notional,
        costs=costs,
        status=status,
        rationale=_rationale(side, status),
        warnings=warnings,
    )


def _costs(
    notional: Decimal,
    side: str,
    currency: str | None,
    assumptions: RebalancePreviewSettings,
) -> PreviewCostBreakdown:
    """Estimate cost components for a preview notional."""

    commission = notional * assumptions.commission_bps / Decimal("10000")
    slippage = notional * assumptions.slippage_bps / Decimal("10000")
    fx_cost = Decimal("0")
    if (currency or "").upper() not in GBP_CURRENCIES:
        fx_cost = notional * assumptions.fx_spread_bps / Decimal("10000")
    sdrt = Decimal("0")
    if side == "BUY" and _sdrt_heuristic(currency):
        sdrt = notional * assumptions.uk_sdrt_rate
    ptm_levy = Decimal("0")
    if notional >= assumptions.ptm_levy_threshold_gbp and _sdrt_heuristic(currency):
        ptm_levy = assumptions.ptm_levy_gbp
    total = commission + slippage + fx_cost + sdrt + ptm_levy
    return PreviewCostBreakdown(
        commission=_money(commission),
        slippage=_money(slippage),
        fx_cost=_money(fx_cost),
        sdrt=_money(sdrt),
        ptm_levy=_money(ptm_levy),
        total=_money(total),
    )


def _risk_checks(
    settings: Settings,
    rows: list[RebalancePreviewRow],
    assumptions: RebalancePreviewSettings,
) -> list[RebalanceRiskCheck]:
    """Return visible pre-trade guardrails for the preview."""

    turnover = sum((row.estimated_notional for row in rows), Decimal("0"))
    has_preview_trades = any(row.status == "preview_blocked" for row in rows)
    return [
        RebalanceRiskCheck(
            name="mode",
            passed=settings.runtime_mode == RuntimeMode.PREVIEW,
            severity="error" if settings.runtime_mode != RuntimeMode.PREVIEW else "info",
            message=(
                f"Runtime mode is {settings.runtime_mode.value}; dashboard preview does not submit."
            ),
        ),
        RebalanceRiskCheck(
            name="live_armed",
            passed=not settings.live_armed,
            severity="error" if settings.live_armed else "info",
            message="Live trading is disarmed for this preview surface.",
        ),
        RebalanceRiskCheck(
            name="kill_switch",
            passed=not settings.kill_switch_enabled,
            severity="error" if settings.kill_switch_enabled else "info",
            message="Kill switch is clear."
            if not settings.kill_switch_enabled
            else "Kill switch is enabled.",
        ),
        RebalanceRiskCheck(
            name="duplicate_order_prevention",
            passed=not has_preview_trades,
            severity="warning" if has_preview_trades else "info",
            message="Preview rows with BUY/SELL are blocked until local idempotency is reserved.",
        ),
        RebalanceRiskCheck(
            name="minimum_trade_size",
            passed=turnover >= assumptions.min_trade_notional_gbp or turnover == 0,
            severity="warning",
            message=f"Minimum trade notional is GBP {assumptions.min_trade_notional_gbp}.",
        ),
    ]


def _position_inputs(snapshot: BrokerPortfolioSnapshot) -> list[_PositionInput]:
    """Normalise broker positions for preview calculations."""

    positions = []
    total = _total_from_snapshot(snapshot)
    for position in snapshot.positions:
        current_value = _position_value(position)
        if current_value is None:
            continue
        current_weight = float(current_value / total) if total > 0 else 0.0
        positions.append(
            _PositionInput(
                symbol=position.symbol,
                name=position.name,
                currency=position.currency,
                quantity=Decimal(str(position.quantity or 0)),
                current_value=current_value,
                current_weight=current_weight,
            )
        )
    return sorted(positions, key=lambda item: item.current_value, reverse=True)


def _total_equity(snapshot: BrokerPortfolioSnapshot, positions: list[_PositionInput]) -> Decimal:
    """Return total account value from broker or valued positions plus cash."""

    broker_total = _total_from_snapshot(snapshot)
    if broker_total > 0:
        return broker_total
    cash = Decimal(str(snapshot.available_to_trade or 0))
    return _money(sum((position.current_value for position in positions), cash))


def _total_from_snapshot(snapshot: BrokerPortfolioSnapshot) -> Decimal:
    """Return broker total as Decimal."""

    return Decimal(str(snapshot.total_value or 0))


def _position_value(position: BrokerPosition) -> Decimal | None:
    """Return current position value in account currency where available."""

    if position.current_value is not None:
        return _money(Decimal(str(position.current_value)))
    if position.current_price is not None and position.quantity:
        return _money(Decimal(str(position.current_price)) * Decimal(str(position.quantity)))
    return None


def _estimated_quantity(position: _PositionInput, drift: Decimal) -> Decimal | None:
    """Estimate quantity by scaling the current holding value, avoiding FX price confusion."""

    if position.current_value <= 0 or position.quantity <= 0:
        return None
    return _quantity(position.quantity * drift / position.current_value)


def _row_warnings(
    position: _PositionInput,
    side: str,
    assumptions: RebalancePreviewSettings,
) -> list[str]:
    """Return row-level caveats."""

    warnings = ["Preview-only: no order will be submitted from this table."]
    if side == "BUY" and _sdrt_heuristic(position.currency):
        warnings.append("UK share purchase may incur SDRT; verify AIM/ETF exemptions.")
    if (position.currency or "").upper() not in GBP_CURRENCIES:
        warnings.append("Non-GBP instrument: FX spread estimate is included.")
    if abs(position.current_weight) > assumptions.max_single_name_weight:
        warnings.append("Current holding already exceeds configured single-name cap.")
    return warnings


def _rationale(side: str, status: str) -> str:
    """Return a concise row rationale."""

    if status == "below_min_trade":
        return "Drift is below the configured minimum trade size."
    if side == "HOLD":
        return "Current weight already matches preview target."
    return "Starter sleeve target differs from current weight; blocked pending paper workflow."


def _sdrt_heuristic(currency: str | None) -> bool:
    """Heuristic SDRT flag until instrument registry exemptions are fully wired."""

    return (currency or "").upper() in GBP_CURRENCIES


def _inverse_or_zero(value: float | None) -> float:
    """Return a simple inverse score for positive valuation ratios."""

    if value is None or value <= 0:
        return 0.0
    return 1.0 / value


def _money(value: Decimal) -> Decimal:
    """Quantise money-like Decimal values."""

    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _quantity(value: Decimal) -> Decimal:
    """Quantise share quantity estimates for display."""

    return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
