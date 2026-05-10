"""Rebalance preview dashboard page."""

from __future__ import annotations

import streamlit as st

from isa_system.dashboard.charts import (
    portfolio_totals,
    positions_frame,
    render_cash_and_invested_chart,
    render_rebalance_hold_table,
    render_rebalance_safety_panel,
    render_snapshot_context,
    render_warnings,
)
from isa_system.dashboard.data import broker_snapshot
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot


def render(snapshot: BrokerPortfolioSnapshot | None = None) -> None:
    """Render a safe rebalance preview surface with live trading blocked."""

    snapshot = snapshot or broker_snapshot()
    frame = positions_frame(snapshot)
    totals = portfolio_totals(snapshot, frame)
    st.title("Rebalance Preview")
    st.error("Live submit is disabled. This page is a read-only preview and safety review.")
    render_snapshot_context(snapshot, frame)
    render_warnings(snapshot)

    st.subheader("Safety Gates")
    st.caption(
        "Every live order path must remain blocked until mode, arming, kill-switch, broker "
        "reconciliation, and duplicate-order checks all pass."
    )
    render_rebalance_safety_panel(snapshot)

    st.subheader("Sleeve and Cash Context")
    cols = st.columns(4)
    cols[0].metric("Configured algo sleeve", "20%")
    cols[1].metric("Configured core sleeve", "80%")
    cols[2].metric("Invested fraction", _percent(totals["invested_weight"]))
    cols[3].metric("Estimated preview costs", "0.00")
    render_cash_and_invested_chart(snapshot, frame)

    st.subheader("Current Holding Preview")
    st.caption(
        "No target-weight strategy run is selected in this dashboard view, so the safe default "
        "preview is HOLD for each current position with zero estimated transaction cost."
    )
    render_rebalance_hold_table(snapshot, frame)


def _percent(value: float | None) -> str:
    """Format an optional ratio as a percentage."""

    if value is None:
        return "n/a"
    return f"{value * 100.0:,.2f}%"


if __name__ == "__main__":
    render()
