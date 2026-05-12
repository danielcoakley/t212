"""Phase 0 portfolio intelligence API checks on the unified ISA app."""

from __future__ import annotations

from fastapi.testclient import TestClient

from isa_system.api.main import app


def test_health_is_local_and_openbb_independent() -> None:
    """Health must work even when OpenBB is offline or absent."""

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["subsystems"]["openbb"] == "not_checked"
    assert payload["subsystems"]["live_trading"] == "not_implemented"
