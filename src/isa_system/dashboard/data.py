"""Shared dashboard data loaders."""

from __future__ import annotations

import streamlit as st

from isa_system.services.portfolio_state import (
    BrokerPortfolioSnapshot,
    clear_portfolio_cache,
    load_trading212_portfolio,
)
from isa_system.services.rebalance_preview import (
    RebalancePreviewSnapshot,
    build_preview_from_holdings,
)
from isa_system.services.valuation import HoldingsValuationResponse, value_current_holdings


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
    _holdings_valuation_payload.clear()
    _rebalance_preview_payload.clear()
    return broker_snapshot()


@st.cache_data(ttl=900, show_spinner="Loading valuation and technical overlays...")
def _holdings_valuation_payload(broker_payload: dict[str, object]) -> dict[str, object]:
    """Return cached valuation data for the current broker payload."""

    snapshot = BrokerPortfolioSnapshot.model_validate(broker_payload)
    return value_current_holdings(snapshot).model_dump(mode="json")


def holdings_valuation(
    snapshot: BrokerPortfolioSnapshot | None = None,
) -> HoldingsValuationResponse:
    """Return valuation and technical overlays for the current holdings."""

    broker = snapshot or broker_snapshot()
    return HoldingsValuationResponse.model_validate(
        _holdings_valuation_payload(broker.model_dump(mode="json"))
    )


@st.cache_data(ttl=300, show_spinner="Building preview-only rebalance plan...")
def _rebalance_preview_payload(broker_payload: dict[str, object]) -> dict[str, object]:
    """Return cached preview-only rebalance plan data."""

    snapshot = BrokerPortfolioSnapshot.model_validate(broker_payload)
    valuation = holdings_valuation(snapshot)
    return build_preview_from_holdings(snapshot, valuation).model_dump(mode="json")


def rebalance_preview(
    snapshot: BrokerPortfolioSnapshot | None = None,
) -> RebalancePreviewSnapshot:
    """Return a preview-only rebalance plan for the current holdings."""

    broker = snapshot or broker_snapshot()
    return RebalancePreviewSnapshot.model_validate(
        _rebalance_preview_payload(broker.model_dump(mode="json"))
    )
