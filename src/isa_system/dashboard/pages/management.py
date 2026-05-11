"""Read-only management and safety status page."""

from __future__ import annotations

from typing import Any

import streamlit as st
from pydantic import SecretStr

from isa_system.dashboard.cache_policy import MarketCacheWindow
from isa_system.dashboard.data import broker_snapshot, cache_window
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot
from isa_system.settings import Settings, get_settings
from isa_system.utils.time import to_london


def render(snapshot: BrokerPortfolioSnapshot | None = None) -> None:
    """Render management status without mutating runtime state."""

    settings = get_settings()
    snapshot = snapshot or broker_snapshot()
    window = cache_window()

    st.title("Management")
    st.caption(
        "Read-only safety, configuration, and freshness checks for the local operator "
        "cockpit. This page does not submit orders or arm live trading."
    )

    _render_runtime_summary(snapshot, settings, window)

    st.subheader("Provider Configuration")
    st.dataframe(provider_status_rows(settings), hide_index=True, use_container_width=True)

    st.subheader("Safety Checklist")
    st.dataframe(
        safety_checklist_rows(snapshot, settings),
        hide_index=True,
        use_container_width=True,
    )

    st.subheader("Blocked Until Later")
    st.info(
        "Full-auto live trading, hosted auth, team approval workflows, and parser-dependent "
        "official catalyst strategies remain post-MVP work. Paper evidence and reconciliation "
        "come first."
    )


def provider_status_rows(settings: Settings) -> list[dict[str, str]]:
    """Return dashboard rows describing provider configuration state."""

    return [
        _provider_row(
            "Trading 212",
            _has_secret(settings.trading212_api_key)
            and _has_secret(settings.trading212_api_secret),
            "Read-only account, positions, and broker universe.",
            "Required for live portfolio context.",
        ),
        _provider_row(
            "OpenAI",
            _has_secret(settings.openai_api_key),
            "Deep research gate for buy/add preview approval.",
            "Optional, but buy/add rows cannot pass the gate without it.",
        ),
        _provider_row(
            "Alpha Vantage",
            _has_secret(settings.alpha_vantage_api_key),
            "Convenience EOD prices and selected research data.",
            "Optional; rate-constrained fallback/enrichment source.",
        ),
        _provider_row(
            "FMP",
            _has_secret(settings.fmp_api_key),
            "Convenience fundamentals and company context.",
            "Optional enrichment source.",
        ),
        _provider_row(
            "FRED",
            _has_secret(settings.fred_api_key),
            "Macro and regime context.",
            "Optional for MVP.",
        ),
        _provider_row(
            "Companies House",
            _has_secret(settings.companies_house_api_key),
            "UK issuer identity and filing history.",
            "Important for post-MVP identity mapping.",
        ),
        _provider_row(
            "SEC EDGAR",
            bool(settings.sec_user_agent),
            "Official US filings.",
            "Use a clear user agent before depending on this source.",
        ),
        _provider_row(
            "Social sentiment",
            _has_secret(settings.reddit_client_id)
            and _has_secret(settings.reddit_client_secret)
            and _has_secret(settings.x_bearer_token),
            "Low-weight optional sentiment overlays.",
            "Disabled by default; official sources remain higher priority.",
        ),
    ]


def safety_checklist_rows(
    snapshot: BrokerPortfolioSnapshot, settings: Settings
) -> list[dict[str, str]]:
    """Return read-only safety checklist rows for the management page."""

    broker_ready = snapshot.status in {"live", "demo"}
    deep_research_ready = _has_secret(settings.openai_api_key)
    live_blocked = settings.kill_switch_enabled or not settings.live_armed
    return [
        _check_row(
            "Preview workflow",
            "Ready",
            "Recommendation-to-preview sizing is available without broker submission.",
        ),
        _check_row(
            "Broker read-only context",
            "Ready" if broker_ready else "Needs setup",
            "Trading 212 credentials are configured."
            if broker_ready
            else "Add Trading 212 credentials for live account context.",
        ),
        _check_row(
            "Deep research gate",
            "Ready" if deep_research_ready else "Unavailable",
            "OpenAI-backed review can approve eligible buy/add preview rows."
            if deep_research_ready
            else "BUY/add rows remain blocked from approval when OPENAI_API_KEY is absent.",
        ),
        _check_row(
            "Kill switch",
            "Enabled" if settings.kill_switch_enabled else "Clear",
            "Live submit paths must stay blocked while the kill switch is enabled."
            if settings.kill_switch_enabled
            else "No kill-switch block is configured in local settings.",
        ),
        _check_row(
            "Live submission",
            "Blocked" if live_blocked else "Armed",
            "Live remains blocked unless explicitly armed and kill switch is clear."
            if live_blocked
            else "Use only after paper acceptance evidence and operator review.",
        ),
        _check_row(
            "Paper evidence",
            "Planned",
            "Paper simulation exists; persistent paper cycles and reconciliation are next.",
        ),
        _check_row(
            "Official-source freshness",
            "Partial",
            "Provider adapters exist, but official PIT evidence depth still needs expansion.",
        ),
        _check_row(
            "Duplicate-order guard",
            "Implemented",
            "Local idempotency reservation exists and must stay mandatory before live POSTs.",
        ),
    ]


def _render_runtime_summary(
    snapshot: BrokerPortfolioSnapshot, settings: Settings, window: MarketCacheWindow
) -> None:
    """Render the compact top-line runtime status."""

    opened = to_london(window.opened_at_utc)
    next_refresh = to_london(window.next_refresh_at_utc)
    cols = st.columns(4)
    cols[0].metric("Runtime mode", settings.runtime_mode.value)
    cols[1].metric("Live armed", "Yes" if settings.live_armed else "No")
    cols[2].metric("Kill switch", "Enabled" if settings.kill_switch_enabled else "Clear")
    cols[3].metric("Broker", snapshot.status)

    cache_cols = st.columns(3)
    cache_cols[0].metric("Broker environment", snapshot.environment)
    cache_cols[1].metric("Cache window", window.label)
    cache_cols[2].metric("Next refresh", f"{next_refresh:%Y-%m-%d %H:%M %Z}")
    st.caption(f"Current cache opened at {opened:%Y-%m-%d %H:%M %Z}.")
    for warning in snapshot.warnings:
        st.warning(warning)


def _provider_row(provider: str, configured: bool, purpose: str, mvp_impact: str) -> dict[str, str]:
    return {
        "Provider": provider,
        "Status": "Configured" if configured else "Missing",
        "Purpose": purpose,
        "MVP impact": mvp_impact,
    }


def _check_row(name: str, status: str, detail: str) -> dict[str, str]:
    return {"Check": name, "Status": status, "Detail": detail}


def _has_secret(value: SecretStr | Any | None) -> bool:
    if value is None:
        return False
    if isinstance(value, SecretStr):
        return bool(value.get_secret_value())
    return bool(value)


if __name__ == "__main__":
    render()
