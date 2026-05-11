"""Schema-light pilot paper workflow shell after recommendation preview."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from pydantic import BaseModel

from isa_system.services.paper_simulation import (
    PaperFillPreview,
    PaperSimulationSnapshot,
    simulate_recommendation_preview_fills,
)
from isa_system.services.recommendation_preview import (
    RecommendationPreviewResponse,
    RecommendationPreviewRow,
)
from isa_system.utils.time import now_utc, require_utc


class PilotPaperWorkflowRow(BaseModel):
    """One selected preview row compared with its simulated paper outcome."""

    symbol: str
    research_symbol: str
    broker_ticker: str | None = None
    side: Literal["BUY", "SELL", "HOLD"]
    preview_eligible: bool
    expected_notional_gbp: Decimal
    expected_fees_gbp: Decimal
    simulated_status: Literal["simulated", "skipped", "missing", "not_expected"]
    simulated_notional_gbp: Decimal | None = None
    simulated_fees_gbp: Decimal | None = None
    expected_vs_simulated_status: Literal[
        "matched",
        "mismatched",
        "missing_simulation",
        "preview_blocked",
        "no_paper_action_expected",
    ]
    blockers: list[str]
    warnings: list[str]
    next_action: str


class PilotPaperWorkflowSummary(BaseModel):
    """Operator-facing pilot workflow shell derived from preview and paper data."""

    mode: Literal["preview"] = "preview"
    generated_at_utc: datetime
    workflow_status: Literal[
        "ready_for_operator_review",
        "needs_attention",
        "blocked_before_paper",
        "no_paper_action",
    ]
    expected_vs_simulated_status: Literal[
        "all_expected_rows_simulated",
        "mismatched",
        "missing_simulation",
        "no_expected_paper_rows",
    ]
    selected_count: int
    preview_eligible_count: int
    simulated_fill_count: int
    preview_source_hash: str
    simulation_hash: str
    persistence_status: Literal["not_persisted"] = "not_persisted"
    reconciliation_status: Literal["not_available"] = "not_available"
    preview: RecommendationPreviewResponse
    paper_simulation: PaperSimulationSnapshot
    rows: list[PilotPaperWorkflowRow]
    warnings: list[str]
    next_action: str


def build_pilot_paper_workflow(
    preview: RecommendationPreviewResponse,
    *,
    paper_simulation: PaperSimulationSnapshot | None = None,
) -> PilotPaperWorkflowSummary:
    """Link selected recommendation preview rows to notional paper simulation rows."""

    simulation = paper_simulation or simulate_recommendation_preview_fills(preview)
    fill_queue = _fill_queue(simulation.fills)
    rows = [_workflow_row(row, fill_queue) for row in preview.rows]
    unmatched_fills = [fill for fills in fill_queue.values() for fill in fills]
    warnings = _summary_warnings(preview, simulation, rows, unmatched_fills)
    workflow_status, expected_status, next_action = _summary_status(rows)
    return PilotPaperWorkflowSummary(
        generated_at_utc=require_utc(now_utc()),
        workflow_status=workflow_status,
        expected_vs_simulated_status=expected_status,
        selected_count=preview.selected_count,
        preview_eligible_count=preview.eligible_count,
        simulated_fill_count=simulation.fill_count,
        preview_source_hash=simulation.source_batch_hash,
        simulation_hash=simulation.simulation_hash,
        preview=preview,
        paper_simulation=simulation,
        rows=rows,
        warnings=warnings,
        next_action=next_action,
    )


def _workflow_row(
    preview_row: RecommendationPreviewRow,
    fill_queue: dict[tuple[str, str], list[PaperFillPreview]],
) -> PilotPaperWorkflowRow:
    expected_notional = _money(Decimal(str(preview_row.estimated_notional_gbp)))
    expected_fees = _money(Decimal(str(preview_row.estimated_total_cost_gbp)))
    expected_paper = preview_row.eligible and preview_row.side != "HOLD" and expected_notional > 0
    if not expected_paper:
        return _not_expected_row(preview_row, expected_notional, expected_fees)

    fill = _pop_fill(fill_queue, preview_row.research_symbol, preview_row.side)
    if fill is None:
        return PilotPaperWorkflowRow(
            symbol=preview_row.symbol,
            research_symbol=preview_row.research_symbol,
            broker_ticker=preview_row.broker_ticker,
            side=preview_row.side,
            preview_eligible=preview_row.eligible,
            expected_notional_gbp=expected_notional,
            expected_fees_gbp=expected_fees,
            simulated_status="missing",
            expected_vs_simulated_status="missing_simulation",
            blockers=list(preview_row.blockers),
            warnings=[
                (
                    "Expected a paper simulation row for this eligible preview row, "
                    "but none was produced."
                )
            ],
            next_action=(
                "Regenerate the preview and paper workflow before using this as pilot evidence."
            ),
        )

    simulated_notional = _money(fill.notional)
    simulated_fees = _money(fill.estimated_fees)
    matched = simulated_notional == expected_notional and simulated_fees == expected_fees
    warnings = [] if matched else [_mismatch_warning(expected_notional, simulated_notional)]
    return PilotPaperWorkflowRow(
        symbol=preview_row.symbol,
        research_symbol=preview_row.research_symbol,
        broker_ticker=preview_row.broker_ticker,
        side=preview_row.side,
        preview_eligible=preview_row.eligible,
        expected_notional_gbp=expected_notional,
        expected_fees_gbp=expected_fees,
        simulated_status=fill.status,
        simulated_notional_gbp=simulated_notional,
        simulated_fees_gbp=simulated_fees,
        expected_vs_simulated_status="matched" if matched else "mismatched",
        blockers=list(preview_row.blockers),
        warnings=warnings,
        next_action=(
            "Review this simulated paper row and record pilot evidence manually."
            if matched
            else "Inspect the preview and simulated paper assumptions before proceeding."
        ),
    )


def _not_expected_row(
    preview_row: RecommendationPreviewRow,
    expected_notional: Decimal,
    expected_fees: Decimal,
) -> PilotPaperWorkflowRow:
    if not preview_row.eligible:
        blockers = list(preview_row.blockers)
        return PilotPaperWorkflowRow(
            symbol=preview_row.symbol,
            research_symbol=preview_row.research_symbol,
            broker_ticker=preview_row.broker_ticker,
            side=preview_row.side,
            preview_eligible=False,
            expected_notional_gbp=expected_notional,
            expected_fees_gbp=expected_fees,
            simulated_status="not_expected",
            expected_vs_simulated_status="preview_blocked",
            blockers=blockers,
            warnings=list(preview_row.warnings),
            next_action=_blocked_next_action(blockers),
        )
    return PilotPaperWorkflowRow(
        symbol=preview_row.symbol,
        research_symbol=preview_row.research_symbol,
        broker_ticker=preview_row.broker_ticker,
        side=preview_row.side,
        preview_eligible=True,
        expected_notional_gbp=expected_notional,
        expected_fees_gbp=expected_fees,
        simulated_status="not_expected",
        expected_vs_simulated_status="no_paper_action_expected",
        blockers=list(preview_row.blockers),
        warnings=list(preview_row.warnings),
        next_action="No paper action is expected for this selected row.",
    )


def _summary_status(
    rows: list[PilotPaperWorkflowRow],
) -> tuple[str, str, str]:
    statuses = {row.expected_vs_simulated_status for row in rows}
    if "mismatched" in statuses:
        return (
            "needs_attention",
            "mismatched",
            "Inspect the preview and paper simulation mismatch before recording pilot evidence.",
        )
    if "missing_simulation" in statuses:
        return (
            "needs_attention",
            "missing_simulation",
            "Regenerate the preview and paper workflow before recording pilot evidence.",
        )
    if "matched" in statuses:
        return (
            "ready_for_operator_review",
            "all_expected_rows_simulated",
            (
                "Review the paper snapshot, note that it is not persisted or reconciled, "
                "and record the pilot evidence manually."
            ),
        )
    if "preview_blocked" in statuses:
        return (
            "blocked_before_paper",
            "no_expected_paper_rows",
            "Resolve preview blockers, refresh recommendations, then rebuild the pilot workflow.",
        )
    return (
        "no_paper_action",
        "no_expected_paper_rows",
        "No paper action is required for the selected rows.",
    )


def _summary_warnings(
    preview: RecommendationPreviewResponse,
    simulation: PaperSimulationSnapshot,
    rows: list[PilotPaperWorkflowRow],
    unmatched_fills: list[PaperFillPreview],
) -> list[str]:
    warnings = [
        (
            "Pilot paper workflow shell is preview-only: selected preview rows and "
            "simulated fills are not persisted or reconciled."
        ),
        "Live broker submission remains outside this workflow.",
        *preview.warnings,
        *simulation.warnings,
    ]
    blocked_rows = [
        row.research_symbol for row in rows if row.expected_vs_simulated_status == "preview_blocked"
    ]
    if blocked_rows:
        warnings.append(
            f"Some selected rows are blocked before paper simulation: {', '.join(blocked_rows)}."
        )
    if unmatched_fills:
        symbols = ", ".join(fill.symbol for fill in unmatched_fills)
        warnings.append(
            "Paper simulation returned fill rows without matching selected preview rows: "
            f"{symbols}."
        )
    return _dedupe(warnings)


def _fill_queue(fills: list[PaperFillPreview]) -> dict[tuple[str, str], list[PaperFillPreview]]:
    queue: dict[tuple[str, str], list[PaperFillPreview]] = defaultdict(list)
    for fill in fills:
        queue[_fill_key(fill.symbol, fill.side)].append(fill)
    return queue


def _pop_fill(
    fill_queue: dict[tuple[str, str], list[PaperFillPreview]],
    symbol: str,
    side: str,
) -> PaperFillPreview | None:
    fills = fill_queue.get(_fill_key(symbol, side))
    if not fills:
        return None
    return fills.pop(0)


def _fill_key(symbol: str, side: str) -> tuple[str, str]:
    return symbol.upper(), side.upper()


def _blocked_next_action(blockers: list[str]) -> str:
    if blockers:
        return f"Resolve preview blockers ({', '.join(blockers)}) before paper simulation."
    return "Refresh recommendation hand-off evidence before paper simulation."


def _mismatch_warning(expected_notional: Decimal, simulated_notional: Decimal) -> str:
    return (
        "Expected preview notional does not match simulated paper notional "
        f"(expected GBP {expected_notional}, simulated GBP {simulated_notional})."
    )


def _dedupe(warnings: list[str]) -> list[str]:
    return list(dict.fromkeys(warning for warning in warnings if warning))


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
