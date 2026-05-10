"""Tests for holdings valuation API routes."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from isa_system.api.main import app
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot, BrokerPosition
from isa_system.services.valuation import (
    HoldingValuationData,
    StaticValuationProvider,
    ValuationMetrics,
    value_current_holdings,
)


def test_holdings_valuation_endpoint_is_offline_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    """The endpoint can be exercised without broker or market-data network access."""

    def fake_snapshot() -> BrokerPortfolioSnapshot:
        return BrokerPortfolioSnapshot(
            status="live",
            environment="live",
            retrieved_at_utc=datetime(2026, 5, 10, 10, 0, tzinfo=UTC),
            positions=[
                BrokerPosition(
                    symbol="AAPL",
                    broker_ticker="AAPL_US_EQ",
                    name="Apple",
                    currency="USD",
                    quantity=3,
                    current_value=600,
                )
            ],
            warnings=[],
        )

    provider = StaticValuationProvider(
        {
            "AAPL": HoldingValuationData(
                symbol="AAPL",
                retrieved_at_utc=datetime(2026, 5, 10, 10, 1, tzinfo=UTC),
                valuation=ValuationMetrics(trailing_pe=30.0, market_cap=3_000_000_000_000),
            )
        }
    )

    monkeypatch.setattr("isa_system.api.routers.valuation.load_trading212_portfolio", fake_snapshot)
    monkeypatch.setattr(
        "isa_system.api.routers.valuation.value_current_holdings",
        lambda snapshot: value_current_holdings(snapshot, provider),
    )

    response = TestClient(app).get("/valuation/holdings")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "static"
    assert payload["holdings"][0]["symbol"] == "AAPL"
    assert payload["holdings"][0]["research_symbol"] == "AAPL"
    assert payload["holdings"][0]["valuation"]["trailing_pe"] == 30.0
    assert "retrieved_at_utc" in payload
