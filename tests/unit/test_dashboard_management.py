"""Tests for the read-only dashboard management status helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import SecretStr

from isa_system.dashboard.pages.management import provider_status_rows, safety_checklist_rows
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


def _snapshot(status: str) -> BrokerPortfolioSnapshot:
    return BrokerPortfolioSnapshot(
        status=status,  # type: ignore[arg-type]
        environment="live" if status == "live" else "demo",
        retrieved_at_utc=datetime(2026, 5, 11, tzinfo=UTC),
        positions=[],
        warnings=[],
    )
