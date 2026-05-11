"""Streamlit operator dashboard."""

from __future__ import annotations

from datetime import UTC, datetime

import streamlit as st

from isa_system.dashboard.data import (
    broker_snapshot,
    cache_window,
    recommendation_workflow,
    refresh_market_data,
)
from isa_system.dashboard.pages import (
    overview,
    recommendations,
    research_review,
)
from isa_system.utils.time import to_london


def main() -> None:
    """Render the starter dashboard."""

    st.set_page_config(page_title="ISA System", layout="wide")
    window = cache_window()
    snapshot = broker_snapshot()
    if st.sidebar.button("Refresh market data now", type="primary"):
        with st.sidebar.status("Refreshing dashboard cache...", expanded=True) as status:
            st.write("Clearing broker, instrument, valuation, and recommendation caches.")
            snapshot = refresh_market_data()
            st.write("Rebuilding the default recommendation workflow cache.")
            recommendation_workflow(snapshot, include_defaults=True, include_llm=False)
            status.update(label="Dashboard cache refreshed.", state="complete", expanded=False)
    london_now = to_london(datetime.now(tz=UTC))
    opened = to_london(window.opened_at_utc)
    next_refresh = to_london(window.next_refresh_at_utc)
    with st.sidebar:
        st.title("ISA System")
        page = st.radio(
            "Workflow",
            ["Overview", "Recommendations", "Research Review"],
            index=0,
        )
        st.divider()
        st.metric("Mode", "Preview only")
        st.metric("Broker", snapshot.status)
        st.metric("Environment", snapshot.environment)
        st.metric("Kill switch", "Clear")
        st.caption(f"Cache: {window.label} ({opened:%Y-%m-%d %H:%M %Z})")
        st.caption(f"Next scheduled refresh: {next_refresh:%Y-%m-%d %H:%M %Z}")
        st.caption(f"London time: {london_now:%Y-%m-%d %H:%M:%S %Z}")
        st.info(window.manual_refresh_hint)
        for warning in snapshot.warnings:
            st.warning(warning)
        with st.expander("Advanced diagnostics"):
            st.caption(
                "Holdings, valuation, catalyst, rebalance, factor, and audit diagnostics are "
                "kept as support modules. The MVP front door is the three-step review workflow."
            )

    if page == "Overview":
        overview.render(snapshot)
    elif page == "Recommendations":
        recommendations.render(snapshot)
    else:
        research_review.render(snapshot)


if __name__ == "__main__":
    main()
