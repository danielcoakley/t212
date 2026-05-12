"""Scoring API tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from isa_system.api.main import app


def test_scores_run_produces_top10_from_fixture_data() -> None:
    """Discovery, enrichment, and scoring produce ranked candidates offline."""

    client = TestClient(app)
    client.post("/discovery/run", json={"use_fixtures": True})
    client.post("/enrichment/run", json={"symbols": ["MSFT", "NVDA"], "use_fixtures": True})

    response = client.post("/scores/run", json={"limit": 10})
    top10 = client.get("/candidates/top10")

    assert response.status_code == 200
    assert top10.status_code == 200
    payload = response.json()
    assert payload
    assert payload[0]["explanation"]
    assert len(top10.json()) <= 10
