"""Portfolio overview dashboard page."""

from __future__ import annotations

import streamlit as st

from isa_system.dashboard.charts import (
    portfolio_totals,
    positions_frame,
    render_cash_and_invested_chart,
    render_concentration_chart,
    render_currency_allocation,
    render_profit_loss_chart,
    render_snapshot_context,
    render_warnings,
)
from isa_system.dashboard.data import broker_snapshot
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot


def render(snapshot: BrokerPortfolioSnapshot | None = None) -> None:
    """Render overview metrics and visual portfolio context."""

    snapshot = snapshot or broker_snapshot()
    frame = positions_frame(snapshot)
    totals = portfolio_totals(snapshot, frame)
    st.title("Portfolio Overview")
    render_snapshot_context(snapshot, frame)
    sleeve_cols = st.columns(4)
    sleeve_cols[0].metric("Algo sleeve", "20%")
    sleeve_cols[1].metric("Core sleeve", "80%")
    sleeve_cols[2].metric("Cash weight", _percent(totals["cash_weight"]))
    sleeve_cols[3].metric("Execution", "Read-only live data")
    if snapshot.warnings:
        render_warnings(snapshot)
    elif snapshot.status in {"live", "demo"}:
        st.success("Trading 212 portfolio state loaded through read-only API calls.")
    st.subheader("Next Action")
    if snapshot.status in {"live", "demo"}:
        st.info(
            "Review the recommendation queue, run deep research for any BUY/add candidate, "
            "then generate a preview-only rebalance plan for eligible rows."
        )
    else:
        st.warning(
            "Connect Trading 212 read-only metadata before relying on live portfolio context."
        )

    st.subheader("Account Context")
    chart_cols = st.columns([1, 1])
    with chart_cols[0]:
        st.caption("Current split between invested value, available cash, and reserved cash.")
        render_cash_and_invested_chart(snapshot, frame)
    with chart_cols[1]:
        st.caption("Currency exposure from live holdings, with cash shown separately.")
        render_currency_allocation(snapshot, frame)

    st.subheader("Holding Concentration and P/L")
    risk_cols = st.columns([1, 1])
    with risk_cols[0]:
        st.caption("Largest current holdings by account weight.")
        render_concentration_chart(frame)
    with risk_cols[1]:
        st.caption("Unrealised profit/loss by holding where the broker supplies the field.")
        render_profit_loss_chart(snapshot, frame)


def _percent(value: float | None) -> str:
    """Format an optional ratio as a percentage."""

    if value is None:
        return "n/a"
    return f"{value * 100.0:,.2f}%"


if __name__ == "__main__":
    render()
