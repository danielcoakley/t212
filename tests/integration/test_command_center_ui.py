"""Integration tests for the FastAPI-served command centre dashboard."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from isa_system.api.main import app
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot, BrokerPosition


def test_command_centre_root_serves_workflow_dashboard() -> None:
    """The API root serves the new workflow command centre UI."""

    response = TestClient(app).get("/")

    assert response.status_code == 200
    assert "Workflow Command Center" in response.text
    assert 'data-page="screener">Screener</a>' in response.text
    assert "Finviz Screener" not in response.text
    assert "Discovery workbench" not in response.text
    assert "Tune discovery filters" not in response.text
    assert "Fixture Run" not in response.text
    assert "My Presets" in response.text
    assert "Columns" in response.text
    assert "Open current screen in Finviz" in response.text
    assert 'data-page="screener"' in response.text
    assert 'data-page="research"' not in response.text
    assert "Holdings health report" in response.text
    assert "Live trading not implemented" in response.text


def test_dashboard_assets_are_served() -> None:
    """Static CSS and JS assets are served by FastAPI."""

    client = TestClient(app)

    assert client.get("/dashboard-assets/styles.css").status_code == 200
    js_response = client.get("/dashboard-assets/app.js")
    assert js_response.status_code == 200
    assert "/health-check/run" in js_response.text
    assert "/discovery/finviz/screener" in js_response.text
    assert "sort-screener" in js_response.text
    assert "add-custom-column" in js_response.text


def test_load_broker_holdings_maps_read_only_positions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Portfolio review can load current broker holdings without live order authority."""

    snapshot = BrokerPortfolioSnapshot(
        status="demo",
        environment="demo",
        retrieved_at_utc=datetime(2026, 5, 12, 9, tzinfo=UTC),
        account_currency="GBP",
        total_value=1_000.0,
        positions=[
            BrokerPosition(
                symbol="GOOD.L",
                broker_ticker="GOODl_EQ",
                name="Good Plc",
                currency="GBP",
                quantity=5,
                average_price_paid=90.0,
                current_price=100.0,
                current_value=500.0,
            )
        ],
        warnings=[],
    )
    monkeypatch.setattr(
        "isa_system.api.routers.portfolio_manager.load_trading212_portfolio",
        lambda force_refresh=False: snapshot,
    )

    response = TestClient(app).post("/portfolio/holdings/load-broker")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["symbol"] == "GOOD.L"
    assert payload[0]["market_value"] == 500.0
    assert payload[0]["current_weight"] == 0.5
    assert "Trading 212 read-only" in payload[0]["notes"]
