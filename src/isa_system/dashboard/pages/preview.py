"""Preview-only sizing page for eligible recommendations."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pandas as pd
import streamlit as st

from isa_system.dashboard.data import broker_snapshot, recommendation_workflow
from isa_system.services.paper_persistence import PersistedPaperCycle, load_paper_cycle
from isa_system.services.pilot_workflow import (
    PilotPaperWorkflowSummary,
    build_pilot_paper_workflow,
)
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot
from isa_system.services.recommendation_preview import (
    RecommendationPreviewResponse,
    build_preview_from_recommendation_handoff,
)
from isa_system.utils.time import to_london


def render(
    snapshot: BrokerPortfolioSnapshot | None = None,
    *,
    candidates: tuple[str, ...] = (),
    include_defaults: bool = True,
    include_llm: bool = False,
) -> None:
    """Render preview-only recommendation sizing."""

    snapshot = snapshot or broker_snapshot()
    st.title("Preview")
    st.caption(
        "Preview converts selected, eligible recommendations into sizing context only. "
        "It estimates target weight, notional, and costs without submitting orders."
    )

    progress = st.progress(0, text="Loading preview eligibility.")
    with st.status("Preparing preview hand-off...", expanded=True) as status:
        st.write("Loading the cached recommendation hand-off and research gate status.")
        progress.progress(30, text="Loading broker validation and recommendation gates.")
        try:
            workflow = recommendation_workflow(
                snapshot,
                candidates=candidates,
                include_defaults=include_defaults,
                include_llm=include_llm,
            )
        except Exception as exc:
            progress.progress(100, text="Preview hand-off failed to load.")
            status.update(label="Preview hand-off failed.", state="error")
            st.error(
                "Preview eligibility could not be prepared. Refresh market data from the "
                "sidebar and retry."
            )
            with st.expander("Technical detail"):
                st.exception(exc)
            return
        progress.progress(75, text="Checking eligible recommendation rows.")
        handoff = workflow.handoff
        cache_time = to_london(workflow.cache_window.opened_at_utc)
        st.write(
            f"Using {workflow.cache_window.label.lower()} from {cache_time:%Y-%m-%d %H:%M %Z}."
        )
        st.write(f"Recommendation bundle source: {workflow.cache_source}.")
        progress.progress(100, text="Preview hand-off ready.")
        status.update(label="Preview hand-off ready.", state="complete", expanded=False)

    eligible = [row for row in handoff.rows if row.eligible_for_preview]
    blocked = [row for row in handoff.rows if not row.eligible_for_preview]
    cols = st.columns(4)
    cols[0].metric("Eligible rows", str(len(eligible)))
    cols[1].metric("Needs review", str(handoff.review_required_count))
    cols[2].metric("Blocked", str(handoff.blocked_count))
    cols[3].metric("Mode", "Preview only")

    if not eligible:
        st.info(
            "No rows are eligible for preview sizing yet. BUY/add ideas need a "
            "non-expired RESEARCH_PASSED review; blocked rows need their listed blockers "
            "resolved first."
        )
    else:
        frame = _handoff_rows_frame(eligible)
        st.subheader("Eligible Recommendations")
        st.dataframe(frame, width="stretch", hide_index=True, column_config=_handoff_config())
        selected = st.multiselect(
            "Select rows for preview-only sizing",
            options=[row.research_symbol for row in eligible],
            default=[row.research_symbol for row in eligible[: min(3, len(eligible))]],
        )
        if st.button("Build preview-only sizing", disabled=not selected):
            preview = build_preview_from_recommendation_handoff(
                selected_symbols=selected,
                snapshot=snapshot,
                handoff=handoff,
            )
            _render_preview(preview)

    with st.expander("Rows not eligible yet", expanded=False):
        blocked_frame = _handoff_rows_frame(blocked)
        if blocked_frame.empty:
            st.success("No blocked or review-required rows in the current hand-off.")
        else:
            st.dataframe(
                blocked_frame,
                width="stretch",
                hide_index=True,
                column_config=_handoff_config(),
            )

    for warning in dict.fromkeys(handoff.warnings):
        st.warning(warning)

    _render_saved_paper_cycle_review()


def _render_preview(preview: RecommendationPreviewResponse) -> None:
    st.success("Preview-only sizing generated. No orders were submitted.")
    generated = to_london(preview.generated_at_utc)
    cols = st.columns(4)
    cols[0].metric("Selected", str(preview.selected_count))
    cols[1].metric("Eligible", str(preview.eligible_count))
    cols[2].metric("Estimated cost", f"GBP {preview.estimated_total_cost_gbp:,.2f}")
    cols[3].metric("Generated", f"{generated:%H:%M %Z}")
    st.dataframe(
        pd.DataFrame([row.model_dump(mode="json") for row in preview.rows]),
        width="stretch",
        hide_index=True,
    )
    for warning in preview.warnings:
        st.warning(warning)
    _render_pilot_workflow(build_pilot_paper_workflow(preview))


def _render_pilot_workflow(workflow: PilotPaperWorkflowSummary) -> None:
    st.subheader("Pilot Paper Workflow")
    cols = st.columns(5)
    cols[0].metric(
        "Expected vs simulated",
        _label(workflow.expected_vs_simulated_status),
    )
    cols[1].metric("Simulated fills", str(workflow.simulated_fill_count))
    cols[2].metric(
        "Paper notional",
        f"GBP {workflow.paper_simulation.estimated_notional:,.2f}",
    )
    cols[3].metric("Persistence", _label(workflow.persistence_status))
    cols[4].metric("Reconciliation", _reconciliation_label(workflow.reconciliation_status))
    st.dataframe(
        pd.DataFrame([row.model_dump(mode="json") for row in workflow.rows]),
        width="stretch",
        hide_index=True,
    )
    st.info(workflow.next_action)
    if workflow.persistence_status == "not_persisted":
        st.info(
            "This paper workflow is not saved yet. To create reloadable evidence, call "
            "`POST /rebalances/from-recommendations/paper-cycle` with the same selected "
            "symbols, then paste the returned cycle ID below or reload it via "
            "`GET /rebalances/paper-cycles/{cycle_id}`."
        )
    with st.expander("Paper simulation snapshot", expanded=False):
        st.json(workflow.paper_simulation.model_dump(mode="json"))
    for warning in workflow.warnings:
        st.warning(warning)


def _render_saved_paper_cycle_review() -> None:
    st.subheader("Saved Paper Cycle Evidence")
    st.caption(
        "Reload persisted paper evidence for operator review. Saved cycles remain "
        "preview evidence only and do not grant order authority."
    )
    cycle_id = st.text_input(
        "Paper cycle ID",
        placeholder="paper-cycle-...",
        help="Use the cycle ID returned by the paper-cycle save endpoint.",
    ).strip()
    if not cycle_id:
        st.info(
            "No saved paper cycle is loaded. Save evidence with "
            "`POST /rebalances/from-recommendations/paper-cycle`, then paste the returned "
            "cycle ID here. The same cycle can be reloaded through "
            "`GET /rebalances/paper-cycles/{cycle_id}`."
        )
        return

    try:
        cycle = load_paper_cycle(cycle_id)
    except Exception as exc:
        st.error("Saved paper-cycle evidence could not be loaded from local persistence.")
        with st.expander("Technical detail"):
            st.exception(exc)
        return

    if cycle is None:
        st.warning(f"No saved paper cycle was found for `{cycle_id}`.")
        return

    _render_persisted_paper_cycle(cycle)


def _render_persisted_paper_cycle(cycle: PersistedPaperCycle) -> None:
    summary = _paper_cycle_summary(cycle)
    st.markdown(f"**Cycle ID:** `{summary['cycle_id']}`")

    status_cols = st.columns(4)
    status_cols[0].metric("Persistence", summary["persistence_status"])
    status_cols[1].metric("Reconciliation", summary["reconciliation_status"])
    status_cols[2].metric("Workflow", summary["workflow_status"])
    status_cols[3].metric("Expected vs simulated", summary["expected_vs_simulated_status"])

    count_cols = st.columns(3)
    count_cols[0].metric("Selected", str(summary["selected_count"]))
    count_cols[1].metric("Eligible", str(summary["preview_eligible_count"]))
    count_cols[2].metric("Simulated fills", str(summary["simulated_fill_count"]))

    total_cols = st.columns(3)
    total_cols[0].metric("Expected notional", summary["total_expected_notional"])
    total_cols[1].metric("Simulated notional", summary["total_simulated_notional"])
    total_cols[2].metric("Simulated fees", summary["total_simulated_fees"])

    st.caption(
        f"Generated {summary['generated_at_london']} and persisted "
        f"{summary['persisted_at_london']}."
    )
    if cycle.reconciliation_status == "not_available":
        st.warning(
            "Reconciliation status is unreconciled. Compare this saved paper evidence with "
            "broker evidence before any live-readiness review."
        )

    intent_frame = _paper_cycle_intents_frame(cycle)
    with st.expander("Saved paper intents", expanded=True):
        if intent_frame.empty:
            st.info("No saved paper intents are attached to this cycle.")
        else:
            st.dataframe(intent_frame, width="stretch", hide_index=True)

    fill_frame = _paper_cycle_fills_frame(cycle)
    with st.expander("Saved simulated fills", expanded=True):
        if fill_frame.empty:
            st.info("No simulated fills are attached to this cycle.")
        else:
            st.dataframe(fill_frame, width="stretch", hide_index=True)

    if cycle.warnings:
        for warning in dict.fromkeys(cycle.warnings):
            st.warning(warning)
    else:
        st.info("No saved paper-cycle warnings were recorded.")


def _paper_cycle_summary(cycle: PersistedPaperCycle) -> dict[str, Any]:
    generated = to_london(cycle.generated_at_utc)
    persisted = to_london(cycle.persisted_at_utc)
    return {
        "cycle_id": cycle.id,
        "persistence_status": _label(cycle.persistence_status),
        "reconciliation_status": _reconciliation_label(cycle.reconciliation_status),
        "workflow_status": _label(cycle.workflow_status),
        "expected_vs_simulated_status": _label(cycle.expected_vs_simulated_status),
        "selected_count": cycle.selected_count,
        "preview_eligible_count": cycle.preview_eligible_count,
        "simulated_fill_count": cycle.simulated_fill_count,
        "total_expected_notional": _money(cycle.total_expected_notional_gbp),
        "total_simulated_notional": _money(cycle.total_simulated_notional_gbp),
        "total_simulated_fees": _money(cycle.total_simulated_fees_gbp),
        "generated_at_london": f"{generated:%Y-%m-%d %H:%M %Z}",
        "persisted_at_london": f"{persisted:%Y-%m-%d %H:%M %Z}",
        "warnings": list(cycle.warnings),
    }


_PAPER_INTENT_COLUMNS = [
    "row_index",
    "research_symbol",
    "broker_ticker",
    "side",
    "preview_eligible",
    "target_weight",
    "expected_notional_gbp",
    "expected_fees_gbp",
    "simulated_status",
    "expected_vs_simulated_status",
    "research_review_status",
    "blockers",
    "warnings",
    "next_action",
]


def _paper_cycle_intents_frame(cycle: PersistedPaperCycle) -> pd.DataFrame:
    payload: list[dict[str, Any]] = []
    for intent in cycle.intents:
        values = intent.model_dump(mode="json")
        values["blockers"] = ", ".join(values.get("blockers") or [])
        values["warnings"] = ", ".join(values.get("warnings") or [])
        payload.append({column: values.get(column) for column in _PAPER_INTENT_COLUMNS})
    return pd.DataFrame(payload, columns=_PAPER_INTENT_COLUMNS)


_PAPER_FILL_COLUMNS = [
    "simulated_fill_index",
    "symbol",
    "side",
    "status",
    "notional_gbp",
    "estimated_fees_gbp",
    "quantity",
    "fill_price_account",
    "notional_source_kind",
    "quantity_source_kind",
    "fill_price_source_kind",
    "paper_intent_id",
    "note",
]


def _paper_cycle_fills_frame(cycle: PersistedPaperCycle) -> pd.DataFrame:
    payload: list[dict[str, Any]] = []
    for fill in cycle.simulated_fills:
        values = fill.model_dump(mode="json")
        payload.append({column: values.get(column) for column in _PAPER_FILL_COLUMNS})
    return pd.DataFrame(payload, columns=_PAPER_FILL_COLUMNS)


def _handoff_rows_frame(rows: list[Any]) -> pd.DataFrame:
    payload: list[dict[str, Any]] = []
    for row in rows:
        values = row.model_dump(mode="json")
        values["blockers"] = ", ".join(values.get("blockers") or [])
        payload.append(values)
    return pd.DataFrame(payload)


def _handoff_config() -> dict[str, Any]:
    return {
        "research_symbol": st.column_config.TextColumn("Symbol"),
        "source": st.column_config.TextColumn("Source"),
        "recommendation_action": st.column_config.TextColumn("Recommendation"),
        "proposed_preview_action": st.column_config.TextColumn("Preview side"),
        "handoff_status": st.column_config.TextColumn("Status"),
        "composite_score": st.column_config.NumberColumn("Composite", format="%.2f"),
        "broker_ticker": st.column_config.TextColumn("T212 ticker"),
        "research_review_status": st.column_config.TextColumn("Research gate"),
        "eligible_for_preview": st.column_config.CheckboxColumn("Eligible"),
        "blockers": st.column_config.TextColumn("Blockers"),
        "next_step": st.column_config.TextColumn("Next step"),
    }


def _label(value: str) -> str:
    return value.replace("_", " ").title()


def _reconciliation_label(value: str) -> str:
    if value == "not_available":
        return "Unreconciled"
    return _label(value)


def _money(value: Decimal | float | int | str) -> str:
    return f"GBP {Decimal(str(value)):,.2f}"


if __name__ == "__main__":
    render()
