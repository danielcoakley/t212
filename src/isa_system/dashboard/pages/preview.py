"""Preview-only sizing page for eligible recommendations."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from isa_system.dashboard.data import broker_snapshot, recommendation_workflow
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
    cols = st.columns(4)
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
    st.dataframe(
        pd.DataFrame([row.model_dump(mode="json") for row in workflow.rows]),
        width="stretch",
        hide_index=True,
    )
    st.info(workflow.next_action)
    with st.expander("Paper simulation snapshot", expanded=False):
        st.json(workflow.paper_simulation.model_dump(mode="json"))
    for warning in workflow.warnings:
        st.warning(warning)


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


if __name__ == "__main__":
    render()
