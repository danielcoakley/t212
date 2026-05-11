"""Read-only management and safety status page."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import streamlit as st
from pydantic import SecretStr

from isa_system.dashboard.cache_policy import MarketCacheWindow
from isa_system.dashboard.data import broker_snapshot, cache_window
from isa_system.domain.enums import RuntimeMode
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot
from isa_system.settings import Settings, get_settings
from isa_system.utils.time import now_utc, require_utc, to_london

BROKER_READY_STATUSES = {"live", "demo"}
FUTURE_CLOCK_TOLERANCE = timedelta(minutes=5)


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

    st.subheader("Operational Status")
    st.dataframe(
        operational_status_rows(snapshot, settings, window),
        hide_index=True,
        use_container_width=True,
    )
    st.info(f"Next required safe action: {next_required_safe_action(snapshot, settings, window)}")

    st.subheader("Cache Freshness")
    st.dataframe(
        cache_freshness_rows(snapshot, window),
        hide_index=True,
        use_container_width=True,
    )

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
            _trading212_provider_status(settings),
            "Read-only account, positions, and broker universe.",
            "Required for live portfolio context.",
            "Add both Trading 212 credentials, then refresh dashboard cache."
            if not _trading212_configured(settings)
            else "Use as read-only account and broker-universe context.",
        ),
        _provider_row(
            "OpenAI",
            _configured_status(settings.openai_api_key),
            "Deep research gate for buy/add preview approval.",
            "Optional, but buy/add rows cannot pass the gate without it.",
            "Add OPENAI_API_KEY before expecting BUY/add research approval."
            if not _has_secret(settings.openai_api_key)
            else "Run deep research for BUY/add candidates before preview sizing.",
        ),
        _provider_row(
            "Alpha Vantage",
            _configured_status(settings.alpha_vantage_api_key),
            "Convenience EOD prices and selected research data.",
            "Optional; rate-constrained fallback/enrichment source.",
            "Use as convenience enrichment; monitor rate limits."
            if _has_secret(settings.alpha_vantage_api_key)
            else "Leave missing unless enrichment quality requires this feed.",
        ),
        _provider_row(
            "FMP",
            _configured_status(settings.fmp_api_key),
            "Convenience fundamentals and company context.",
            "Optional enrichment source.",
            "Use as convenience enrichment; official sources still win for evidence."
            if _has_secret(settings.fmp_api_key)
            else "Leave missing unless fundamentals enrichment is needed.",
        ),
        _provider_row(
            "FRED",
            _configured_status(settings.fred_api_key),
            "Macro and regime context.",
            "Optional for MVP.",
            "Use for macro overlays only when they are part of the review."
            if _has_secret(settings.fred_api_key)
            else "Leave missing unless macro overlays are part of the review.",
        ),
        _provider_row(
            "Companies House",
            _configured_status(settings.companies_house_api_key),
            "UK issuer identity and filing history.",
            "Important for post-MVP identity mapping.",
            "Use for official UK identity checks; preserve availability timing."
            if _has_secret(settings.companies_house_api_key)
            else "Configure before relying on official UK identity checks.",
        ),
        _provider_row(
            "SEC EDGAR",
            "Configured" if settings.sec_user_agent else "Missing",
            "Official US filings.",
            "Use a clear user agent before depending on this source.",
            "Use for official US filing evidence; preserve availability timing."
            if settings.sec_user_agent
            else "Set SEC_USER_AGENT before depending on US filing evidence.",
        ),
        _provider_row(
            "Social sentiment",
            _social_provider_status(settings),
            "Low-weight optional sentiment overlays.",
            "Disabled by default; official sources remain higher priority.",
            _social_provider_action(settings),
        ),
    ]


def operational_status_rows(
    snapshot: BrokerPortfolioSnapshot,
    settings: Settings,
    window: MarketCacheWindow,
    *,
    as_of_utc: datetime | None = None,
) -> list[dict[str, str]]:
    """Return the high-level management status model for the page."""

    provider_status, provider_state, provider_action = _provider_readiness(settings)
    cache_status, cache_state, cache_action = _cache_freshness_summary(
        cache_freshness_rows(snapshot, window, as_of_utc=as_of_utc)
    )
    broker_status, broker_state, broker_action = _broker_read_only_state(snapshot)
    research_status, research_state, research_action = _deep_research_state(settings)
    guardrail_status, guardrail_state, guardrail_action = _live_guardrail_state(settings)

    return [
        _status_row("Provider readiness", provider_status, provider_state, provider_action),
        _status_row("Cache freshness", cache_status, cache_state, cache_action),
        _status_row("Broker read-only", broker_status, broker_state, broker_action),
        _status_row("Deep research", research_status, research_state, research_action),
        _status_row("Live guardrails", guardrail_status, guardrail_state, guardrail_action),
        _status_row(
            "Next required action",
            "Action",
            "Highest-priority safe operator step.",
            next_required_safe_action(snapshot, settings, window, as_of_utc=as_of_utc),
        ),
    ]


def cache_freshness_rows(
    snapshot: BrokerPortfolioSnapshot,
    window: MarketCacheWindow,
    *,
    as_of_utc: datetime | None = None,
) -> list[dict[str, str]]:
    """Return freshness rows for the dashboard cache window and broker snapshot."""

    as_of = require_utc(as_of_utc or now_utc())
    opened_at = require_utc(window.opened_at_utc)
    next_refresh = require_utc(window.next_refresh_at_utc)
    snapshot_at = require_utc(snapshot.retrieved_at_utc)

    if as_of < opened_at:
        window_row = _cache_row(
            "Market-session cache",
            "Check clock",
            f"{window.label} opens at {_format_london(opened_at)}, after the current clock.",
            "Check local clock/timezone before relying on cache timestamps.",
        )
    elif as_of >= next_refresh:
        window_row = _cache_row(
            "Market-session cache",
            "Stale",
            f"{window.label} opened at {_format_london(opened_at)}; refresh was due at "
            f"{_format_london(next_refresh)}.",
            "Refresh dashboard cache before relying on market context.",
        )
    else:
        window_row = _cache_row(
            "Market-session cache",
            "Fresh",
            f"{window.label} opened at {_format_london(opened_at)}; next refresh is "
            f"{_format_london(next_refresh)}.",
            "No action unless broker state or market context changed materially.",
        )

    if snapshot.status == "not_configured":
        broker_row = _cache_row(
            "Broker snapshot",
            "Missing",
            "No Trading 212 account snapshot is available because credentials are not configured.",
            "Add Trading 212 read-only credentials, then refresh dashboard cache.",
        )
    elif snapshot.status == "error":
        broker_row = _cache_row(
            "Broker snapshot",
            "Error",
            f"Trading 212 read failed at {_format_london(snapshot_at)}.",
            "Resolve the provider error or work only with local preview context.",
        )
    elif snapshot_at > as_of + FUTURE_CLOCK_TOLERANCE:
        broker_row = _cache_row(
            "Broker snapshot",
            "Check clock",
            f"Broker snapshot timestamp {_format_london(snapshot_at)} is ahead of the "
            "current clock.",
            "Check local clock/timezone before relying on broker freshness.",
        )
    elif snapshot_at < opened_at:
        broker_row = _cache_row(
            "Broker snapshot",
            "Stale",
            f"Broker snapshot was retrieved at {_format_london(snapshot_at)}, before the current "
            f"{window.label.lower()} opened.",
            "Refresh dashboard cache before reviewing account state or previews.",
        )
    else:
        broker_row = _cache_row(
            "Broker snapshot",
            "Fresh",
            f"Read-only {snapshot.environment} broker context was retrieved at "
            f"{_format_london(snapshot_at)}.",
            "No action unless account state changed at the broker.",
        )

    return [window_row, broker_row]


def next_required_safe_action(
    snapshot: BrokerPortfolioSnapshot,
    settings: Settings,
    window: MarketCacheWindow,
    *,
    as_of_utc: datetime | None = None,
) -> str:
    """Return one prioritized safe operator action for the current state."""

    if snapshot.status == "error":
        return "Resolve the Trading 212 read error before relying on broker state."
    if not _trading212_configured(settings) or snapshot.status == "not_configured":
        return "Configure Trading 212 read-only credentials, then refresh dashboard cache."

    cache_rows = cache_freshness_rows(snapshot, window, as_of_utc=as_of_utc)
    stale_or_clock_rows = [row for row in cache_rows if row["Status"] in {"Stale", "Check clock"}]
    if stale_or_clock_rows:
        return stale_or_clock_rows[0]["Next safe action"]

    if settings.kill_switch_enabled:
        return (
            "Keep live blocked while the kill switch is enabled; continue with preview "
            "or paper only."
        )
    if (
        settings.runtime_mode == RuntimeMode.LIVE
        and settings.live_armed
        and not settings.kill_switch_enabled
    ):
        return (
            "Live is armed; require paper evidence, reconciliation, idempotency, and explicit "
            "operator approval before any separate live path."
        )
    if not _has_secret(settings.openai_api_key):
        return (
            "Configure OpenAI for the deep research gate, or limit review to rows that do not "
            "need BUY/add approval."
        )
    if settings.runtime_mode == RuntimeMode.PAPER:
        return "Continue paper simulation and collect evidence before any live-readiness review."
    return (
        "Review recommendations, run deep research for BUY/add rows, then build "
        "preview-only sizing."
    )


def safety_checklist_rows(
    snapshot: BrokerPortfolioSnapshot, settings: Settings
) -> list[dict[str, str]]:
    """Return read-only safety checklist rows for the management page."""

    broker_ready = snapshot.status in BROKER_READY_STATUSES
    deep_research_ready = _has_secret(settings.openai_api_key)
    live_blocked = (
        settings.runtime_mode != RuntimeMode.LIVE
        or settings.kill_switch_enabled
        or not settings.live_armed
    )
    return [
        _check_row(
            "Runtime mode",
            "Preview-first"
            if settings.runtime_mode == RuntimeMode.PREVIEW
            else settings.runtime_mode.value,
            "Dashboard Management remains read-only and does not mutate runtime mode.",
        ),
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
    st.caption(window.manual_refresh_hint)
    for warning in snapshot.warnings:
        st.warning(warning)


def _provider_row(
    provider: str,
    status: str,
    purpose: str,
    mvp_impact: str,
    next_safe_action: str,
) -> dict[str, str]:
    return {
        "Provider": provider,
        "Status": status,
        "Purpose": purpose,
        "MVP impact": mvp_impact,
        "Next safe action": next_safe_action,
    }


def _status_row(area: str, status: str, state: str, next_safe_action: str) -> dict[str, str]:
    return {
        "Area": area,
        "Status": status,
        "State": state,
        "Next safe action": next_safe_action,
    }


def _cache_row(item: str, status: str, state: str, next_safe_action: str) -> dict[str, str]:
    return {
        "Cache item": item,
        "Status": status,
        "State": state,
        "Next safe action": next_safe_action,
    }


def _check_row(name: str, status: str, detail: str) -> dict[str, str]:
    return {"Check": name, "Status": status, "Detail": detail}


def _provider_readiness(settings: Settings) -> tuple[str, str, str]:
    broker_configured = _trading212_configured(settings)
    deep_research_configured = _has_secret(settings.openai_api_key)
    optional_count = _optional_provider_count(settings)
    optional_state = f"{optional_count} optional enrichment source(s) configured."

    if broker_configured and deep_research_configured:
        return (
            "Ready",
            f"Trading 212 and OpenAI are configured. {optional_state}",
            "Review provider warnings and refresh when broker state changes.",
        )
    if broker_configured:
        return (
            "Partial",
            f"Trading 212 is configured, but OpenAI is missing. {optional_state}",
            "Add OPENAI_API_KEY before expecting BUY/add research approval.",
        )
    if deep_research_configured:
        return (
            "Partial",
            "OpenAI is configured, but Trading 212 read-only credentials are missing. "
            f"{optional_state}",
            "Add Trading 212 credentials for account state and broker-universe validation.",
        )
    return (
        "Missing",
        f"Trading 212 and OpenAI are missing. {optional_state}",
        "Configure Trading 212 first; add OpenAI before BUY/add research approval.",
    )


def _cache_freshness_summary(rows: list[dict[str, str]]) -> tuple[str, str, str]:
    status_order = ["Error", "Missing", "Stale", "Check clock"]
    for status in status_order:
        for row in rows:
            if row["Status"] == status:
                return (
                    status,
                    "; ".join(f"{item['Cache item']}: {item['Status']}" for item in rows),
                    row["Next safe action"],
                )
    return (
        "Fresh",
        "; ".join(f"{item['Cache item']}: {item['Status']}" for item in rows),
        "No cache action required unless broker state or market context changed materially.",
    )


def _broker_read_only_state(snapshot: BrokerPortfolioSnapshot) -> tuple[str, str, str]:
    retrieved_at = _format_london(snapshot.retrieved_at_utc)
    if snapshot.status in BROKER_READY_STATUSES:
        return (
            "Ready",
            f"Read-only {snapshot.status} broker context retrieved at {retrieved_at}.",
            "Use broker data as context only; Management does not submit or arm orders.",
        )
    if snapshot.status == "not_configured":
        return (
            "Missing",
            "Trading 212 read-only context is not configured.",
            "Add Trading 212 credentials for account state, positions, and broker-universe checks.",
        )
    return (
        "Error",
        f"Trading 212 read-only context failed at {retrieved_at}.",
        "Resolve the broker read failure before relying on account state.",
    )


def _deep_research_state(settings: Settings) -> tuple[str, str, str]:
    if _has_secret(settings.openai_api_key):
        return (
            "Ready",
            "OpenAI is configured, so deep research reviews can be generated.",
            "Run deep research for BUY/add candidates and require non-expired RESEARCH_PASSED.",
        )
    return (
        "Unavailable",
        "OpenAI is not configured; BUY/add rows cannot receive research-gate approval.",
        "Configure OPENAI_API_KEY or restrict review to rows that do not need BUY/add approval.",
    )


def _live_guardrail_state(settings: Settings) -> tuple[str, str, str]:
    mode = settings.runtime_mode.value
    armed = "armed" if settings.live_armed else "disarmed"
    if settings.kill_switch_enabled:
        return (
            "Blocked",
            f"Runtime mode is {mode}, live is {armed}, and the kill switch is enabled.",
            "Keep live blocked and use preview or paper workflows only.",
        )
    if settings.runtime_mode != RuntimeMode.LIVE:
        return (
            "Safe default",
            f"Runtime mode is {mode}; live is {armed}; kill switch is clear.",
            "Stay in preview/paper until paper evidence supports a separate live-readiness review.",
        )
    if not settings.live_armed:
        return (
            "Blocked",
            "Runtime mode is live, but live trading is not armed.",
            "Return to preview/paper unless a live-readiness review explicitly selects live mode.",
        )
    return (
        "Armed",
        "Runtime mode is live, live is armed, and the kill switch is clear.",
        "Do not submit from Management; require paper evidence and explicit operator approval.",
    )


def _trading212_provider_status(settings: Settings) -> str:
    key_configured = _has_secret(settings.trading212_api_key)
    secret_configured = _has_secret(settings.trading212_api_secret)
    if key_configured and secret_configured:
        return "Configured"
    if key_configured or secret_configured:
        return "Partial"
    return "Missing"


def _configured_status(value: SecretStr | Any | None) -> str:
    return "Configured" if _has_secret(value) else "Missing"


def _social_provider_status(settings: Settings) -> str:
    configured_count = sum(
        [
            _has_secret(settings.reddit_client_id),
            _has_secret(settings.reddit_client_secret),
            _has_secret(settings.x_bearer_token),
        ]
    )
    if configured_count == 3:
        return "Configured"
    if configured_count:
        return "Partial"
    return "Missing"


def _social_provider_action(settings: Settings) -> str:
    status = _social_provider_status(settings)
    if status == "Configured":
        return "Use only as low-weight context; official sources remain higher priority."
    if status == "Partial":
        return "Complete all sentiment credentials or leave sentiment disabled."
    return "Keep disabled unless sentiment overlays are explicitly in scope."


def _trading212_configured(settings: Settings) -> bool:
    return _has_secret(settings.trading212_api_key) and _has_secret(settings.trading212_api_secret)


def _optional_provider_count(settings: Settings) -> int:
    return sum(
        [
            _has_secret(settings.alpha_vantage_api_key),
            _has_secret(settings.fmp_api_key),
            _has_secret(settings.fred_api_key),
            _has_secret(settings.companies_house_api_key),
            bool(settings.sec_user_agent),
            _social_provider_status(settings) == "Configured",
        ]
    )


def _has_secret(value: SecretStr | Any | None) -> bool:
    if value is None:
        return False
    if isinstance(value, SecretStr):
        return bool(value.get_secret_value())
    return bool(value)


def _format_london(value: datetime) -> str:
    return f"{to_london(value):%Y-%m-%d %H:%M %Z}"


if __name__ == "__main__":
    render()
