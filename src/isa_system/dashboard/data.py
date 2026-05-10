"""Shared dashboard data loaders."""

from __future__ import annotations

import streamlit as st

from isa_system.services.portfolio_state import (
    BrokerPortfolioSnapshot,
    clear_portfolio_cache,
    load_trading212_portfolio,
)


@st.cache_data(ttl=30, show_spinner=False)
def _broker_snapshot_payload() -> dict[str, object]:
    """Return cached broker snapshot data."""

    return load_trading212_portfolio().model_dump(mode="json")


def broker_snapshot() -> BrokerPortfolioSnapshot:
    """Return a validated broker snapshot for dashboard pages."""

    return BrokerPortfolioSnapshot.model_validate(_broker_snapshot_payload())


def refresh_broker_snapshot() -> BrokerPortfolioSnapshot:
    """Clear cache and reload broker state."""

    clear_portfolio_cache()
    _broker_snapshot_payload.clear()
    return broker_snapshot()
