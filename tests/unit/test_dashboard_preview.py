"""Tests for Preview dashboard paper-cycle helper transforms."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from isa_system.dashboard.pages.preview import (
    _paper_cycle_fills_frame,
    _paper_cycle_intents_frame,
    _paper_cycle_summary,
)
from isa_system.services.paper_persistence import (
    PersistedPaperCycle,
    PersistedPaperIntent,
    PersistedPaperSimulatedFill,
)


def test_paper_cycle_summary_exposes_saved_counts_totals_and_unreconciled_status() -> None:
    """Saved paper evidence summary keeps persistence and reconciliation explicit."""

    summary = _paper_cycle_summary(_paper_cycle())

    assert summary["cycle_id"] == "paper-cycle-test"
    assert summary["persistence_status"] == "Persisted"
    assert summary["reconciliation_status"] == "Unreconciled"
    assert summary["selected_count"] == 2
    assert summary["preview_eligible_count"] == 1
    assert summary["simulated_fill_count"] == 1
    assert summary["total_expected_notional"] == "GBP 400.00"
    assert summary["total_simulated_notional"] == "GBP 400.00"
    assert summary["total_simulated_fees"] == "GBP 2.50"
    assert summary["warnings"] == ["Live broker submission remains outside this workflow."]


def test_paper_cycle_frames_flatten_intents_and_fills_for_operator_review() -> None:
    """Intent and fill frames expose evidence fields without nested lists."""

    cycle = _paper_cycle()

    intents = _paper_cycle_intents_frame(cycle)
    fills = _paper_cycle_fills_frame(cycle)

    assert list(intents["research_symbol"]) == ["GOOD.L", "WAIT.L"]
    assert list(intents["expected_vs_simulated_status"]) == ["matched", "preview_blocked"]
    assert intents.loc[1, "blockers"] == "DEEP_RESEARCH_REQUIRED"
    assert intents.loc[1, "warnings"] == "Selected row is not eligible for preview sizing."
    assert fills.loc[0, "paper_intent_id"] == "paper-intent-good"
    assert fills.loc[0, "notional_source_kind"].endswith("estimated_notional")
    assert "quantity_unavailable" in fills.loc[0, "quantity_source_kind"]
    assert "fill_price_unavailable" in fills.loc[0, "fill_price_source_kind"]


def _paper_cycle() -> PersistedPaperCycle:
    generated = datetime(2026, 5, 11, 9, 0, tzinfo=UTC)
    persisted = datetime(2026, 5, 11, 9, 5, tzinfo=UTC)
    return PersistedPaperCycle(
        id="paper-cycle-test",
        generated_at_utc=generated,
        persisted_at_utc=persisted,
        source_kind="recommendation_preview",
        workflow_status="ready_for_operator_review",
        expected_vs_simulated_status="all_expected_rows_simulated",
        selected_count=2,
        preview_eligible_count=1,
        simulated_fill_count=1,
        preview_source_hash="preview-hash",
        simulation_hash="simulation-hash",
        total_expected_notional_gbp=Decimal("400.00"),
        total_simulated_notional_gbp=Decimal("400.00"),
        total_simulated_fees_gbp=Decimal("2.50"),
        intents=[
            PersistedPaperIntent(
                id="paper-intent-good",
                paper_cycle_id="paper-cycle-test",
                row_index=0,
                symbol="GOOD.L",
                research_symbol="GOOD.L",
                broker_ticker="GOOD_GB_EQ",
                side="BUY",
                preview_eligible=True,
                target_weight=Decimal("0.04"),
                expected_notional_gbp=Decimal("400.00"),
                expected_fees_gbp=Decimal("2.50"),
                simulated_status="simulated",
                expected_vs_simulated_status="matched",
                research_review_status="RESEARCH_PASSED",
                blockers=[],
                warnings=[],
                next_action="Review this simulated paper row.",
                preview_row_hash="preview-row-good",
            ),
            PersistedPaperIntent(
                id="paper-intent-wait",
                paper_cycle_id="paper-cycle-test",
                row_index=1,
                symbol="WAIT.L",
                research_symbol="WAIT.L",
                side="HOLD",
                preview_eligible=False,
                target_weight=Decimal("0.00"),
                expected_notional_gbp=Decimal("0.00"),
                expected_fees_gbp=Decimal("0.00"),
                simulated_status="not_expected",
                expected_vs_simulated_status="preview_blocked",
                research_review_status="MISSING",
                blockers=["DEEP_RESEARCH_REQUIRED"],
                warnings=["Selected row is not eligible for preview sizing."],
                next_action="Resolve preview blockers before paper simulation.",
                preview_row_hash="preview-row-wait",
            ),
        ],
        simulated_fills=[
            PersistedPaperSimulatedFill(
                id="paper-fill-good",
                paper_cycle_id="paper-cycle-test",
                paper_intent_id="paper-intent-good",
                simulated_fill_index=0,
                symbol="GOOD.L",
                side="BUY",
                source_kind="recommendation_preview",
                status="simulated",
                quantity=None,
                fill_price_account=None,
                notional_gbp=Decimal("400.00"),
                estimated_fees_gbp=Decimal("2.50"),
                notional_source_kind="recommendation_preview.estimated_notional",
                quantity_source_kind=("recommendation_preview.notional_only_quantity_unavailable"),
                fill_price_source_kind=(
                    "recommendation_preview.notional_only_fill_price_unavailable"
                ),
                note="Notional-only simulated paper fill.",
            )
        ],
        warnings=["Live broker submission remains outside this workflow."],
    )
