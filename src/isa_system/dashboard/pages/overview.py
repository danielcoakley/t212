"""Portfolio overview dashboard page."""

from __future__ import annotations

import streamlit as st

from isa_system.dashboard.data import broker_snapshot
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot


def render(snapshot: BrokerPortfolioSnapshot | None = None) -> None:
    """Render overview metrics."""

    snapshot = snapshot or broker_snapshot()
    st.title("Portfolio Overview")
    cols = st.columns(4)
    cols[0].metric("Broker status", snapshot.status)
    cols[1].metric("Total value", _money(snapshot.total_value, snapshot.account_currency))
    cols[2].metric(
        "Available cash",
        _money(snapshot.available_to_trade, snapshot.account_currency),
    )
    cols[3].metric("Open positions", str(len(snapshot.positions)))
    sleeve_cols = st.columns(4)
    sleeve_cols[0].metric("Algo sleeve", "20%")
    sleeve_cols[1].metric("Core sleeve", "80%")
    sleeve_cols[2].metric("Cash buffer", "3%")
    sleeve_cols[3].metric("Execution", "Read-only live data")
    if snapshot.warnings:
        for warning in snapshot.warnings:
            st.warning(warning)
    elif snapshot.status in {"live", "demo"}:
        st.success("Trading 212 portfolio state loaded through read-only API calls.")


def _money(value: float | None, currency: str | None) -> str:
    """Format optional money values for display."""

    if value is None:
        return "n/a"
    return f"{currency or ''} {value:,.2f}".strip()


if __name__ == "__main__":
    render()
