"""Portfolio overview dashboard page."""

from __future__ import annotations

import streamlit as st


def render() -> None:
    """Render overview metrics."""

    cols = st.columns(4)
    cols[0].metric("Algo sleeve", "20%")
    cols[1].metric("Core sleeve", "80%")
    cols[2].metric("Cash buffer", "3%")
    cols[3].metric("Exposure", "97%")
    st.info("Offline starter data is displayed until real broker and research data are configured.")
