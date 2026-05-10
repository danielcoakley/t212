"""Streamlit operator dashboard."""

from __future__ import annotations

from datetime import UTC, datetime

import streamlit as st

from isa_system.dashboard.pages import (
    audit_logs,
    catalysts,
    factor_attribution,
    holdings,
    overview,
    rebalance_preview,
)
from isa_system.utils.time import to_london


def main() -> None:
    """Render the starter dashboard."""

    st.set_page_config(page_title="ISA System", layout="wide")
    london_now = to_london(datetime.now(tz=UTC))
    st.title("ISA System Control")
    with st.sidebar:
        st.metric("Mode", "Preview")
        st.metric("Kill switch", "Clear")
        st.caption(f"London time: {london_now:%Y-%m-%d %H:%M:%S %Z}")
    tabs = st.tabs(["Overview", "Holdings", "Catalysts", "Rebalance", "Factors", "Audit"])
    with tabs[0]:
        overview.render()
    with tabs[1]:
        holdings.render()
    with tabs[2]:
        catalysts.render()
    with tabs[3]:
        rebalance_preview.render()
    with tabs[4]:
        factor_attribution.render()
    with tabs[5]:
        audit_logs.render()


if __name__ == "__main__":
    main()
