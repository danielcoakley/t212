"""Valuation, technical, event, and sentiment dashboard page."""

from __future__ import annotations

import streamlit as st

from isa_system.dashboard.charts import positions_frame, render_snapshot_context, render_warnings
from isa_system.dashboard.data import broker_snapshot, holdings_valuation
from isa_system.dashboard.valuation_charts import (
    render_indicator_bars,
    render_information_panel,
    render_relative_valuation,
    render_technical_heatmap,
    render_valuation_context,
    render_valuation_table,
    valuation_frame,
    valuation_warning_count,
)
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot


def render(snapshot: BrokerPortfolioSnapshot | None = None) -> None:
    """Render valuation and technical overlays for current holdings."""

    snapshot = snapshot or broker_snapshot()
    broker_frame = positions_frame(snapshot)
    valuation_snapshot = holdings_valuation(snapshot)
    frame = valuation_frame(valuation_snapshot)

    st.title("Valuation")
    st.warning(
        "Valuation and technical overlays are research context only. They do not create "
        "orders and must not override event vetoes, stale-data checks, or live arming controls."
    )
    render_snapshot_context(snapshot, broker_frame, include_broker=False)
    render_warnings(snapshot)

    st.subheader("Coverage and Freshness")
    render_valuation_context(valuation_snapshot, frame)
    st.caption(
        "Broker symbols remain the account-truth identifiers. Research symbols are separate "
        "because convenience feeds use different ticker formats, especially for UK listings."
    )

    st.subheader("Holding Valuation Table")
    render_valuation_table(frame, snapshot.account_currency)

    st.subheader("Relative Valuation and Technicals")
    chart_cols = st.columns([1, 1])
    with chart_cols[0]:
        st.caption("Available multiples from the configured convenience feed.")
        render_relative_valuation(frame)
    with chart_cols[1]:
        st.caption("RSI 14 with 30-70 context band where history is available.")
        render_indicator_bars(frame)

    st.subheader("Momentum Context")
    st.caption("Medium-term momentum windows align with the daily-bar strategy roadmap.")
    render_technical_heatmap(frame)

    st.subheader("Events, Sentiment, and News")
    st.caption(
        "Official filings, RNS/NSM validations, PDMR transactions, and short-disclosure "
        "sentiment remain roadmap items. This table exposes any provider context already "
        "available and makes missing coverage explicit."
    )
    render_information_panel(frame)

    st.subheader("Operational Notes")
    warning_count = valuation_warning_count(valuation_snapshot)
    cols = st.columns(3)
    cols[0].metric("Provider", valuation_snapshot.provider)
    cols[1].metric("Warnings", str(warning_count))
    cols[2].metric("Order path", "Blocked")


if __name__ == "__main__":
    render()
