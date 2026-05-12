"""Workspace metadata routes."""

from __future__ import annotations

from fastapi import APIRouter

from isa_system.workspace.apps_json import workspace_apps_json

router = APIRouter(prefix="/workspace", tags=["workspace"])


@router.get("/widgets.json")
def widgets_json() -> dict[str, object]:
    """Return local widget metadata for Workspace-style consumption."""

    return workspace_apps_json()


@router.get("/risk-warnings")
def risk_warnings() -> list[dict[str, str]]:
    """Return current high-level risk warnings."""

    return [
        {"severity": "info", "message": "Live trading is not implemented."},
        {"severity": "info", "message": "All rebalance proposals require manual approval."},
        {"severity": "info", "message": "OpenBB and Finviz data may be missing or stale."},
    ]
