"""Tests for audit API route."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from isa_system.api.main import app
from isa_system.services.audit_status import AuditStatusSnapshot


def test_audit_endpoint_returns_status(monkeypatch: pytest.MonkeyPatch) -> None:
    """The audit endpoint returns structured operator status."""

    monkeypatch.setattr(
        "isa_system.api.routers.audit.load_audit_status",
        lambda: AuditStatusSnapshot(
            retrieved_at_utc=datetime(2026, 5, 10, tzinfo=UTC),
            mode="preview",
            live_armed=False,
            kill_switch_enabled=False,
            broker_status="live",
            broker_environment="live",
            broker_position_count=6,
            broker_warning_count=0,
            audit_log_count=0,
            latest_audit_logs=[],
            smoke_artifacts=[],
            warnings=[],
        ),
    )

    response = TestClient(app).get("/audit")

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "preview"
    assert payload["broker_position_count"] == 6
    assert payload["latest_audit_logs"] == []
