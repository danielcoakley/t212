"""Tests for the read-only dashboard management status helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pydantic import SecretStr

from isa_system.dashboard.cache_policy import MarketCacheWindow
from isa_system.dashboard.pages.management import (
    cache_freshness_rows,
    next_required_safe_action,
    operational_status_rows,
    provider_status_rows,
    safety_checklist_rows,
)
from isa_system.domain.enums import RuntimeMode
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot
from isa_system.settings import Settings


def test_provider_status_marks_missing_optional_and_required_sources() -> None:
    """Provider rows expose configuration gaps without reading real credentials."""

    rows = provider_status_rows(Settings(_env_file=None))
    by_provider = {row["Provider"]: row for row in rows}

    assert by_provider["Trading 212"]["Status"] == "Missing"
    assert by_provider["OpenAI"]["Status"] == "Missing"
    assert by_provider["Companies House"]["Status"] == "Missing"
    assert "not a historical OHLC feed" in by_provider["Trading 212"]["Source caveat"]
    assert "point-in-time truth" in by_provider["FMP"]["Source caveat"]


def test_provider_status_marks_configured_sources() -> None:
    """Configured secrets appear as configured without exposing values."""

    rows = provider_status_rows(
        Settings(
            _env_file=None,
            trading212_api_key=SecretStr("key"),
            trading212_api_secret=SecretStr("secret"),
            openai_api_key=SecretStr("openai"),
            sec_user_agent="isa-system-test",
        )
    )
    by_provider = {row["Provider"]: row for row in rows}

    assert by_provider["Trading 212"]["Status"] == "Configured"
    assert by_provider["OpenAI"]["Status"] == "Configured"
    assert by_provider["SEC EDGAR"]["Status"] == "Configured"


def test_provider_status_marks_partial_broker_configuration() -> None:
    """A half-configured broker provider is called out without exposing values."""

    rows = provider_status_rows(Settings(_env_file=None, trading212_api_key=SecretStr("key")))
    by_provider = {row["Provider"]: row for row in rows}

    assert by_provider["Trading 212"]["Status"] == "Partial"
    assert "both Trading 212 credentials" in by_provider["Trading 212"]["Next safe action"]


def test_cache_freshness_marks_stale_broker_snapshot() -> None:
    """Broker reads from a previous market-session window are visibly stale."""

    opened_at = datetime(2026, 5, 11, 8, tzinfo=UTC)
    rows = cache_freshness_rows(
        _snapshot("demo", retrieved_at_utc=opened_at - timedelta(minutes=15)),
        _window(opened_at=opened_at, next_refresh_at=opened_at + timedelta(hours=6)),
        as_of_utc=opened_at + timedelta(hours=1),
    )
    by_item = {row["Cache item"]: row for row in rows}

    assert by_item["Market-session cache"]["Status"] == "Fresh"
    assert by_item["Market-session cache"]["Age"] == "1h 0m old"
    assert by_item["Broker snapshot"]["Status"] == "Stale"
    assert by_item["Broker snapshot"]["Age"] == "1h 15m old"
    assert "Refresh dashboard cache" in by_item["Broker snapshot"]["Next safe action"]


def test_operational_status_summarises_ready_preview_state() -> None:
    """The high-level model exposes provider, cache, broker, research, and guardrail states."""

    opened_at = datetime(2026, 5, 11, 8, tzinfo=UTC)
    rows = operational_status_rows(
        _snapshot("demo", retrieved_at_utc=opened_at + timedelta(minutes=5)),
        Settings(
            _env_file=None,
            trading212_api_key=SecretStr("key"),
            trading212_api_secret=SecretStr("secret"),
            openai_api_key=SecretStr("openai"),
        ),
        _window(opened_at=opened_at, next_refresh_at=opened_at + timedelta(hours=6)),
        as_of_utc=opened_at + timedelta(hours=1),
    )
    by_area = {row["Area"]: row for row in rows}

    assert by_area["Provider readiness"]["Status"] == "Ready"
    assert by_area["Cache freshness"]["Status"] == "Fresh"
    assert by_area["Broker read-only"]["Status"] == "Ready"
    assert by_area["Deep research"]["Status"] == "Ready"
    assert by_area["Live guardrails"]["Status"] == "Safe default"
    assert "preview-only sizing" in by_area["Next required action"]["Next safe action"]


def test_next_action_prioritises_missing_broker_credentials() -> None:
    """Missing broker setup is more urgent than optional research configuration."""

    opened_at = datetime(2026, 5, 11, 8, tzinfo=UTC)
    action = next_required_safe_action(
        _snapshot("not_configured", retrieved_at_utc=opened_at + timedelta(minutes=5)),
        Settings(_env_file=None),
        _window(opened_at=opened_at, next_refresh_at=opened_at + timedelta(hours=6)),
        as_of_utc=opened_at + timedelta(hours=1),
    )

    assert action.startswith("Configure Trading 212 read-only credentials")


def test_next_action_warns_when_live_is_armed() -> None:
    """An armed live state is surfaced as a review-required condition, not a control."""

    opened_at = datetime(2026, 5, 11, 8, tzinfo=UTC)
    action = next_required_safe_action(
        _snapshot("live", retrieved_at_utc=opened_at + timedelta(minutes=5)),
        Settings(
            _env_file=None,
            runtime_mode=RuntimeMode.LIVE,
            live_armed=True,
            kill_switch_enabled=False,
            trading212_api_key=SecretStr("key"),
            trading212_api_secret=SecretStr("secret"),
            openai_api_key=SecretStr("openai"),
        ),
        _window(opened_at=opened_at, next_refresh_at=opened_at + timedelta(hours=6)),
        as_of_utc=opened_at + timedelta(hours=1),
    )

    assert action.startswith("Live is armed")
    assert "explicit operator approval" in action


def test_safety_checklist_blocks_live_when_not_armed() -> None:
    """Management helper keeps live submission blocked by default."""

    rows = safety_checklist_rows(_snapshot("not_configured"), Settings(_env_file=None))
    by_check = {row["Check"]: row for row in rows}

    assert by_check["Broker read-only context"]["Status"] == "Needs setup"
    assert by_check["Deep research gate"]["Status"] == "Unavailable"
    assert by_check["Live submission"]["Status"] == "Blocked"


def test_safety_checklist_shows_armed_only_when_configured_that_way() -> None:
    """The checklist reflects local settings without arming anything itself."""

    rows = safety_checklist_rows(
        _snapshot("live"),
        Settings(
            _env_file=None,
            runtime_mode=RuntimeMode.LIVE,
            live_armed=True,
            kill_switch_enabled=False,
            openai_api_key=SecretStr("openai"),
        ),
    )
    by_check = {row["Check"]: row for row in rows}

    assert by_check["Broker read-only context"]["Status"] == "Ready"
    assert by_check["Deep research gate"]["Status"] == "Ready"
    assert by_check["Live submission"]["Status"] == "Armed"


def _snapshot(
    status: str,
    *,
    retrieved_at_utc: datetime = datetime(2026, 5, 11, tzinfo=UTC),
) -> BrokerPortfolioSnapshot:
    return BrokerPortfolioSnapshot(
        status=status,  # type: ignore[arg-type]
        environment="live" if status == "live" else "demo",
        retrieved_at_utc=retrieved_at_utc,
        positions=[],
        warnings=[],
    )


def _window(opened_at: datetime, next_refresh_at: datetime) -> MarketCacheWindow:
    return MarketCacheWindow(
        key="20260511-london_open",
        label="London open cache",
        opened_at_utc=opened_at,
        next_refresh_at_utc=next_refresh_at,
        manual_refresh_hint="Refresh manually when broker state changes.",
    )
