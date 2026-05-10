"""Rebalance preview dashboard page."""

from __future__ import annotations

import pandas as pd
import streamlit as st


def render() -> None:
    """Render preview table and warnings."""

    st.error(
        "Live submit is disabled until mode is live, armed, and kill switch is clear.", icon="!"
    )
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
