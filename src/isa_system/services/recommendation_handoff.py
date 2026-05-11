"""Review hand-off from recommendation rows into preview workflow."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from isa_system.services.deep_research import DeepResearchReview
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
    deep_research_required: bool = False
    research_review_status: str | None = None
    research_review_id: str | None = None
    eligible_for_preview: bool = False
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
    research_reviews: dict[str, DeepResearchReview] | None = None,
) -> RecommendationHandoffResponse:
    """Map recommendations to preview workflow readiness without creating orders."""

    instrument_rows = (
        {row.research_symbol.upper(): row for row in instrument_validation.rows}
        if instrument_validation
        else {}
    )
    review_rows = research_reviews or {}
    rows = []
    for item in response.recommendations:
        key = item.candidate.research_symbol.upper()
        rows.append(
            _handoff_row(item, instrument_rows.get(key), _research_for_symbol(key, review_rows))
        )
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
    item: TradeRecommendation,
    instrument_row: InstrumentValidationRow | None,
    research_review: DeepResearchReview | None,
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
            eligible_for_preview=False,
            reason="Recommendation is blocked by missing data, event veto, or source warnings.",
            blockers=blockers or item.risk_flags,
            next_step="Resolve blockers before this row can be reviewed for preview.",
        )

    if "CATALYST_BLACKOUT" in item.risk_flags:
        return _blocked_event_row(item, blockers, instrument_row, research_review)

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
            deep_research_required=False,
            eligible_for_preview=True,
            reason=(
                "Existing holding has weak review score and can be considered "
                "for trim/reduce preview."
            ),
            blockers=blockers,
            next_step="Review in rebalance preview sizing with cost, sleeve, and audit checks.",
        )

    if item.action == RecommendationAction.REVIEW_BUY:
        research_blockers = _research_blockers(research_review)
        research_status = _research_review_status(research_review)
        research_id = research_review.id if research_review else None
        if candidate.source == "holding":
            if research_blockers:
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
                    deep_research_required=True,
                    research_review_status=research_status,
                    research_review_id=research_id,
                    eligible_for_preview=False,
                    reason=(
                        "Existing holding scored positively but add sizing requires a "
                        "non-expired deep research pass first."
                    ),
                    blockers=[*blockers, *research_blockers],
                    next_step="Run deep research review, then reopen preview sizing if it passes.",
                )
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
                deep_research_required=True,
                research_review_status=research_status,
                research_review_id=research_id,
                eligible_for_preview=True,
                reason=(
                    "Existing broker holding has a current deep research pass and may be "
                    "reviewed for add sizing."
                ),
                blockers=blockers,
                next_step="Review in rebalance preview sizing with sector, cash, and cost checks.",
            )
        broker_validated = instrument_status in {
            InstrumentValidationStatus.BROKER_MATCHED.value,
            InstrumentValidationStatus.HOLDING_CONFIRMED.value,
        }
        validation_blockers = (
            [] if broker_validated else _broker_validation_blockers(instrument_status)
        )
        all_blockers = [*blockers, *validation_blockers, *research_blockers]
        status = (
            HandoffStatus.ELIGIBLE
            if broker_validated and not research_blockers
            else HandoffStatus.REVIEW_REQUIRED
        )
        if status == HandoffStatus.ELIGIBLE:
            reason = (
                "Market-scan idea has broker metadata validation and a non-expired deep "
                "research pass; it can enter preview-only sizing."
            )
            next_step = "Review preview sizing, costs, sleeve limits, and operator controls."
        elif broker_validated:
            reason = (
                "Market-scan idea matched broker metadata but needs a non-expired deep "
                "research pass before preview sizing."
            )
            next_step = "Run deep research review, then reopen preview sizing if it passes."
        else:
            reason = "Market-scan idea needs broker instrument and ISA eligibility validation."
            next_step = (
                "Validate Trading 212 instrument mapping, ISA availability, liquidity, "
                "and official-source timing before adding to preview targets."
            )
        return RecommendationHandoffRow(
            symbol=candidate.symbol,
            research_symbol=candidate.research_symbol,
            source=candidate.source,
            recommendation_action=item.action,
            proposed_preview_action="BUY",
            handoff_status=status,
            composite_score=item.scores.composite,
            instrument_validation_status=instrument_status,
            broker_ticker=broker_ticker,
            deep_research_required=True,
            research_review_status=research_status,
            research_review_id=research_id,
            eligible_for_preview=status == HandoffStatus.ELIGIBLE,
            reason=reason,
            blockers=all_blockers,
            next_step=next_step,
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
            eligible_for_preview=False,
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
        eligible_for_preview=False,
        reason="Existing holding is not asking for a trade in the current review cycle.",
        blockers=blockers,
        next_step="Keep holding under normal monitoring and catalyst checks.",
    )


def _blocked_event_row(
    item: TradeRecommendation,
    blockers: Sequence[str],
    instrument_row: InstrumentValidationRow | None,
    research_review: DeepResearchReview | None,
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
        deep_research_required=item.action == RecommendationAction.REVIEW_BUY,
        research_review_status=_research_review_status(research_review),
        research_review_id=research_review.id if research_review else None,
        eligible_for_preview=False,
        reason="Known catalyst blackout blocks buy/add hand-off until the window clears.",
        blockers=list(blockers) or ["CATALYST_BLACKOUT"],
        next_step="Wait for the event window to pass and refresh official event validation.",
    )


def _handoff_blockers(item: TradeRecommendation) -> list[str]:
    hard_flags = [flag for flag in item.risk_flags if flag != "MISSING_SENTIMENT"]
    blockers = list(dict.fromkeys([*hard_flags, *item.warnings]))
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


def _research_for_symbol(
    key: str, research_reviews: dict[str, DeepResearchReview]
) -> DeepResearchReview | None:
    return research_reviews.get(key) or research_reviews.get(key.upper())


def _research_review_status(review: DeepResearchReview | None) -> str | None:
    if review is None:
        return "MISSING"
    if review.is_valid_pass:
        return "RESEARCH_PASSED"
    return review.status.value if review.decision is None else review.decision.value


def _research_blockers(review: DeepResearchReview | None) -> list[str]:
    if review is None:
        return ["DEEP_RESEARCH_REQUIRED"]
    if review.is_valid_pass:
        return []
    if review.status.value == "EXPIRED":
        return ["DEEP_RESEARCH_EXPIRED"]
    if review.decision is not None:
        return [f"DEEP_RESEARCH_{review.decision.value}"]
    return [f"DEEP_RESEARCH_{review.status.value}"]
