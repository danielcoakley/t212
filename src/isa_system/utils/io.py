"""File I/O helpers used by scripts and smoke tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def ensure_directory(path: Path) -> Path:
    """Create and return a directory."""

    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, payload: Any) -> Path:
    """Write JSON with deterministic formatting."""

    ensure_directory(path.parent)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return path


def read_json(path: Path) -> Any:
    """Read a JSON document."""

    return json.loads(path.read_text(encoding="utf-8"))
