"""Tests for live read-only rebalance preview API route."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from isa_system.api.main import app
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot, BrokerPosition
from isa_system.services.valuation import HoldingsValuationResponse


def test_live_rebalance_preview_endpoint_is_preview_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The live preview endpoint uses read-only broker data and remains blocked."""

    snapshot = BrokerPortfolioSnapshot(
        status="live",
        environment="live",
        retrieved_at_utc=datetime(2026, 5, 11, tzinfo=UTC),
        account_currency="GBP",
        total_value=1000,
        positions=[
            BrokerPosition(
                symbol="AAPL_US_EQ",
                broker_ticker="AAPL_US_EQ",
                currency="USD",
                quantity=2,
                current_value=900,
            )
        ],
        warnings=[],
    )
    monkeypatch.setattr(
        "isa_system.api.routers.rebalances.load_trading212_portfolio", lambda: snapshot
    )
    monkeypatch.setattr(
        "isa_system.api.routers.rebalances.value_current_holdings",
        lambda broker_snapshot: HoldingsValuationResponse(
            status=broker_snapshot.status,
            environment=broker_snapshot.environment,
            retrieved_at_utc=broker_snapshot.retrieved_at_utc,
            provider="static",
            holdings=[],
            warnings=[],
        ),
    )

    response = TestClient(app).get("/rebalances/live-preview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "preview"
    assert payload["rows"][0]["status"] in {"preview_blocked", "below_min_trade", "hold"}
    assert payload["risk_checks"]


def test_paper_simulation_endpoint_is_local_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """The paper simulation endpoint returns local fill rows from preview assumptions."""

    snapshot = BrokerPortfolioSnapshot(
        status="live",
        environment="live",
        retrieved_at_utc=datetime(2026, 5, 11, tzinfo=UTC),
        account_currency="GBP",
        total_value=1000,
        positions=[
            BrokerPosition(
                symbol="AAPL_US_EQ",
                broker_ticker="AAPL_US_EQ",
                currency="USD",
                quantity=2,
                current_value=900,
            )
        ],
        warnings=[],
    )
    monkeypatch.setattr(
        "isa_system.api.routers.rebalances.load_trading212_portfolio", lambda: snapshot
    )
    monkeypatch.setattr(
        "isa_system.api.routers.rebalances.value_current_holdings",
        lambda broker_snapshot: HoldingsValuationResponse(
            status=broker_snapshot.status,
            environment=broker_snapshot.environment,
            retrieved_at_utc=broker_snapshot.retrieved_at_utc,
            provider="static",
            holdings=[],
            warnings=[],
        ),
    )

    response = TestClient(app).get("/rebalances/paper-simulation")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_batch_hash"]
    assert "no order is sent" in payload["warnings"][0]
