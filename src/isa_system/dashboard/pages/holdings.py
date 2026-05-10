"""Holdings dashboard page."""

from __future__ import annotations

import pandas as pd
import streamlit as st


def render() -> None:
    """Render holdings table."""

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
