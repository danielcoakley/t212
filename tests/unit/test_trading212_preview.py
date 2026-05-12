"""Trading 212 read-only/order-preview tests."""

from __future__ import annotations

import httpx

from isa_system.settings import Settings
from isa_system.trading212.client import Trading212ReadOnlyClient
from isa_system.trading212.models import OrderPreviewRequest
from isa_system.trading212.order_preview import create_order_preview


def test_trading212_api_key_optional() -> None:
    """Broker account read works safely without an API key."""

    client = Trading212ReadOnlyClient(settings=Settings(_env_file=None))

    account = client.account_summary()

    assert account.status == "not_configured"
    assert account.warnings


def test_mocked_account_response() -> None:
    """Read-only account summary can be loaded from a mocked response."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v0/equity/account/summary"
        return httpx.Response(
            200, json={"currency": "GBP", "totalValue": 1000, "cash": {"free": 50}}
        )

    settings = Settings(_env_file=None, trading212_api_key="test")
    client = Trading212ReadOnlyClient(
        settings=settings,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    account = client.account_summary()

    assert account.status == "ok"
    assert account.total_value == 1000
    assert account.cash == 50


def test_mocked_positions_response() -> None:
    """Read-only positions can be loaded from a mocked response."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v0/equity/positions"
        return httpx.Response(
            200,
            json=[
                {"ticker": "MSFT_EQ", "quantity": 2, "averagePricePaid": 100, "currentPrice": 110}
            ],
        )

    settings = Settings(_env_file=None, trading212_api_key="test")
    client = Trading212ReadOnlyClient(
        settings=settings,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    positions = client.positions()

    assert positions[0].ticker == "MSFT_EQ"
    assert positions[0].quantity == 2


def test_order_preview_requires_manual_approval_and_hash_is_deterministic() -> None:
    """Order previews are deterministic and require manual approval."""

    request = OrderPreviewRequest(
        symbol="MSFT",
        side="BUY",
        estimated_trade_value=550,
        current_price=110,
        currency="USD",
        target_weight=0.04,
    )

    first = create_order_preview(request)
    second = create_order_preview(request)

    assert first.manual_approval_required is True
    assert first.quantity == 5
    assert first.estimated_fx_impact > 0
    assert first.duplicate_order_hash == second.duplicate_order_hash
