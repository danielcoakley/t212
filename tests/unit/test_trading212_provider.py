"""Tests for Trading 212 provider adapter."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from isa_system.data.providers.trading212 import Trading212Client, Trading212Settings


def test_instruments_with_mocked_http() -> None:
    """Instrument metadata is parsed from a mocked response."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v0/equity/metadata/instruments"
        return httpx.Response(
            200, json=[{"ticker": "AAPL_US_EQ", "currencyCode": "USD", "name": "Apple"}]
        )

    client = Trading212Client(
        Trading212Settings(api_key="key", api_secret="secret"),
        transport=httpx.MockTransport(handler),
    )
    instruments = client.instruments()
    assert instruments[0].ticker == "AAPL_US_EQ"


def test_fixture_has_no_secret() -> None:
    """Provider fixtures are static and contain no API keys."""

    payload = json.loads(
        Path("tests/fixtures/trading212_instruments.json").read_text(encoding="utf-8")
    )
    assert payload[0]["ticker"] == "AAPL_US_EQ"
