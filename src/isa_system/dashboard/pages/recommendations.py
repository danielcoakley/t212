"""Review-only recommendation dashboard page."""

from __future__ import annotations

import streamlit as st

from isa_system.dashboard.data import broker_snapshot, recommendations
from isa_system.dashboard.recommendation_charts import (
    handoff_frame,
    instrument_validation_frame,
    recommendation_frame,
    render_action_chart,
    render_component_heatmap,
    render_handoff_chart,
    render_handoff_summary,
    render_handoff_table,
    render_instrument_validation_summary,
    render_instrument_validation_table,
    render_recommendation_summary,
    render_recommendation_table,
)
from isa_system.services.instrument_validation import validate_recommendation_instruments
from isa_system.services.market_scan import load_market_scan_universe
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot
from isa_system.services.recommendation_handoff import build_recommendation_handoff


def render(snapshot: BrokerPortfolioSnapshot | None = None) -> None:
    """Render holdings and market-scan recommendations."""

    snapshot = snapshot or broker_snapshot()
    scan_universe = load_market_scan_universe()
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
        include_defaults = st.checkbox("Include configured wider-market scan", value=True)
        include_llm = st.checkbox("Use optional OpenAI rationale", value=False)
        st.caption(f"Configured scan: {scan_universe.name} ({len(scan_universe.symbols)} symbols).")

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
    instrument_validation = validate_recommendation_instruments(response)
    instrument_rows = instrument_validation_frame(instrument_validation)
    handoff = build_recommendation_handoff(response, instrument_validation=instrument_validation)
    handoff_rows = handoff_frame(handoff)

    render_recommendation_summary(response, frame)

    st.subheader("Configured Scan Universe")
    st.caption(
        "This is the current wider-market scan seed. Symbols are discovery candidates only "
        "until broker, ISA, liquidity, and official-source validation pass."
    )
    st.dataframe(
        [
            {"symbol": symbol, "source": scan_universe.source_path}
            for symbol in scan_universe.symbols
        ],
        width="stretch",
        hide_index=True,
        column_config={
            "symbol": st.column_config.TextColumn("Symbol"),
            "source": st.column_config.TextColumn("Config source"),
        },
    )
    for warning in scan_universe.warnings:
        st.warning(warning)

    st.subheader("Action Queue")
    render_action_chart(frame)

    st.subheader("Component Score Heatmap")
    render_component_heatmap(frame)

    st.subheader("Recommendation Table")
    render_recommendation_table(frame)

    st.subheader("Rebalance Hand-off")
    st.caption(
        "Rows can only move toward preview after human review. Market-scan buys remain held "
        "for broker instrument, ISA eligibility, liquidity, and official-source validation."
    )
    render_handoff_summary(handoff, handoff_rows)
    render_handoff_chart(handoff_rows)
    render_handoff_table(handoff_rows)

    st.subheader("Broker Instrument Validation")
    st.caption(
        "Trading 212 instrument metadata is used as read-only broker validation. "
        "A match helps symbol mapping but still needs ISA, liquidity, official-source, "
        "and operator review before preview sizing."
    )
    render_instrument_validation_summary(instrument_validation, instrument_rows)
    render_instrument_validation_table(instrument_rows)

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
