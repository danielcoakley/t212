"""Shared dashboard data loaders."""

from __future__ import annotations

import streamlit as st

from isa_system.services.paper_simulation import PaperSimulationSnapshot, simulate_paper_fills
from isa_system.services.portfolio_state import (
    BrokerPortfolioSnapshot,
    clear_portfolio_cache,
    load_trading212_portfolio,
)
from isa_system.services.rebalance_preview import (
    RebalancePreviewSnapshot,
    build_preview_from_holdings,
)
from isa_system.services.recommendations import RecommendationsResponse, build_recommendations
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
    _paper_simulation_payload.clear()
    _recommendations_payload.clear()
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


@st.cache_data(ttl=300, show_spinner=False)
def _paper_simulation_payload(broker_payload: dict[str, object]) -> dict[str, object]:
    """Return cached paper fill simulation for the current preview."""

    snapshot = BrokerPortfolioSnapshot.model_validate(broker_payload)
    preview = rebalance_preview(snapshot)
    return simulate_paper_fills(preview).model_dump(mode="json")


def paper_simulation(
    snapshot: BrokerPortfolioSnapshot | None = None,
) -> PaperSimulationSnapshot:
    """Return a local paper fill simulation for the current preview."""

    broker = snapshot or broker_snapshot()
    return PaperSimulationSnapshot.model_validate(
        _paper_simulation_payload(broker.model_dump(mode="json"))
    )


@st.cache_data(ttl=900, show_spinner="Scanning holdings and market candidates...")
def _recommendations_payload(
    broker_payload: dict[str, object],
    candidates: tuple[str, ...],
    include_defaults: bool,
    include_llm: bool,
) -> dict[str, object]:
    """Return cached review-only recommendations."""

    snapshot = BrokerPortfolioSnapshot.model_validate(broker_payload)
    return build_recommendations(
        snapshot,
        candidates=candidates,
        include_default_candidates=include_defaults,
        include_llm_rationale=include_llm,
    ).model_dump(mode="json")


def recommendations(
    snapshot: BrokerPortfolioSnapshot | None = None,
    *,
    candidates: tuple[str, ...] = (),
    include_defaults: bool = True,
    include_llm: bool = False,
) -> RecommendationsResponse:
    """Return review-only recommendations for holdings and scan candidates."""

    broker = snapshot or broker_snapshot()
    return RecommendationsResponse.model_validate(
        _recommendations_payload(
            broker.model_dump(mode="json"),
            candidates,
            include_defaults,
            include_llm,
        )
    )
