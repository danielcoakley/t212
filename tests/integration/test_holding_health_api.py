"""Integration tests for holdings health-check routes."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from isa_system.api.main import app
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot, BrokerPosition
from isa_system.services.valuation import HoldingsValuationResponse, HoldingValuation
from isa_system.settings import Settings


def test_health_check_routes_run_store_and_accept(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The API can run a health report and store accepted target/action updates."""

    settings = Settings(
        _env_file=None,
        operational_db_dsn=f"sqlite:///{tmp_path / 'api-health.sqlite3'}",
    )
    snapshot = _snapshot()
    valuation = _valuation(snapshot)
    monkeypatch.setattr("isa_system.api.routers.holding_health.get_settings", lambda: settings)
    monkeypatch.setattr(
        "isa_system.api.routers.holding_health.load_trading212_portfolio",
        lambda force_refresh=False: snapshot,
    )
    monkeypatch.setattr(
        "isa_system.api.routers.holding_health.value_current_holdings",
        lambda snapshot: valuation,
    )

    client = TestClient(app)
    run_response = client.post("/health-check/run")

    assert run_response.status_code == 200
    payload = run_response.json()
    report_id = payload["report"]["id"]
    assert payload["report"]["status"] == "DETERMINISTIC_FALLBACK"
    assert payload["report"]["assessments"][0]["symbol"] == "GOOD.L"

    latest_response = client.get("/health-check/latest")
    assert latest_response.status_code == 200
    assert latest_response.json()["report"]["id"] == report_id

    accept_response = client.post(
        f"/health-check/reports/{report_id}/holdings/GOOD.L/accept",
        json={
            "price_targets": {"bear": 85, "base": 130, "bull": 175},
            "carried_forward_action": "BUY_MORE",
            "notes": "Accepted after manual review.",
        },
    )
    assert accept_response.status_code == 200
    assert accept_response.json()["adjusted"] is True

    report_response = client.get(f"/health-check/reports/{report_id}")
    assert report_response.status_code == 200
    report_payload = report_response.json()
    assert report_payload["updates"][0]["accepted_price_targets"]["base"] == 130.0
    assert report_payload["updates"][0]["carried_forward_action"] == "BUY_MORE"


def _snapshot() -> BrokerPortfolioSnapshot:
    generated = datetime(2026, 5, 12, 9, tzinfo=UTC)
    return BrokerPortfolioSnapshot(
        status="demo",
        environment="demo",
        retrieved_at_utc=generated,
        account_currency="GBP",
        total_value=1_000.0,
        positions=[
            BrokerPosition(
                symbol="GOOD.L",
                broker_ticker="GOODl_EQ",
                name="Good Plc",
                isin="GB00GOOD0001",
                currency="GBP",
                quantity=10,
                average_price_paid=90.0,
                current_price=100.0,
                current_value=1_000.0,
            )
        ],
        warnings=[],
    )


def _valuation(snapshot: BrokerPortfolioSnapshot) -> HoldingsValuationResponse:
    generated = datetime(2026, 5, 12, 9, tzinfo=UTC)
    return HoldingsValuationResponse(
        status=snapshot.status,
        environment=snapshot.environment,
        retrieved_at_utc=generated,
        provider="static",
        holdings=[
            HoldingValuation(
                symbol="GOOD.L",
                broker_ticker="GOODl_EQ",
                research_symbol="GOOD.L",
                name="Good Plc",
                currency="GBP",
                quantity=10,
                current_price=100.0,
                current_value=1_000.0,
                valuation={},
                technicals={},
                upcoming_events=[],
                news=[],
                warnings=[],
            )
        ],
        warnings=[],
    )
