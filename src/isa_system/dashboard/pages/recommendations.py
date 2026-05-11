"""Review-only recommendation dashboard page."""

from __future__ import annotations

import streamlit as st

from isa_system.dashboard.data import broker_snapshot, recommendations
from isa_system.dashboard.recommendation_charts import (
    recommendation_frame,
    render_action_chart,
    render_component_heatmap,
    render_recommendation_summary,
    render_recommendation_table,
)
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot


def render(snapshot: BrokerPortfolioSnapshot | None = None) -> None:
    """Render holdings and market-scan recommendations."""

    snapshot = snapshot or broker_snapshot()
    st.title("Recommendations")
    st.warning(
        "Recommendations are review-only. They cannot create orders, set targets, or override "
        "event vetoes, risk checks, duplicate-order controls, or live arming."
    )

    with st.sidebar:
        st.subheader("Recommendation scan")
        raw_watchlist = st.text_area(
            "Additional candidates",
            value="",
            help="Comma or newline separated research symbols, for example VOD.L, GSK.L, NVDA.",
        )
        include_defaults = st.checkbox("Include default wider-market scan", value=True)
        include_llm = st.checkbox("Use optional OpenAI rationale", value=False)

    candidates = tuple(
        item.strip()
        for chunk in raw_watchlist.splitlines()
        for item in chunk.split(",")
        if item.strip()
    )
    response = recommendations(
        snapshot,
        candidates=candidates,
        include_defaults=include_defaults,
        include_llm=include_llm,
    )
    frame = recommendation_frame(response)

    render_recommendation_summary(response, frame)

    st.subheader("Action Queue")
    render_action_chart(frame)

    st.subheader("Component Score Heatmap")
    render_component_heatmap(frame)

    st.subheader("Recommendation Table")
    render_recommendation_table(frame)

    st.subheader("MVP Guardrails")
    st.dataframe(
        [
            {
                "control": "Execution",
                "state": "Blocked",
                "reason": "Recommendation actions never submit orders.",
            },
            {
                "control": "Wider-market scan",
                "state": "Convenience feed",
                "reason": (
                    "Candidates are discovery context, not confirmed ISA-accessible universe."
                ),
            },
            {
                "control": "LLM rationale",
                "state": "Optional",
                "reason": (
                    "LLM text summarises evidence only and degrades when the API is unavailable."
                ),
            },
            {
                "control": "Official validation",
                "state": "Pending",
                "reason": (
                    "SEC, Companies House, RNS, NSM, and FCA short data remain authoritative "
                    "roadmap layers."
                ),
            },
        ],
        width="stretch",
        hide_index=True,
    )


if __name__ == "__main__":
    render()
