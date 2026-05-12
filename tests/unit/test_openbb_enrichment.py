"""OpenBB enrichment tests."""

from __future__ import annotations

import httpx

from isa_system.enrichment.enrichment_packet import EnrichmentService, load_fixture_enrichment
from isa_system.enrichment.openbb_client import OpenBBClient


def test_openbb_client_mocked_price_response_and_cache() -> None:
    """OpenBB client uses configured routes and caches per-run section responses."""

    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        assert request.url.path == "/api/v1/equity/price/historical"
        assert request.url.params["symbol"] == "MSFT"
        return httpx.Response(200, json=[{"date": "2026-05-11", "close": 110.0}])

    client = OpenBBClient(client=httpx.Client(transport=httpx.MockTransport(handler)))

    first = client.get_section("price_history", "MSFT")
    second = client.get_section("price_history", "MSFT")

    assert first.status == "ok"
    assert second.data == first.data
    assert calls["count"] == 1


def test_openbb_unavailable_creates_missing_packet() -> None:
    """Unavailable OpenBB sections do not crash packet creation."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    client = OpenBBClient(client=httpx.Client(transport=httpx.MockTransport(handler)))

    packet = EnrichmentService(client=client).enrich_symbol("MSFT")

    assert packet.symbol == "MSFT"
    assert packet.price is None
    assert "price_history" in packet.missing_sections
    assert packet.data_quality["score"] < 50


def test_mocked_price_and_fundamentals_response_create_packet() -> None:
    """Mocked section responses populate packet fields."""

    fixture = load_fixture_enrichment("MSFT")

    packet = EnrichmentService().enrich_symbol("MSFT", fixture_data=fixture)

    assert packet.company_name == "Microsoft Corporation"
    assert packet.price == 110.0
    assert packet.price_history_summary["return_pct"] == 10.0
    assert packet.fundamentals["revenue_growth"] == 0.14
    assert packet.valuation["pe_ratio"] == 34.2


def test_missing_data_quality_explanations() -> None:
    """Partial fixture data records missing sections explicitly."""

    packet = EnrichmentService().enrich_symbol(
        "MSFT",
        fixture_data={"price_history": [{"date": "2026-05-11", "close": 10}]},
    )

    assert "fundamentals" in packet.missing_sections
    assert packet.data_quality["present_sections"] == 1
    assert packet.data_quality["attempted_sections"] >= 8
    assert packet.data_quality["explanations"]
