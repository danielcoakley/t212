"""Review hand-off from recommendation rows into preview workflow."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from isa_system.services.instrument_validation import (
    InstrumentValidationResponse,
    InstrumentValidationRow,
    InstrumentValidationStatus,
)
from isa_system.services.recommendations import (
    RecommendationAction,
    RecommendationsResponse,
    TradeRecommendation,
)
from isa_system.utils.time import require_utc


class HandoffStatus(StrEnum):
    """Preview-readiness status for a recommendation row."""

    ELIGIBLE = "ELIGIBLE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    BLOCKED = "BLOCKED"
    NO_ACTION = "NO_ACTION"


class RecommendationHandoffRow(BaseModel):
    """One recommendation row mapped to its next safe workflow step."""

    symbol: str
    research_symbol: str
    source: Literal["holding", "watchlist", "default"]
    recommendation_action: RecommendationAction
    proposed_preview_action: Literal["BUY", "SELL", "HOLD"]
    handoff_status: HandoffStatus
    composite_score: float = Field(ge=-1.0, le=1.0)
    instrument_validation_status: str | None = None
    broker_ticker: str | None = None
    reason: str
    blockers: list[str] = Field(default_factory=list)
    next_step: str


class RecommendationHandoffResponse(BaseModel):
    """Review hand-off summary for dashboard and API display."""

    generated_at_utc: datetime
    provider: str
    rows: list[RecommendationHandoffRow]
    eligible_count: int
    review_required_count: int
    blocked_count: int
    warnings: list[str] = Field(default_factory=list)


def build_recommendation_handoff(
    response: RecommendationsResponse,
    *,
    instrument_validation: InstrumentValidationResponse | None = None,
) -> RecommendationHandoffResponse:
    """Map recommendations to preview workflow readiness without creating orders."""

    instrument_rows = (
        {row.research_symbol.upper(): row for row in instrument_validation.rows}
        if instrument_validation
        else {}
    )
    rows = [
        _handoff_row(item, instrument_rows.get(item.candidate.research_symbol.upper()))
        for item in response.recommendations
    ]
    return RecommendationHandoffResponse(
        generated_at_utc=require_utc(response.retrieved_at_utc),
        provider=response.provider,
        rows=rows,
        eligible_count=sum(1 for row in rows if row.handoff_status == HandoffStatus.ELIGIBLE),
        review_required_count=sum(
            1 for row in rows if row.handoff_status == HandoffStatus.REVIEW_REQUIRED
        ),
        blocked_count=sum(1 for row in rows if row.handoff_status == HandoffStatus.BLOCKED),
        warnings=[
            *response.warnings,
            "Hand-off is review-only and never submits orders or updates target weights.",
        ],
    )


def _handoff_row(
    item: TradeRecommendation, instrument_row: InstrumentValidationRow | None
) -> RecommendationHandoffRow:
    candidate = item.candidate
    blockers = _handoff_blockers(item)
    instrument_status = instrument_row.status.value if instrument_row else None
    broker_ticker = instrument_row.broker_ticker if instrument_row else None

    if item.action == RecommendationAction.BLOCKED:
        return RecommendationHandoffRow(
            symbol=candidate.symbol,
            research_symbol=candidate.research_symbol,
            source=candidate.source,
            recommendation_action=item.action,
            proposed_preview_action="HOLD",
            handoff_status=HandoffStatus.BLOCKED,
            composite_score=item.scores.composite,
            instrument_validation_status=instrument_status,
            broker_ticker=broker_ticker,
            reason="Recommendation is blocked by missing data, event veto, or source warnings.",
            blockers=blockers or item.risk_flags,
            next_step="Resolve blockers before this row can be reviewed for preview.",
        )

    if "CATALYST_BLACKOUT" in item.risk_flags:
        return _blocked_event_row(item, blockers, instrument_row)

    if item.action == RecommendationAction.REVIEW_SELL and candidate.source == "holding":
        return RecommendationHandoffRow(
            symbol=candidate.symbol,
            research_symbol=candidate.research_symbol,
            source=candidate.source,
            recommendation_action=item.action,
            proposed_preview_action="SELL",
            handoff_status=HandoffStatus.ELIGIBLE,
            composite_score=item.scores.composite,
            instrument_validation_status=instrument_status,
            broker_ticker=broker_ticker,
            reason=(
                "Existing holding has weak review score and can be considered "
                "for trim/reduce preview."
            ),
            blockers=blockers,
            next_step="Review in rebalance preview sizing with cost, sleeve, and audit checks.",
        )

    if item.action == RecommendationAction.REVIEW_BUY:
        if candidate.source == "holding":
            return RecommendationHandoffRow(
                symbol=candidate.symbol,
                research_symbol=candidate.research_symbol,
                source=candidate.source,
                recommendation_action=item.action,
                proposed_preview_action="BUY",
                handoff_status=HandoffStatus.ELIGIBLE,
                composite_score=item.scores.composite,
                instrument_validation_status=instrument_status,
                broker_ticker=broker_ticker,
                reason=(
                    "Existing broker holding scored positively and may be reviewed for add sizing."
                ),
                blockers=blockers,
                next_step="Review in rebalance preview sizing with sector, cash, and cost checks.",
            )
        broker_validated = instrument_status in {
            InstrumentValidationStatus.BROKER_MATCHED.value,
            InstrumentValidationStatus.HOLDING_CONFIRMED.value,
        }
        validation_blockers = (
            ["OFFICIAL_SOURCE_VALIDATION_REQUIRED", "ISA_LIQUIDITY_REVIEW_REQUIRED"]
            if broker_validated
            else _broker_validation_blockers(instrument_status)
        )
        return RecommendationHandoffRow(
            symbol=candidate.symbol,
            research_symbol=candidate.research_symbol,
            source=candidate.source,
            recommendation_action=item.action,
            proposed_preview_action="BUY",
            handoff_status=HandoffStatus.REVIEW_REQUIRED,
            composite_score=item.scores.composite,
            instrument_validation_status=instrument_status,
            broker_ticker=broker_ticker,
            reason=(
                "Market-scan idea matched broker metadata but still needs official-source, "
                "ISA, liquidity, and operator validation."
                if broker_validated
                else "Market-scan idea needs broker instrument and ISA eligibility validation."
            ),
            blockers=[*blockers, *validation_blockers],
            next_step=(
                "Review official-source timing, liquidity, ISA constraints, and target sizing "
                "before adding to preview."
                if broker_validated
                else "Validate Trading 212 instrument mapping, ISA availability, liquidity, "
                "and official-source timing before adding to preview targets."
            ),
        )

    if item.action == RecommendationAction.WATCH:
        return RecommendationHandoffRow(
            symbol=candidate.symbol,
            research_symbol=candidate.research_symbol,
            source=candidate.source,
            recommendation_action=item.action,
            proposed_preview_action="HOLD",
            handoff_status=HandoffStatus.NO_ACTION,
            composite_score=item.scores.composite,
            instrument_validation_status=instrument_status,
            broker_ticker=broker_ticker,
            reason=(
                "Candidate is watchlist context and does not currently clear "
                "the review-buy threshold."
            ),
            blockers=blockers,
            next_step="Keep on discovery list and refresh evidence after new data or catalysts.",
        )

    return RecommendationHandoffRow(
        symbol=candidate.symbol,
        research_symbol=candidate.research_symbol,
        source=candidate.source,
        recommendation_action=item.action,
        proposed_preview_action="HOLD",
        handoff_status=HandoffStatus.NO_ACTION,
        composite_score=item.scores.composite,
        instrument_validation_status=instrument_status,
        broker_ticker=broker_ticker,
        reason="Existing holding is not asking for a trade in the current review cycle.",
        blockers=blockers,
        next_step="Keep holding under normal monitoring and catalyst checks.",
    )


def _blocked_event_row(
    item: TradeRecommendation,
    blockers: Sequence[str],
    instrument_row: InstrumentValidationRow | None,
) -> RecommendationHandoffRow:
    candidate = item.candidate
    instrument_status = instrument_row.status.value if instrument_row else None
    broker_ticker = instrument_row.broker_ticker if instrument_row else None
    return RecommendationHandoffRow(
        symbol=candidate.symbol,
        research_symbol=candidate.research_symbol,
        source=candidate.source,
        recommendation_action=item.action,
        proposed_preview_action="HOLD",
        handoff_status=HandoffStatus.BLOCKED,
        composite_score=item.scores.composite,
        instrument_validation_status=instrument_status,
        broker_ticker=broker_ticker,
        reason="Known catalyst blackout blocks buy/add hand-off until the window clears.",
        blockers=list(blockers) or ["CATALYST_BLACKOUT"],
        next_step="Wait for the event window to pass and refresh official event validation.",
    )


def _handoff_blockers(item: TradeRecommendation) -> list[str]:
    blockers = list(dict.fromkeys([*item.risk_flags, *item.warnings]))
    if "DATA_WARNINGS" in item.risk_flags and item.action != RecommendationAction.BLOCKED:
        blockers.append("REVIEW_SOURCE_WARNINGS")
    return blockers


def _broker_validation_blockers(instrument_status: str | None) -> list[str]:
    if instrument_status in {
        InstrumentValidationStatus.NOT_CONFIGURED.value,
        InstrumentValidationStatus.ERROR.value,
    }:
        return ["BROKER_INSTRUMENT_VALIDATION_UNAVAILABLE"]
    return ["BROKER_INSTRUMENT_VALIDATION_REQUIRED"]
