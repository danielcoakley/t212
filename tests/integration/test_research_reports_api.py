"""Structured research report API tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from isa_system.api.main import app


def test_top10_research_run_creates_reports_and_retains_watchlist(monkeypatch, tmp_path) -> None:
    """Top 10 research reports can be generated offline and thesis remains tracked."""

    monkeypatch.setenv("ISA_OPERATIONAL_DB_DSN", f"sqlite:///{tmp_path / 'research.sqlite3'}")
    monkeypatch.setenv("ISA_ARTIFACTS_PATH", str(tmp_path / "artifacts"))
    from isa_system.settings import clear_settings_cache

    clear_settings_cache()
    client = TestClient(app)
    client.post("/discovery/run", json={"use_fixtures": True})
    client.post("/enrichment/run", json={"symbols": ["MSFT", "NVDA"], "use_fixtures": True})
    client.post("/scores/run", json={"limit": 10})
    client.post("/thesis/generate/MSFT")

    response = client.post("/research/run-top10")
    latest = client.get("/research/reports/latest")
    thesis = client.get("/thesis/MSFT")

    assert response.status_code == 200
    assert latest.status_code == 200
    assert response.json()
    assert latest.json()
    assert thesis.json()["latest_report_id"] is not None

    clear_settings_cache()
