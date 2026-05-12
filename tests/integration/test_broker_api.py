"""Broker read-only and order preview API tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from isa_system.api.main import app


def test_broker_account_positions_and_order_preview_without_keys() -> None:
    """Broker routes are safe without Trading 212 credentials."""

    client = TestClient(app)

    account = client.get("/broker/account")
    positions = client.get("/broker/positions")
    preview = client.post(
        "/orders/preview",
        json={
            "symbol": "MSFT",
            "side": "BUY",
            "estimated_trade_value": 550,
            "current_price": 110,
            "currency": "USD",
            "target_weight": 0.04,
        },
    )

    assert account.status_code == 200
    assert positions.status_code == 200
    assert preview.status_code == 200
    assert preview.json()["manual_approval_required"] is True


def test_no_live_order_submission_route_exists() -> None:
    """There is no live order submission endpoint in this build."""

    response = TestClient(app).post(
        "/rebalances/submit", json={"batch_hash": "abc", "mode": "live"}
    )

    assert response.status_code == 404
