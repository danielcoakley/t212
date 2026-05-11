"""Tests for persisted paper workflow evidence."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from isa_system.db.session import init_db, make_engine, make_session_factory
from isa_system.services.paper_persistence import (
    load_paper_cycle,
    persist_pilot_paper_workflow,
)
from isa_system.services.pilot_workflow import build_pilot_paper_workflow
from isa_system.services.recommendation_preview import (
    RecommendationPreviewResponse,
    RecommendationPreviewRow,
)


def test_persist_pilot_workflow_saves_reloadable_intents_and_fills() -> None:
    """Paper cycles retain intent/fill linkage and source-kind evidence."""

    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    factory = make_session_factory(engine)
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
                ),
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
                ),
            ],
            eligible_count=1,
        )
    )

    with factory() as session:
        persisted = persist_pilot_paper_workflow(workflow, session=session)
        session.commit()
        reloaded = load_paper_cycle(persisted.id, session=session)
        persisted_again = persist_pilot_paper_workflow(workflow, session=session)

    assert reloaded is not None
    assert persisted.id == persisted_again.id
    assert persisted.intents[0].id == persisted_again.intents[0].id
    assert persisted.simulated_fills[0].id == persisted_again.simulated_fills[0].id
    assert reloaded.persistence_status == "persisted"
    assert reloaded.reconciliation_status == "not_available"
    assert reloaded.expected_vs_simulated_status == "all_expected_rows_simulated"
    assert [intent.expected_vs_simulated_status for intent in reloaded.intents] == [
        "matched",
        "preview_blocked",
    ]
    assert reloaded.intents[0].expected_notional_gbp == Decimal("400.00")
    assert reloaded.simulated_fills[0].paper_intent_id == reloaded.intents[0].id
    assert reloaded.simulated_fills[0].notional_gbp == Decimal("400.00")
    assert reloaded.simulated_fills[0].quantity is None
    assert reloaded.simulated_fills[0].fill_price_account is None
    assert reloaded.simulated_fills[0].notional_source_kind.endswith("estimated_notional")
    assert "quantity_unavailable" in reloaded.simulated_fills[0].quantity_source_kind
    assert "fill_price_unavailable" in reloaded.simulated_fills[0].fill_price_source_kind


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
