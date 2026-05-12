"""Enrichment API tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from isa_system.api.main import app
from isa_system.enrichment.openbb_client import OpenBBHealth


def test_enrichment_run_from_fixture_data() -> None:
    """API enrichment can run offline with fixture data."""

    client = TestClient(app)

    response = client.post("/enrichment/run", json={"symbols": ["MSFT"], "use_fixtures": True})
    latest = client.get("/enrichment/MSFT")

    assert response.status_code == 200
    assert latest.status_code == 200
    payload = response.json()[0]
    assert payload["symbol"] == "MSFT"
    assert payload["company_name"] == "Microsoft Corporation"
    assert latest.json()["price"] == 110.0


def test_openbb_health_endpoint_reports_status(monkeypatch) -> None:
    """OpenBB health endpoint reports wrapper status."""

    class FakeOpenBBClient:
        def health_check(self) -> OpenBBHealth:
            return OpenBBHealth(
                available=False,
                base_url="http://127.0.0.1:6900",
                openapi="unavailable",
                widgets="unavailable",
                error="offline",
            )

    monkeypatch.setattr("isa_system.api.routers.enrichment.OpenBBClient", FakeOpenBBClient)

    response = TestClient(app).get("/health/openbb")

    assert response.status_code == 200
    assert response.json()["available"] is False
