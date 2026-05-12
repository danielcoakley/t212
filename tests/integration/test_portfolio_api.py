"""Tests for read-only portfolio analytics API routes."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from isa_system.api.main import app
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot, BrokerPosition


def test_portfolio_summary_endpoint_is_read_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """The summary endpoint returns analytics without touching a live broker in tests."""

    def fake_snapshot() -> BrokerPortfolioSnapshot:
        return BrokerPortfolioSnapshot(
            status="live",
            environment="live",
            retrieved_at_utc=datetime(2026, 5, 10, 10, 0, tzinfo=UTC),
            account_currency="GBP",
            total_value=2_500.0,
            available_to_trade=500.0,
            reserved_for_orders=0.0,
            positions=[
                BrokerPosition(
                    symbol="SHEL.L",
                    broker_ticker="SHEL_GB_EQ",
                    name="Shell",
                    currency="GBP",
                    quantity=25.0,
                    current_value=1_000.0,
                    unrealised_profit_loss=40.0,
                )
            ],
            warnings=[],
        )

    monkeypatch.setattr("isa_system.api.routers.portfolio.load_trading212_portfolio", fake_snapshot)

    response = TestClient(app).get("/portfolio/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "live"
    assert payload["total_value"] == 2_500.0
    assert payload["cash_fraction"] == 0.2
    assert payload["concentration"]["max_position_weight"] == 0.4
    assert payload["currency_exposure"] == [
        {"currency": "GBP", "current_value": 1_000.0, "weight": 0.4}
    ]
    assert payload["top_positions"][0]["symbol"] == "SHEL.L"


def test_deep_valuation_endpoint_rejects_empty_selection() -> None:
    """The API does not run selected-stock valuation without selected symbols."""

    response = TestClient(app).post(
        "/portfolio/deep-valuation",
        json={"symbols": [], "maximum_depth": False, "source_heavy": False},
    )

    assert response.status_code == 400
    assert "Select at least one stock" in response.json()["detail"]
