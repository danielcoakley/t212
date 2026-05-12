"""Workspace app metadata payload."""

from __future__ import annotations

from typing import Any

from isa_system.workspace.widgets import workspace_widgets


def workspace_apps_json() -> dict[str, Any]:
    """Return a simple OpenBB-style backend metadata payload."""

    return {
        "name": "ISA Portfolio Intelligence",
        "version": "0.1.0",
        "widgets": [widget.model_dump() for widget in workspace_widgets()],
    }
