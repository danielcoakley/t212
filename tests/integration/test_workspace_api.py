"""Workspace widget metadata tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from isa_system.api.main import app


def test_widgets_json_returns_valid_metadata_without_openbb() -> None:
    """Workspace metadata is local and does not require OpenBB."""

    response = TestClient(app).get("/workspace/widgets.json")

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "ISA Portfolio Intelligence"
    assert any(widget["id"] == "ranked-candidates" for widget in payload["widgets"])


def test_key_widget_endpoints_exist() -> None:
    """Key widget target endpoints are registered."""

    paths = TestClient(app).get("/openapi.json").json()["paths"]

    for endpoint in [
        "/scores/latest",
        "/candidates/top10",
        "/thesis/watchlist",
        "/portfolio/holdings",
        "/rebalance/latest",
        "/workspace/risk-warnings",
        "/research/reports/latest",
    ]:
        assert endpoint in paths
