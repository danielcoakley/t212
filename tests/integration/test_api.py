"""FastAPI integration tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from isa_system.api.main import app


def test_health_and_preview() -> None:
    """Health and preview endpoints work offline."""

    client = TestClient(app)
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    preview = client.post("/rebalances/preview", json={"run_id": "test", "total_equity_gbp": 10000})
    assert preview.status_code == 200
    assert "batch_hash" in preview.json()


def test_live_submit_requires_arm() -> None:
    """Live submit is rejected unless armed."""

    client = TestClient(app)
    client.post("/modes/live")
    response = client.post("/rebalances/submit", json={"batch_hash": "abc", "mode": "live"})
    assert response.status_code == 403
