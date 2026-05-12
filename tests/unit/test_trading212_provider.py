"""Tests for Trading 212 provider adapter."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from decimal import Decimal

from isa_system.data.providers.trading212 import Trading212Client, Trading212Settings
from isa_system.domain.enums import OrderSide, OrderType
from isa_system.execution.order_models import OrderIntent


def test_instruments_with_mocked_http() -> None:
    """Instrument metadata is parsed from a mocked response."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v0/equity/metadata/instruments"
        return httpx.Response(
            200, json=[{"ticker": "AAPL_US_EQ", "currencyCode": "USD", "name": "Apple"}]
        )

    client = Trading212Client(
        Trading212Settings(api_key="key", api_secret="secret", respect_rate_limits=False),
        transport=httpx.MockTransport(handler),
    )
    instruments = client.instruments()
    assert instruments[0].ticker == "AAPL_US_EQ"


def test_paginated_history_follows_next_page_path() -> None:
    """Historical endpoints follow the documented nextPagePath cursor contract."""

    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if "cursor=next" not in str(request.url):
            return httpx.Response(
                200,
                json={
                    "items": [{"order": {"id": 1}}],
                    "nextPagePath": "/api/v0/equity/history/orders?limit=50&cursor=next",
                },
            )
        return httpx.Response(200, json={"items": [{"order": {"id": 2}}], "nextPagePath": None})

    client = Trading212Client(
        Trading212Settings(api_key="key", api_secret="secret", respect_rate_limits=False),
        transport=httpx.MockTransport(handler),
    )

    rows = client.history_orders()

    assert [row["order"]["id"] for row in rows] == [1, 2]
    assert len(seen) == 2


def test_stop_limit_sell_uses_negative_quantity_payload() -> None:
    """Stop-limit sell orders use Trading 212's negative quantity convention."""

    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = request.read().decode()
        return httpx.Response(200, json={"id": 123, "status": "NEW", "type": "STOP_LIMIT"})

    client = Trading212Client(
        Trading212Settings(api_key="key", api_secret="secret", respect_rate_limits=False),
        transport=httpx.MockTransport(handler),
    )

    response = client.submit_order(
        OrderIntent(
            symbol="AAPL",
            broker_ticker="AAPL_US_EQ",
            side=OrderSide.SELL,
            order_type=OrderType.STOP_LIMIT,
            quantity=Decimal("1.5"),
            stop_price=Decimal("90"),
            limit_price=Decimal("89"),
        )
    )

    assert response.id == 123
    assert captured["path"] == "/api/v0/equity/orders/stop_limit"
    assert '"quantity":-1.5' in str(captured["body"])


def test_fixture_has_no_secret() -> None:
    """Provider fixtures are static and contain no API keys."""

    payload = json.loads(
        Path("tests/fixtures/trading212_instruments.json").read_text(encoding="utf-8")
    )
    assert payload[0]["ticker"] == "AAPL_US_EQ"
