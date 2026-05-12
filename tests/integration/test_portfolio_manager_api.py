"""Portfolio manager API tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from isa_system.api.main import app


def test_portfolio_manager_routes_return_manual_review_outputs(monkeypatch, tmp_path) -> None:
    """Portfolio manager endpoints expose holdings and proposal state."""

    monkeypatch.setenv("ISA_OPERATIONAL_DB_DSN", f"sqlite:///{tmp_path / 'portfolio.sqlite3'}")
    from isa_system.settings import clear_settings_cache

    clear_settings_cache()
    client = TestClient(app)

    holdings = client.post("/portfolio/holdings/load-example")
    proposals = client.post("/rebalance/propose", json={"cash_gbp": 5000})
    latest = client.get("/portfolio/actions/latest")

    assert holdings.status_code == 200
    assert proposals.status_code == 200
    assert latest.status_code == 200
    assert isinstance(latest.json(), list)

    clear_settings_cache()
