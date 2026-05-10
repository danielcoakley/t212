"""Catalyst dashboard page."""

from __future__ import annotations

import pandas as pd
import streamlit as st


def render() -> None:
    """Render upcoming catalysts."""

    st.warning("Event vetoes and blackout windows appear here before live submission.")
    st.dataframe(
        pd.DataFrame(
            [{"symbol": "AAPL", "event": "earnings", "source": "synthetic", "blackout": True}]
        ),
        use_container_width=True,
    )
