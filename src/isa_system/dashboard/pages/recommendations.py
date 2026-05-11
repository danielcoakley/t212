"""MVP recommendation queue page."""

from __future__ import annotations

import streamlit as st

from isa_system.dashboard.data import broker_snapshot, recommendation_workflow
from isa_system.dashboard.recommendation_charts import (
    consolidated_recommendation_frame,
    handoff_frame,
    instrument_validation_frame,
    recommendation_evidence_frame,
    recommendation_frame,
    render_action_chart,
    render_component_heatmap,
    render_consolidated_recommendation_table,
    render_handoff_table,
    render_instrument_validation_table,
    render_recommendation_evidence_table,
    render_recommendation_summary,
)
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot
from isa_system.services.recommendation_preview import build_preview_from_recommendation_handoff
from isa_system.utils.time import to_london


def render(snapshot: BrokerPortfolioSnapshot | None = None) -> None:
    """Render the consolidated recommendation and preview-readiness workflow."""

    snapshot = snapshot or broker_snapshot()
    st.title("Recommendations")
    st.caption(
        "One review queue for current holdings and broker-universe scan candidates. "
        "Buy/add rows need broker validation and a non-expired deep research pass before "
        "preview-only sizing."
    )

    with st.sidebar:
        st.subheader("Screener")
        raw_watchlist = st.text_area(
            "Add symbols",
            value="",
            help="Comma or newline separated research symbols, for example VOD.L, GSK.L, NVDA.",
        )
        include_defaults = st.checkbox("Use Trading 212 universe scan", value=True)
        include_llm = st.checkbox("Attach short LLM rationale", value=False)

    candidates = tuple(
        item.strip()
        for chunk in raw_watchlist.splitlines()
        for item in chunk.split(",")
        if item.strip()
    )
    progress = st.progress(0, text="Checking the current market-session cache.")
    with st.status("Preparing recommendation workflow...", expanded=True) as status:
        st.write("Checking the London/US open cache window.")
        progress.progress(20, text="Loading cached broker snapshot and scan universe.")
        try:
            workflow = recommendation_workflow(
                snapshot,
                candidates=candidates,
                include_defaults=include_defaults,
                include_llm=include_llm,
            )
        except Exception as exc:
            progress.progress(100, text="Recommendation workflow failed to load.")
            status.update(label="Recommendation workflow failed.", state="error")
            st.error(
                "The recommendation queue could not be prepared. Use the sidebar refresh "
                "button to rebuild the cache; if it keeps failing, check provider warnings."
            )
            with st.expander("Technical detail"):
                st.exception(exc)
            return
        progress.progress(65, text="Validating broker symbols and research gate status.")
        response = workflow.recommendations
        validation = workflow.instrument_validation
        handoff = workflow.handoff
        cache_time = to_london(workflow.cache_window.opened_at_utc)
        st.write(
            f"Using {workflow.cache_window.label.lower()} from {cache_time:%Y-%m-%d %H:%M %Z}."
        )
        st.write(f"Recommendation bundle source: {workflow.cache_source}.")
        st.write(
            "Broker metadata, recommendation scores, hand-off blockers, and research gate "
            "status are loaded."
        )
        progress.progress(100, text="Recommendation workflow ready.")
        status.update(label="Recommendation workflow ready.", state="complete", expanded=False)
    queue = consolidated_recommendation_frame(response, handoff, validation)

    render_recommendation_summary(response, recommendation_frame(response))
    cols = st.columns(4)
    cols[0].metric("Broker scan seed", str(len(workflow.scan_universe_symbols)))
    cols[1].metric("Broker metadata rows", str(validation.instrument_count))
    cols[2].metric("Preview eligible", str(handoff.eligible_count))
    cols[3].metric("Needs research/review", str(handoff.review_required_count))

    st.subheader("Recommendation Queue")
    render_consolidated_recommendation_table(queue)

    eligible_symbols = [row.research_symbol for row in handoff.rows if row.eligible_for_preview]
    selected = st.multiselect(
        "Preview selected eligible rows",
        options=eligible_symbols,
        help="Only rows with broker validation and required deep research pass are shown.",
    )
    if st.button("Build preview from selected rows", disabled=not selected):
        preview = build_preview_from_recommendation_handoff(
            selected_symbols=selected,
            snapshot=snapshot,
            handoff=handoff,
        )
        st.success("Preview-only sizing generated. No orders were submitted.")
        st.dataframe(
            [row.model_dump(mode="json") for row in preview.rows],
            width="stretch",
            hide_index=True,
        )
        for warning in preview.warnings:
            st.warning(warning)

    if not queue.empty:
        symbol = st.selectbox("Evidence detail", queue["research_symbol"].tolist())
        row = queue[queue["research_symbol"] == symbol].iloc[0].to_dict()
        with st.expander(f"{symbol} evidence and blockers", expanded=False):
            st.json(row)

    with st.expander("Advanced diagnostics"):
        st.caption(
            "These tables are retained for audit and debugging. They are not the primary "
            "operator workflow."
        )
        st.subheader("Score chart")
        frame = recommendation_frame(response)
        render_action_chart(frame)
        render_component_heatmap(frame)
        st.subheader("Evidence table")
        render_recommendation_evidence_table(recommendation_evidence_frame(response))
        st.subheader("Hand-off table")
        render_handoff_table(handoff_frame(handoff))
        st.subheader("Broker instrument validation")
        render_instrument_validation_table(instrument_validation_frame(validation))

    for warning in dict.fromkeys(
        [
            *workflow.scan_universe_warnings,
            *handoff.warnings,
            *validation.warnings,
        ]
    ):
        st.warning(warning)


if __name__ == "__main__":
    render()
