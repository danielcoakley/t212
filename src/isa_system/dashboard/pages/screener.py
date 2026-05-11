"""Explainable broad-market screener funnel page."""

from __future__ import annotations

from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

from isa_system.dashboard.data import broker_snapshot, recommendation_workflow
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot
from isa_system.services.screener_funnel import ScreenerFunnelResponse, ScreenerFunnelStage
from isa_system.utils.time import to_london


def render(
    snapshot: BrokerPortfolioSnapshot | None = None,
    *,
    candidates: tuple[str, ...] = (),
    include_defaults: bool = True,
    include_llm: bool = False,
) -> None:
    """Render the additive funnel from broker universe to deep-research shortlist."""

    snapshot = snapshot or broker_snapshot()
    st.title("Screener")
    st.caption(
        "The broad-market scan starts from the Trading 212 accessible universe where "
        "available, then applies broker validation, evidence, event, and ranking gates. "
        "Rows are review-only until they pass the deep research gate."
    )

    progress = st.progress(0, text="Loading market-session cache.")
    with st.status("Preparing screener funnel...", expanded=True) as status:
        st.write("Loading the cached broker-universe scan and recommendation workflow.")
        progress.progress(25, text="Loading broker universe and recommendation scores.")
        try:
            workflow = recommendation_workflow(
                snapshot,
                candidates=candidates,
                include_defaults=include_defaults,
                include_llm=include_llm,
            )
        except Exception as exc:
            progress.progress(100, text="Screener funnel failed to load.")
            status.update(label="Screener funnel failed.", state="error")
            st.error(
                "The screener funnel could not be prepared. Refresh market data from the "
                "sidebar; if it keeps failing, check provider warnings in Advanced."
            )
            with st.expander("Technical detail"):
                st.exception(exc)
            return
        progress.progress(70, text="Building additive filter stages.")
        funnel = workflow.screener_funnel
        cache_time = to_london(workflow.cache_window.opened_at_utc)
        st.write(
            f"Using {workflow.cache_window.label.lower()} from {cache_time:%Y-%m-%d %H:%M %Z}."
        )
        st.write(
            f"Universe source: {workflow.scan_universe_source or workflow.scan_universe_name}."
        )
        st.write(f"Recommendation bundle source: {workflow.cache_source}.")
        progress.progress(100, text="Screener funnel ready.")
        status.update(label="Screener funnel ready.", state="complete", expanded=False)

    _render_funnel_summary(funnel)
    _render_stage_chart(funnel)
    _render_final_candidates(funnel)
    _render_stage_details(funnel)

    for warning in dict.fromkeys([*workflow.scan_universe_warnings, *funnel.warnings]):
        st.warning(warning)


def _render_funnel_summary(funnel: ScreenerFunnelResponse) -> None:
    cols = st.columns(4)
    cols[0].metric("Broker scan symbols", str(funnel.universe_count))
    cols[1].metric("Scored holdings/candidates", str(funnel.scored_count))
    cols[2].metric("Unscored/removed", str(funnel.unscored_count))
    cols[3].metric("Deep research shortlist", str(len(funnel.final_candidates)))


def _render_stage_chart(funnel: ScreenerFunnelResponse) -> None:
    frame = pd.DataFrame(
        [
            {
                "stage": stage.name,
                "passed": stage.passed_count,
                "removed": stage.removed_count,
            }
            for stage in funnel.stages
        ]
    )
    if frame.empty:
        st.info("No screener stages are available.")
        return
    stage_frame = frame.melt("stage", var_name="outcome", value_name="count")
    st.altair_chart(
        alt.Chart(stage_frame)
        .mark_bar(size=22)
        .encode(
            x=alt.X("count:Q", title="Rows"),
            y=alt.Y("stage:N", sort=None, title=None),
            color=alt.Color("outcome:N", title="Outcome"),
            tooltip=[
                alt.Tooltip("stage:N", title="Stage"),
                alt.Tooltip("outcome:N", title="Outcome"),
                alt.Tooltip("count:Q", title="Rows", format=",d"),
            ],
        )
        .properties(height=max(260, 42 * len(frame))),
        width="stretch",
    )


def _render_final_candidates(funnel: ScreenerFunnelResponse) -> None:
    st.subheader("Top Candidates For Deep Research")
    frame = _rows_frame(funnel.final_candidates)
    if frame.empty:
        st.info(
            "No BUY/add or WATCH candidates currently survive all screener gates. "
            "Refresh market data or broaden the universe if this looks unexpected."
        )
        return
    st.dataframe(
        frame,
        width="stretch",
        hide_index=True,
        column_config=_row_column_config(),
    )


def _render_stage_details(funnel: ScreenerFunnelResponse) -> None:
    st.subheader("How The Funnel Arrived Here")
    for stage in funnel.stages:
        with st.expander(
            f"{stage.name}: {stage.passed_count} passed, {stage.removed_count} removed",
            expanded=stage.stage_id in {"seed", "deep_research_shortlist"},
        ):
            _render_stage(stage)


def _render_stage(stage: ScreenerFunnelStage) -> None:
    st.caption(stage.purpose)
    cols = st.columns(3)
    cols[0].metric("Starting rows", str(stage.starting_count))
    cols[1].metric("Passed", str(stage.passed_count))
    cols[2].metric("Removed", str(stage.removed_count))
    if stage.removal_reasons:
        st.write("Removal reasons")
        st.dataframe(
            pd.DataFrame(
                [
                    {"reason": reason, "rows": count}
                    for reason, count in stage.removal_reasons.items()
                ]
            ),
            width="stretch",
            hide_index=True,
        )
    passed = _rows_frame(stage.passed_rows)
    removed = _rows_frame(stage.removed_rows)
    if not passed.empty:
        st.write("Passed rows")
        st.dataframe(
            passed.head(30),
            width="stretch",
            hide_index=True,
            column_config=_row_column_config(),
        )
    if not removed.empty:
        st.write("Removed rows")
        st.dataframe(
            removed.head(30),
            width="stretch",
            hide_index=True,
            column_config=_row_column_config(),
        )


def _rows_frame(rows: list[Any]) -> pd.DataFrame:
    payload: list[dict[str, Any]] = []
    for row in rows:
        values = row.model_dump(mode="json")
        values["reasons"] = ", ".join(values.get("reasons") or [])
        payload.append(values)
    return pd.DataFrame(payload)


def _row_column_config() -> dict[str, Any]:
    return {
        "research_symbol": st.column_config.TextColumn("Symbol"),
        "source": st.column_config.TextColumn("Source"),
        "action": st.column_config.TextColumn("Action"),
        "composite_score": st.column_config.NumberColumn("Composite", format="%.2f"),
        "broker_validation_status": st.column_config.TextColumn("Broker check"),
        "broker_ticker": st.column_config.TextColumn("T212 ticker"),
        "research_review_status": st.column_config.TextColumn("Research gate"),
        "preview_eligible": st.column_config.CheckboxColumn("Preview"),
        "passed": st.column_config.CheckboxColumn("Passed"),
        "reasons": st.column_config.TextColumn("Why"),
    }


if __name__ == "__main__":
    render()
