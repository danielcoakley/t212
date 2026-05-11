"""Tests for the schema-light pilot paper workflow shell."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from isa_system.services.pilot_workflow import build_pilot_paper_workflow
from isa_system.services.recommendation_preview import (
    RecommendationPreviewResponse,
    RecommendationPreviewRow,
)


def test_pilot_workflow_links_preview_rows_to_simulated_paper_snapshot() -> None:
    """Eligible preview rows are matched to notional paper simulation rows."""

    workflow = build_pilot_paper_workflow(
        _preview(
            [
                RecommendationPreviewRow(
                    symbol="GOOD.L",
                    research_symbol="GOOD.L",
                    broker_ticker="GOOD_GB_EQ",
                    side="BUY",
                    eligible=True,
                    target_weight=0.04,
                    estimated_notional_gbp=400.0,
                    estimated_total_cost_gbp=2.5,
                    research_review_status="RESEARCH_PASSED",
                    rationale="Preview-ready.",
                )
            ]
        )
    )

    assert workflow.mode == "preview"
    assert workflow.workflow_status == "ready_for_operator_review"
    assert workflow.expected_vs_simulated_status == "all_expected_rows_simulated"
    assert workflow.persistence_status == "not_persisted"
    assert workflow.reconciliation_status == "not_available"
    assert workflow.paper_simulation.source_kind == "recommendation_preview"
    assert workflow.paper_simulation.fill_count == 1
    assert workflow.rows[0].expected_vs_simulated_status == "matched"
    assert workflow.rows[0].expected_notional_gbp == Decimal("400.00")
    assert workflow.rows[0].simulated_notional_gbp == Decimal("400.00")
    assert any("not persisted or reconciled" in warning for warning in workflow.warnings)
    assert "manually" in workflow.next_action


def test_pilot_workflow_keeps_blocked_preview_rows_out_of_paper() -> None:
    """Blocked selected rows remain visible and do not create simulated fills."""

    workflow = build_pilot_paper_workflow(
        _preview(
            [
                RecommendationPreviewRow(
                    symbol="WAIT.L",
                    research_symbol="WAIT.L",
                    side="HOLD",
                    eligible=False,
                    target_weight=0.0,
                    estimated_notional_gbp=0.0,
                    estimated_total_cost_gbp=0.0,
                    blockers=["DEEP_RESEARCH_REQUIRED"],
                    warnings=["Selected row is not eligible for preview sizing."],
                    rationale="Blocked.",
                )
            ],
            eligible_count=0,
        )
    )

    assert workflow.workflow_status == "blocked_before_paper"
    assert workflow.expected_vs_simulated_status == "no_expected_paper_rows"
    assert workflow.paper_simulation.fill_count == 0
    assert workflow.rows[0].expected_vs_simulated_status == "preview_blocked"
    assert workflow.rows[0].simulated_status == "not_expected"
    assert workflow.rows[0].blockers == ["DEEP_RESEARCH_REQUIRED"]
    assert "Resolve preview blockers" in workflow.next_action


def _preview(
    rows: list[RecommendationPreviewRow],
    *,
    eligible_count: int | None = None,
) -> RecommendationPreviewResponse:
    return RecommendationPreviewResponse(
        generated_at_utc=datetime(2026, 5, 11, tzinfo=UTC),
        total_equity_gbp=10_000,
        selected_count=len(rows),
        eligible_count=eligible_count if eligible_count is not None else len(rows),
        estimated_total_cost_gbp=sum(row.estimated_total_cost_gbp for row in rows),
        rows=rows,
    )
