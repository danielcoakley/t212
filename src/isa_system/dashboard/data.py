"""Shared dashboard data loaders."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import streamlit as st

from isa_system.dashboard.cache_policy import MarketCacheWindow, current_market_cache_window
from isa_system.services.deep_research import latest_deep_research_reviews
from isa_system.services.instrument_validation import (
    InstrumentValidationResponse,
    clear_instrument_cache,
    validate_recommendation_instruments,
)
from isa_system.services.market_scan import load_broker_market_scan_universe
from isa_system.services.market_screener import MarketScreenerResponse, build_market_screener
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
from isa_system.services.recommendation_handoff import (
    RecommendationHandoffResponse,
    build_recommendation_handoff,
)
from isa_system.services.recommendations import RecommendationsResponse, build_recommendations
from isa_system.services.screener_funnel import (
    ScreenerFunnelResponse,
    build_screener_funnel,
)
from isa_system.services.valuation import HoldingsValuationResponse, value_current_holdings
from isa_system.settings import get_settings
from isa_system.utils.hashing import sha256_digest

CACHE_TTL_SECONDS = 14 * 60 * 60


@dataclass(frozen=True)
class RecommendationWorkflow:
    """Cached recommendation workflow payload for dashboard pages."""

    cache_window: MarketCacheWindow
    scan_universe_name: str
    scan_universe_source: str | None
    scan_universe_symbols: list[str]
    scan_universe_warnings: list[str]
    cache_source: str
    recommendations: RecommendationsResponse
    instrument_validation: InstrumentValidationResponse
    handoff: RecommendationHandoffResponse
    screener_funnel: ScreenerFunnelResponse


def cache_window() -> MarketCacheWindow:
    """Return the current market-session cache window."""

    return current_market_cache_window()


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def _broker_snapshot_payload(cache_key: str) -> dict[str, object]:
    """Return cached broker snapshot data."""

    return load_trading212_portfolio().model_dump(mode="json")


def broker_snapshot() -> BrokerPortfolioSnapshot:
    """Return a validated broker snapshot for dashboard pages."""

    return BrokerPortfolioSnapshot.model_validate(_broker_snapshot_payload(cache_window().key))


def refresh_market_data() -> BrokerPortfolioSnapshot:
    """Clear all dashboard caches and reload broker state."""

    clear_portfolio_cache()
    clear_instrument_cache()
    _broker_snapshot_payload.clear()
    _holdings_valuation_payload.clear()
    _rebalance_preview_payload.clear()
    _paper_simulation_payload.clear()
    _recommendations_payload.clear()
    _recommendation_workflow_payload.clear()
    _market_screener_payload.clear()
    _clear_dashboard_disk_cache()
    return broker_snapshot()


def refresh_broker_snapshot() -> BrokerPortfolioSnapshot:
    """Clear cache and reload broker state."""

    return refresh_market_data()


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner="Loading valuation and technical overlays...")
def _holdings_valuation_payload(
    broker_payload: dict[str, object], cache_key: str
) -> dict[str, object]:
    """Return cached valuation data for the current broker payload."""

    snapshot = BrokerPortfolioSnapshot.model_validate(broker_payload)
    return value_current_holdings(snapshot).model_dump(mode="json")


def holdings_valuation(
    snapshot: BrokerPortfolioSnapshot | None = None,
) -> HoldingsValuationResponse:
    """Return valuation and technical overlays for the current holdings."""

    broker = snapshot or broker_snapshot()
    return HoldingsValuationResponse.model_validate(
        _holdings_valuation_payload(broker.model_dump(mode="json"), cache_window().key)
    )


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner="Building preview-only rebalance plan...")
def _rebalance_preview_payload(
    broker_payload: dict[str, object], cache_key: str
) -> dict[str, object]:
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
        _rebalance_preview_payload(broker.model_dump(mode="json"), cache_window().key)
    )


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def _paper_simulation_payload(
    broker_payload: dict[str, object], cache_key: str
) -> dict[str, object]:
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
        _paper_simulation_payload(broker.model_dump(mode="json"), cache_window().key)
    )


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner="Scanning holdings and market candidates...")
def _recommendations_payload(
    broker_payload: dict[str, object],
    candidates: tuple[str, ...],
    include_defaults: bool,
    include_llm: bool,
    cache_key: str,
) -> dict[str, object]:
    """Return cached review-only recommendations."""

    snapshot = BrokerPortfolioSnapshot.model_validate(broker_payload)
    scan_universe = load_broker_market_scan_universe()
    return build_recommendations(
        snapshot,
        candidates=candidates,
        include_default_candidates=include_defaults,
        default_candidates=scan_universe.symbols,
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
            cache_window().key,
        )
    )


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner="Preparing recommendation workflow...")
def _recommendation_workflow_payload(
    broker_payload: dict[str, object],
    candidates: tuple[str, ...],
    include_defaults: bool,
    include_llm: bool,
    cache_key: str,
) -> dict[str, object]:
    """Return cached recommendation, validation, and hand-off data."""

    cached_payload = _read_workflow_disk_cache(
        cache_key,
        candidates=candidates,
        include_defaults=include_defaults,
        include_llm=include_llm,
    )
    if cached_payload is not None:
        cached_payload["cache_source"] = "disk cache"
        _ensure_screener_funnel_payload(cached_payload)
        return cached_payload

    snapshot = BrokerPortfolioSnapshot.model_validate(broker_payload)
    scan_universe = load_broker_market_scan_universe()
    response = build_recommendations(
        snapshot,
        candidates=candidates,
        include_default_candidates=include_defaults,
        default_candidates=scan_universe.symbols,
        include_llm_rationale=include_llm,
    )
    response.warnings.extend(scan_universe.warnings)
    validation = validate_recommendation_instruments(response)
    reviews = latest_deep_research_reviews(
        [item.candidate.research_symbol for item in response.recommendations]
    )
    handoff = build_recommendation_handoff(
        response,
        instrument_validation=validation,
        research_reviews=reviews,
    )
    funnel = build_screener_funnel(
        response,
        validation,
        handoff,
        universe_symbols=scan_universe.symbols,
    )
    payload: dict[str, object] = {
        "cache_key": cache_key,
        "cache_source": "provider refresh",
        "scan_universe_name": scan_universe.name,
        "scan_universe_source": scan_universe.source_path,
        "scan_universe_symbols": scan_universe.symbols,
        "scan_universe_warnings": scan_universe.warnings,
        "recommendations": response.model_dump(mode="json"),
        "instrument_validation": validation.model_dump(mode="json"),
        "handoff": handoff.model_dump(mode="json"),
        "screener_funnel": funnel.model_dump(mode="json"),
    }
    _write_workflow_disk_cache(
        payload,
        cache_key,
        candidates=candidates,
        include_defaults=include_defaults,
        include_llm=include_llm,
    )
    return payload


def recommendation_workflow(
    snapshot: BrokerPortfolioSnapshot | None = None,
    *,
    candidates: tuple[str, ...] = (),
    include_defaults: bool = True,
    include_llm: bool = False,
) -> RecommendationWorkflow:
    """Return cached recommendation workflow data."""

    broker = snapshot or broker_snapshot()
    window = cache_window()
    payload = _recommendation_workflow_payload(
        broker.model_dump(mode="json"),
        candidates,
        include_defaults,
        include_llm,
        window.key,
    )
    symbols_payload = payload["scan_universe_symbols"]
    warnings_payload = payload["scan_universe_warnings"]
    scan_symbols = (
        [str(symbol) for symbol in symbols_payload] if isinstance(symbols_payload, list) else []
    )
    scan_warnings = (
        [str(warning) for warning in warnings_payload] if isinstance(warnings_payload, list) else []
    )
    return RecommendationWorkflow(
        cache_window=window,
        scan_universe_name=str(payload["scan_universe_name"]),
        scan_universe_source=payload["scan_universe_source"]
        if isinstance(payload["scan_universe_source"], str)
        else None,
        scan_universe_symbols=scan_symbols,
        scan_universe_warnings=scan_warnings,
        cache_source=str(payload.get("cache_source") or "memory cache"),
        recommendations=RecommendationsResponse.model_validate(payload["recommendations"]),
        instrument_validation=InstrumentValidationResponse.model_validate(
            payload["instrument_validation"]
        ),
        handoff=RecommendationHandoffResponse.model_validate(payload["handoff"]),
        screener_funnel=ScreenerFunnelResponse.model_validate(payload["screener_funnel"]),
    )


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner="Screening the Trading 212 market universe...")
def _market_screener_payload(max_loaded: int, top_n: int, cache_key: str) -> dict[str, object]:
    """Return cached broad-market screener rows."""

    return build_market_screener(max_loaded=max_loaded, top_n=top_n).model_dump(mode="json")


def market_screener(*, max_loaded: int = 250, top_n: int = 50) -> MarketScreenerResponse:
    """Return the current broad-market screener."""

    return MarketScreenerResponse.model_validate(
        _market_screener_payload(max_loaded, top_n, cache_window().key)
    )


def _read_workflow_disk_cache(
    cache_key: str,
    *,
    candidates: tuple[str, ...],
    include_defaults: bool,
    include_llm: bool,
) -> dict[str, object] | None:
    path = _workflow_cache_path(
        cache_key,
        candidates=candidates,
        include_defaults=include_defaults,
        include_llm=include_llm,
    )
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _ensure_screener_funnel_payload(payload: dict[str, object]) -> None:
    """Backfill funnel data for dashboard caches written by older app versions."""

    if "screener_funnel" in payload:
        return
    try:
        response = RecommendationsResponse.model_validate(payload["recommendations"])
        validation = InstrumentValidationResponse.model_validate(payload["instrument_validation"])
        handoff = RecommendationHandoffResponse.model_validate(payload["handoff"])
    except (KeyError, TypeError, ValueError):
        return
    symbols_payload = payload.get("scan_universe_symbols")
    universe_symbols = (
        [str(symbol) for symbol in symbols_payload] if isinstance(symbols_payload, list) else []
    )
    payload["screener_funnel"] = build_screener_funnel(
        response,
        validation,
        handoff,
        universe_symbols=universe_symbols,
    ).model_dump(mode="json")


def _write_workflow_disk_cache(
    payload: dict[str, object],
    cache_key: str,
    *,
    candidates: tuple[str, ...],
    include_defaults: bool,
    include_llm: bool,
) -> None:
    path = _workflow_cache_path(
        cache_key,
        candidates=candidates,
        include_defaults=include_defaults,
        include_llm=include_llm,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2, default=str), encoding="utf-8")


def _workflow_cache_path(
    cache_key: str,
    *,
    candidates: tuple[str, ...],
    include_defaults: bool,
    include_llm: bool,
) -> Path:
    variant_hash = sha256_digest(
        {
            "cache_key": cache_key,
            "candidates": list(candidates),
            "include_defaults": include_defaults,
            "include_llm": include_llm,
        }
    )[:12]
    return _dashboard_cache_dir() / f"recommendation_workflow_{cache_key}_{variant_hash}.json"


def _dashboard_cache_dir() -> Path:
    return get_settings().artifacts_path / "dashboard_cache"


def _clear_dashboard_disk_cache() -> None:
    cache_dir = _dashboard_cache_dir()
    try:
        resolved_dir = cache_dir.resolve()
    except OSError:
        return
    artifacts_dir = get_settings().artifacts_path.resolve()
    if artifacts_dir not in resolved_dir.parents and resolved_dir != artifacts_dir:
        return
    for path in cache_dir.glob("*.json"):
        try:
            path.unlink()
        except OSError:
            continue
