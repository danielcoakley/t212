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
    advanced,
    overview,
    preview,
    recommendations,
    research_review,
    screener,
)
from isa_system.utils.time import to_london


def _parse_candidates(raw_value: str) -> tuple[str, ...]:
    """Parse comma/newline separated symbols from the sidebar scope control."""

    return tuple(
        item.strip()
        for chunk in raw_value.splitlines()
        for item in chunk.split(",")
        if item.strip()
    )


def main() -> None:
    """Render the starter dashboard."""

    st.set_page_config(page_title="ISA System", layout="wide")
    window = cache_window()
    snapshot = broker_snapshot()
    london_now = to_london(datetime.now(tz=UTC))
    opened = to_london(window.opened_at_utc)
    next_refresh = to_london(window.next_refresh_at_utc)
    with st.sidebar:
        st.title("ISA System")
        page = st.radio(
            "Workflow",
            ["Overview", "Screener", "Recommendations", "Deep Research", "Preview", "Advanced"],
            index=0,
        )
        st.divider()
        st.subheader("Screening Scope")
        raw_candidates = st.text_area(
            "Manual symbols",
            value="",
            help="Optional comma or newline separated symbols, for example VOD.L, GSK.L, NVDA.",
        )
        candidates = _parse_candidates(raw_candidates)
        include_defaults = st.checkbox("Use Trading 212 universe scan", value=True)
        include_llm = st.checkbox(
            "Attach short LLM rationale",
            value=False,
            help="The deep research gate remains separate and is only run from Deep Research.",
        )
        if st.button("Refresh market data now", type="primary"):
            with st.status("Refreshing dashboard cache...", expanded=True) as status:
                st.write("Clearing broker, instrument, valuation, and recommendation caches.")
                snapshot = refresh_market_data()
                st.write("Rebuilding the recommendation workflow cache for this scope.")
                recommendation_workflow(
                    snapshot,
                    candidates=candidates,
                    include_defaults=include_defaults,
                    include_llm=include_llm,
                )
                status.update(label="Dashboard cache refreshed.", state="complete", expanded=False)
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
        st.caption("Advanced diagnostics are available from the Advanced page.")

    if page == "Overview":
        overview.render(snapshot)
    elif page == "Screener":
        screener.render(
            snapshot,
            candidates=candidates,
            include_defaults=include_defaults,
            include_llm=include_llm,
        )
    elif page == "Recommendations":
        recommendations.render(
            snapshot,
            candidates=candidates,
            include_defaults=include_defaults,
            include_llm=include_llm,
        )
    elif page == "Deep Research":
        research_review.render(
            snapshot,
            candidates=candidates,
            include_defaults=include_defaults,
            include_llm=include_llm,
        )
    elif page == "Preview":
        preview.render(
            snapshot,
            candidates=candidates,
            include_defaults=include_defaults,
            include_llm=include_llm,
        )
    else:
        advanced.render(snapshot)


if __name__ == "__main__":
    main()
