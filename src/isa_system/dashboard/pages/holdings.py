"""Holdings dashboard page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from isa_system.dashboard.data import broker_snapshot
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot


def render(snapshot: BrokerPortfolioSnapshot | None = None) -> None:
    """Render holdings table."""

    snapshot = snapshot or broker_snapshot()
    st.title("Holdings")
    if snapshot.positions:
        st.dataframe(
            pd.DataFrame([position.model_dump() for position in snapshot.positions]),
            use_container_width=True,
        )
        return
    for warning in snapshot.warnings:
        st.warning(warning)
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "symbol": "TSCO.L",
                    "weight": 0.02,
                    "score": 0.42,
                    "rank_change": 1,
                    "stale_data": False,
                }
            ]
        ),
        use_container_width=True,
    )


if __name__ == "__main__":
    render()
