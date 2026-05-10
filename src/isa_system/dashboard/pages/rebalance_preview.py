"""Rebalance preview dashboard page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from isa_system.dashboard.data import broker_snapshot
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot


def render(snapshot: BrokerPortfolioSnapshot | None = None) -> None:
    """Render preview table and warnings."""

    snapshot = snapshot or broker_snapshot()
    st.title("Rebalance Preview")
    st.error("Live submit is disabled until mode is live, armed, and kill switch is clear.")
    st.caption(f"Read-only broker status: {snapshot.status}; environment: {snapshot.environment}.")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "symbol": "TSCO.L",
                    "current": 0.02,
                    "target": 0.04,
                    "side": "BUY",
                    "estimated_cost_gbp": 1.55,
                },
                {
                    "symbol": "AAPL",
                    "current": 0.00,
                    "target": 0.05,
                    "side": "BUY",
                    "estimated_cost_gbp": 1.50,
                },
            ]
        ),
        use_container_width=True,
    )


if __name__ == "__main__":
    render()
