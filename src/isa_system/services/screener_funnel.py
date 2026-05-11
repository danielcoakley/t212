"""Explainable additive screener funnel for recommendation candidates."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from isa_system.services.instrument_validation import InstrumentValidationResponse
from isa_system.services.recommendation_handoff import RecommendationHandoffResponse
from isa_system.services.recommendations import RecommendationAction, RecommendationsResponse


class ScreenerFunnelRow(BaseModel):
    """One candidate as it passes or fails a funnel stage."""

    research_symbol: str
    source: str
    action: RecommendationAction
    composite_score: float
    broker_validation_status: str | None = None
    broker_ticker: str | None = None
    research_review_status: str | None = None
    preview_eligible: bool = False
    passed: bool
    reasons: list[str] = Field(default_factory=list)


class ScreenerFunnelStage(BaseModel):
    """One additive screener stage."""

    stage_id: str
    name: str
    purpose: str
    starting_count: int
    passed_count: int
    removed_count: int
    passed_rows: list[ScreenerFunnelRow]
    removed_rows: list[ScreenerFunnelRow]
    removal_reasons: dict[str, int] = Field(default_factory=dict)


class ScreenerFunnelResponse(BaseModel):
    """Full screener funnel used by the dashboard."""

    universe_count: int = 0
    scored_count: int = 0
    unscored_count: int = 0
    stages: list[ScreenerFunnelStage]
    final_candidates: list[ScreenerFunnelRow]
    warnings: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class _CandidateContext:
    research_symbol: str
    source: str
    action: RecommendationAction
    composite_score: float
    risk_flags: list[str]
    warnings: list[str]
    broker_validation_status: str | None
    broker_ticker: str | None
    research_review_status: str | None
    preview_eligible: bool


def build_screener_funnel(
    recommendations: RecommendationsResponse,
    instrument_validation: InstrumentValidationResponse,
    handoff: RecommendationHandoffResponse,
    *,
    universe_symbols: list[str],
) -> ScreenerFunnelResponse:
    """Build an explainable funnel from universe seed to deep-research candidates."""

    contexts = _contexts(recommendations, instrument_validation, handoff)
    universe_count = len(set(symbol.upper() for symbol in universe_symbols))
    scored_count = len(contexts)
    unscored_count = max(0, universe_count - scored_count)
    stages: list[ScreenerFunnelStage] = []
    remaining = list(contexts)
    stage_specs: list[
        tuple[
            str,
            str,
            str,
            Literal["seed", "broker", "evidence", "catalyst", "rank", "research"],
        ]
    ] = [
        (
            "seed",
            "Broker universe and holdings seed",
            "Trading 212 metadata and current holdings form the scored candidate set.",
            "seed",
        ),
        (
            "broker_validation",
            "Broker symbol validation",
            "Keep holdings and candidates with a broker metadata match or explicit "
            "holding confirmation.",
            "broker",
        ),
        (
            "evidence_available",
            "Evidence availability",
            "Keep rows with enough valuation or technical evidence to score; "
            "show missing-data blockers.",
            "evidence",
        ),
        (
            "catalyst_clear",
            "Catalyst and event veto",
            "Remove rows inside known blackout or unmanaged event windows.",
            "catalyst",
        ),
        (
            "ranked_candidates",
            "Ranked review candidates",
            "Keep BUY, WATCH, HOLD, and SELL review rows for operator attention; "
            "remove blocked rows.",
            "rank",
        ),
        (
            "deep_research_shortlist",
            "Deep research shortlist",
            "Keep BUY/add or WATCH candidates most relevant for thesis validation.",
            "research",
        ),
    ]
    for index, (stage_id, name, purpose, rule) in enumerate(stage_specs):
        stage = _build_stage(stage_id, name, purpose, remaining, rule)
        if index == 0 and unscored_count:
            stage = stage.model_copy(
                update={
                    "starting_count": universe_count,
                    "removed_count": unscored_count,
                    "removal_reasons": {
                        **stage.removal_reasons,
                        "NOT_SCORED_AFTER_PROVIDER_NORMALISATION": unscored_count,
                    },
                }
            )
        stages.append(stage)
        remaining = []
        for row in stage.passed_rows:
            context = _row_context(row, contexts)
            if context is not None:
                remaining.append(context)

    warnings = list(recommendations.warnings)
    if len(universe_symbols) > len(contexts):
        warnings.append(
            "Some universe symbols are not in the scored workflow, usually because they were "
            "deduplicated against holdings or unavailable after provider normalisation."
        )
    return ScreenerFunnelResponse(
        universe_count=universe_count,
        scored_count=scored_count,
        unscored_count=unscored_count,
        stages=stages,
        final_candidates=stages[-1].passed_rows if stages else [],
        warnings=warnings,
    )


def _contexts(
    recommendations: RecommendationsResponse,
    instrument_validation: InstrumentValidationResponse,
    handoff: RecommendationHandoffResponse,
) -> list[_CandidateContext]:
    validation_by_symbol = {row.research_symbol.upper(): row for row in instrument_validation.rows}
    handoff_by_symbol = {row.research_symbol.upper(): row for row in handoff.rows}
    rows: list[_CandidateContext] = []
    for item in recommendations.recommendations:
        key = item.candidate.research_symbol.upper()
        validation = validation_by_symbol.get(key)
        handoff_row = handoff_by_symbol.get(key)
        rows.append(
            _CandidateContext(
                research_symbol=item.candidate.research_symbol,
                source=item.candidate.source,
                action=item.action,
                composite_score=item.scores.composite,
                risk_flags=list(item.risk_flags),
                warnings=list(item.warnings),
                broker_validation_status=validation.status.value if validation else None,
                broker_ticker=validation.broker_ticker if validation else None,
                research_review_status=handoff_row.research_review_status if handoff_row else None,
                preview_eligible=handoff_row.eligible_for_preview if handoff_row else False,
            )
        )
    return sorted(rows, key=lambda row: (-row.composite_score, row.research_symbol))


def _build_stage(
    stage_id: str,
    name: str,
    purpose: str,
    rows: list[_CandidateContext],
    rule: Literal["seed", "broker", "evidence", "catalyst", "rank", "research"],
) -> ScreenerFunnelStage:
    passed: list[ScreenerFunnelRow] = []
    removed: list[ScreenerFunnelRow] = []
    for row in rows:
        row_passed, reasons = _evaluate(row, rule)
        funnel_row = _funnel_row(row, passed=row_passed, reasons=reasons)
        if row_passed:
            passed.append(funnel_row)
        else:
            removed.append(funnel_row)
    removal_reasons = Counter(reason for row in removed for reason in row.reasons)
    return ScreenerFunnelStage(
        stage_id=stage_id,
        name=name,
        purpose=purpose,
        starting_count=len(rows),
        passed_count=len(passed),
        removed_count=len(removed),
        passed_rows=passed,
        removed_rows=removed,
        removal_reasons=dict(sorted(removal_reasons.items())),
    )


def _evaluate(
    row: _CandidateContext,
    rule: Literal["seed", "broker", "evidence", "catalyst", "rank", "research"],
) -> tuple[bool, list[str]]:
    if rule == "seed":
        return True, ["IN_UNIVERSE_OR_HOLDING"]
    if rule == "broker":
        if row.source == "holding" or row.broker_validation_status in {
            "BROKER_MATCHED",
            "HOLDING_CONFIRMED",
        }:
            return True, ["BROKER_VALIDATED"]
        return False, ["BROKER_MAPPING_REQUIRED"]
    if rule == "evidence":
        blockers = [
            flag
            for flag in row.risk_flags
            if flag in {"MISSING_FUNDAMENTALS", "MISSING_TECHNICALS"}
        ]
        if len(blockers) == 2:
            return False, blockers
        return True, ["HAS_MINIMUM_EVIDENCE"]
    if rule == "catalyst":
        if "CATALYST_BLACKOUT" in row.risk_flags:
            return False, ["CATALYST_BLACKOUT"]
        return True, ["NO_BLACKOUT"]
    if rule == "rank":
        if row.action == RecommendationAction.BLOCKED:
            return False, row.risk_flags or ["BLOCKED"]
        return True, [f"ACTION_{row.action.value}"]
    if rule == "research":
        if row.action in {RecommendationAction.REVIEW_BUY, RecommendationAction.WATCH}:
            return True, ["DEEP_RESEARCH_CANDIDATE"]
        return False, [f"NOT_DEEP_RESEARCH_PRIORITY_{row.action.value}"]
    raise AssertionError(f"Unhandled screener rule: {rule}")


def _funnel_row(row: _CandidateContext, *, passed: bool, reasons: list[str]) -> ScreenerFunnelRow:
    return ScreenerFunnelRow(
        research_symbol=row.research_symbol,
        source=row.source,
        action=row.action,
        composite_score=row.composite_score,
        broker_validation_status=row.broker_validation_status,
        broker_ticker=row.broker_ticker,
        research_review_status=row.research_review_status,
        preview_eligible=row.preview_eligible,
        passed=passed,
        reasons=list(dict.fromkeys(reasons)),
    )


def _row_context(
    row: ScreenerFunnelRow, contexts: list[_CandidateContext]
) -> _CandidateContext | None:
    key = row.research_symbol.upper()
    return next((context for context in contexts if context.research_symbol.upper() == key), None)
