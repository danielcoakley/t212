"""Streamlit operator dashboard."""

from __future__ import annotations

from datetime import UTC, datetime

import streamlit as st

from isa_system.dashboard.data import broker_snapshot, refresh_broker_snapshot
from isa_system.dashboard.pages import (
    audit_logs,
    catalysts,
    factor_attribution,
    holdings,
    overview,
    rebalance_preview,
    valuation,
)
from isa_system.utils.time import to_london


def main() -> None:
    """Render the starter dashboard."""

    st.set_page_config(page_title="ISA System", layout="wide")
    snapshot = broker_snapshot()
    if st.sidebar.button("Refresh broker state"):
        snapshot = refresh_broker_snapshot()
    london_now = to_london(datetime.now(tz=UTC))
    st.title("ISA System Control")
    with st.sidebar:
        st.metric("Mode", "Preview")
        st.metric("Broker", snapshot.status)
        st.metric("Broker environment", snapshot.environment)
        st.metric("Kill switch", "Clear")
        st.caption(f"London time: {london_now:%Y-%m-%d %H:%M:%S %Z}")
        for warning in snapshot.warnings:
            st.warning(warning)
    tabs = st.tabs(
        ["Overview", "Holdings", "Valuation", "Catalysts", "Rebalance", "Factors", "Audit"]
    )
    with tabs[0]:
        overview.render(snapshot)
    with tabs[1]:
        holdings.render(snapshot)
    with tabs[2]:
        valuation.render(snapshot)
    with tabs[3]:
        catalysts.render(snapshot)
    with tabs[4]:
        rebalance_preview.render(snapshot)
    with tabs[5]:
        factor_attribution.render(snapshot)
    with tabs[6]:
        audit_logs.render(snapshot)


if __name__ == "__main__":
    main()
