"""Thesis API tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from isa_system.api.main import app


def test_top10_candidate_can_generate_thesis(monkeypatch, tmp_path) -> None:
    """A scored candidate can generate and persist a thesis through the API."""

    monkeypatch.setenv("ISA_OPERATIONAL_DB_DSN", f"sqlite:///{tmp_path / 'api-thesis.sqlite3'}")
    from isa_system.settings import clear_settings_cache

    clear_settings_cache()

    client = TestClient(app)
    client.post("/discovery/run", json={"use_fixtures": True})
    client.post("/enrichment/run", json={"symbols": ["MSFT"], "use_fixtures": True})
    client.post("/scores/run", json={"limit": 10})

    response = client.post("/thesis/generate/MSFT")
    watchlist = client.get("/thesis/watchlist")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "MSFT"
    assert payload["decision"] in {
        "BUY_NOW",
        "WATCHLIST_WAIT_ENTRY",
        "WATCHLIST_WAIT_CATALYST",
        "REJECT",
    }
    assert watchlist.status_code == 200

    clear_settings_cache()
