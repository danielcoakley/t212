"""Holdings dashboard page."""

from __future__ import annotations

import streamlit as st

from isa_system.dashboard.charts import (
    positions_frame,
    render_concentration_chart,
    render_currency_allocation,
    render_holdings_table,
    render_profit_loss_chart,
    render_snapshot_context,
    render_warnings,
)
from isa_system.dashboard.data import broker_snapshot
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot


def render(snapshot: BrokerPortfolioSnapshot | None = None) -> None:
    """Render holdings analytics and the live broker holdings table."""

    snapshot = snapshot or broker_snapshot()
    frame = positions_frame(snapshot)
    st.title("Holdings")
    render_snapshot_context(snapshot, frame, include_broker=False)
    render_warnings(snapshot)

    st.subheader("Live Position Table")
    st.caption(
        "Values are normalised from Trading 212 read-only position data. Missing broker fields "
        "are left as n/a rather than inferred beyond simple price x quantity fallbacks."
    )
    render_holdings_table(frame)

    st.subheader("Portfolio Shape")
    chart_cols = st.columns([1, 1])
    with chart_cols[0]:
        st.caption("Concentration by current account weight.")
        render_concentration_chart(frame)
    with chart_cols[1]:
        st.caption("Currency mix across live positions and available cash.")
        render_currency_allocation(snapshot, frame)

    st.subheader("Profit and Loss Context")
    render_profit_loss_chart(snapshot, frame)


if __name__ == "__main__":
    render()
