"""MVP recommendation queue page."""

from __future__ import annotations

import streamlit as st

from isa_system.dashboard.data import broker_snapshot, recommendation_workflow
from isa_system.dashboard.recommendation_charts import (
    consolidated_recommendation_frame,
    recommendation_frame,
    recommendation_source_freshness_rows,
    render_action_chart,
    render_component_heatmap,
    render_consolidated_recommendation_table,
    render_recommendation_summary,
)
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot
from isa_system.utils.time import to_london


def render(
    snapshot: BrokerPortfolioSnapshot | None = None,
    *,
    candidates: tuple[str, ...] = (),
    include_defaults: bool = True,
    include_llm: bool = False,
) -> None:
    """Render the consolidated recommendation and preview-readiness workflow."""

    snapshot = snapshot or broker_snapshot()
    st.title("Recommendations")
    st.caption(
        "One review queue for current holdings and broker-universe scan candidates. "
        "Buy/add rows need broker validation and a non-expired deep research pass before "
        "preview-only sizing."
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
    source_rows = recommendation_source_freshness_rows(
        response,
        handoff,
        validation,
        cache_window=workflow.cache_window,
        cache_source=workflow.cache_source,
    )
    queue = consolidated_recommendation_frame(
        response,
        handoff,
        validation,
        cache_window=workflow.cache_window,
        cache_source=workflow.cache_source,
    )
    score_frame = recommendation_frame(response)

    render_recommendation_summary(response, score_frame)
    cols = st.columns(5)
    cols[0].metric("Broker scan seed", str(len(workflow.scan_universe_symbols)))
    cols[1].metric("Broker metadata rows", str(validation.instrument_count))
    cols[2].metric("Preview eligible", str(handoff.eligible_count))
    cols[3].metric("Needs research/review", str(handoff.review_required_count))
    cols[4].metric("Blocked", str(handoff.blocked_count))

    st.subheader("Source Freshness")
    st.caption(
        "Freshness diagnostics show source age and provider gaps for review. "
        "They do not change scoring or approve orders."
    )
    st.dataframe(source_rows, hide_index=True, use_container_width=True)

    st.subheader("Recommendation Queue")
    st.caption(
        "Rows are review-only. Preview-ready means the row can enter sizing review; "
        "it is not order authority."
    )
    render_consolidated_recommendation_table(queue)

    st.subheader("Score Breakdown")
    render_action_chart(score_frame)
    render_component_heatmap(score_frame)

    if not queue.empty:
        symbol = st.selectbox("Evidence detail", queue["research_symbol"].tolist())
        row = queue[queue["research_symbol"] == symbol].iloc[0].to_dict()
        with st.expander(f"{symbol} evidence and blockers", expanded=False):
            st.json(row)

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
