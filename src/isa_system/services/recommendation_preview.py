"""Preview-only sizing from recommendation hand-off rows."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from isa_system.portfolio.costs import CostModel, InstrumentCostFlags
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot
from isa_system.services.recommendation_handoff import (
    HandoffStatus,
    RecommendationHandoffResponse,
)
from isa_system.services.valuation import research_symbol_for_position
from isa_system.utils.time import now_utc, require_utc

ALGO_SLEEVE_WEIGHT = Decimal("0.20")
MAX_NEW_IDEA_WEIGHT = Decimal("0.04")
DEFAULT_TRIM_FRACTION = Decimal("0.25")


class RecommendationPreviewRow(BaseModel):
    """One selected recommendation mapped to preview-only sizing."""

    symbol: str
    research_symbol: str
    broker_ticker: str | None = None
    side: Literal["BUY", "SELL", "HOLD"]
    eligible: bool
    target_weight: float
    estimated_notional_gbp: float
    estimated_total_cost_gbp: float
    research_review_status: str | None = None
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    rationale: str


class RecommendationPreviewResponse(BaseModel):
    """Preview-only recommendation sizing response."""

    mode: Literal["preview"] = "preview"
    generated_at_utc: datetime
    total_equity_gbp: float | None
    selected_count: int
    eligible_count: int
    estimated_total_cost_gbp: float
    rows: list[RecommendationPreviewRow]
    warnings: list[str] = Field(default_factory=list)


def build_preview_from_recommendation_handoff(
    *,
    selected_symbols: list[str],
    snapshot: BrokerPortfolioSnapshot,
    handoff: RecommendationHandoffResponse,
    cost_model: CostModel | None = None,
    total_equity_gbp: Decimal | None = None,
) -> RecommendationPreviewResponse:
    """Create preview-only sizing rows from selected, eligible recommendation rows."""

    model = cost_model or CostModel()
    selected_keys = [symbol.upper() for symbol in selected_symbols]
    handoff_by_symbol = {row.research_symbol.upper(): row for row in handoff.rows} | {
        row.symbol.upper(): row for row in handoff.rows
    }
    equity = total_equity_gbp if total_equity_gbp is not None else _total_equity(snapshot)
    warnings = [
        "Recommendation preview is sizing context only; it does not submit orders.",
        "Live submit remains disabled unless all existing arming and risk controls pass.",
    ]
    if equity is None or equity <= 0:
        warnings.append("Total equity is unavailable, so notional estimates are zero.")

    buy_count = max(
        1,
        sum(
            1
            for symbol in selected_keys
            if (handoff_by_symbol.get(symbol) is not None)
            and handoff_by_symbol[symbol].proposed_preview_action == "BUY"
        ),
    )
    buy_weight = min(MAX_NEW_IDEA_WEIGHT, ALGO_SLEEVE_WEIGHT / Decimal(buy_count))
    position_values = _position_values(snapshot)
    rows: list[RecommendationPreviewRow] = []
    for key in selected_keys:
        handoff_row = handoff_by_symbol.get(key)
        if handoff_row is None:
            rows.append(_missing_row(key))
            continue
        eligible = (
            handoff_row.eligible_for_preview
            and handoff_row.handoff_status == HandoffStatus.ELIGIBLE
        )
        notional = (
            _notional_for_row(
                handoff_row.proposed_preview_action,
                equity=equity,
                buy_weight=buy_weight,
                current_value=position_values.get(handoff_row.research_symbol.upper()),
            )
            if eligible
            else Decimal("0")
        )
        instrument = InstrumentCostFlags(
            currency=_currency_for_row(handoff_row.broker_ticker),
            country=_country_for_row(handoff_row.broker_ticker),
            asset_type="STOCK",
        )
        estimated_cost = (
            model.estimate(
                notional, side=handoff_row.proposed_preview_action, instrument=instrument
            )
            if notional > 0
            else Decimal("0")
        )
        rows.append(
            RecommendationPreviewRow(
                symbol=handoff_row.symbol,
                research_symbol=handoff_row.research_symbol,
                broker_ticker=handoff_row.broker_ticker,
                side=handoff_row.proposed_preview_action,
                eligible=eligible,
                target_weight=float(buy_weight)
                if eligible and handoff_row.proposed_preview_action == "BUY"
                else 0.0,
                estimated_notional_gbp=float(notional),
                estimated_total_cost_gbp=float(estimated_cost),
                research_review_status=handoff_row.research_review_status,
                blockers=handoff_row.blockers,
                warnings=[] if eligible else ["Selected row is not eligible for preview sizing."],
                rationale=handoff_row.reason,
            )
        )
    return RecommendationPreviewResponse(
        generated_at_utc=require_utc(now_utc()),
        total_equity_gbp=float(equity) if equity is not None else None,
        selected_count=len(selected_symbols),
        eligible_count=sum(1 for row in rows if row.eligible),
        estimated_total_cost_gbp=float(
            sum(Decimal(str(row.estimated_total_cost_gbp)) for row in rows)
        ),
        rows=rows,
        warnings=warnings,
    )


def _total_equity(snapshot: BrokerPortfolioSnapshot) -> Decimal | None:
    if snapshot.total_value is not None:
        return Decimal(str(snapshot.total_value))
    value = Decimal(str(snapshot.available_to_trade or 0))
    for position in snapshot.positions:
        value += Decimal(str(position.current_value or 0))
    return value if value > 0 else None


def _position_values(snapshot: BrokerPortfolioSnapshot) -> dict[str, Decimal]:
    rows: dict[str, Decimal] = {}
    for position in snapshot.positions:
        rows[research_symbol_for_position(position).upper()] = Decimal(
            str(position.current_value or 0)
        )
    return rows


def _notional_for_row(
    side: str,
    *,
    equity: Decimal | None,
    buy_weight: Decimal,
    current_value: Decimal | None,
) -> Decimal:
    if side == "BUY":
        return (equity or Decimal("0")) * buy_weight
    if side == "SELL":
        return (current_value or Decimal("0")) * DEFAULT_TRIM_FRACTION
    return Decimal("0")


def _missing_row(symbol: str) -> RecommendationPreviewRow:
    return RecommendationPreviewRow(
        symbol=symbol,
        research_symbol=symbol,
        side="HOLD",
        eligible=False,
        target_weight=0.0,
        estimated_notional_gbp=0.0,
        estimated_total_cost_gbp=0.0,
        blockers=["RECOMMENDATION_NOT_FOUND"],
        warnings=["Selected symbol was not found in current recommendations."],
        rationale="Refresh recommendations before preview sizing.",
    )


def _currency_for_row(broker_ticker: str | None) -> str:
    if broker_ticker and "_US_" in broker_ticker.upper():
        return "USD"
    return "GBP"


def _country_for_row(broker_ticker: str | None) -> str:
    if broker_ticker and "_US_" in broker_ticker.upper():
        return "US"
    return "GB"
