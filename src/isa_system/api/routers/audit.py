"""Audit routes."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/audit")
def audit() -> list[dict[str, str]]:
    """Return starter audit rows."""

    return [{"actor": "system", "action": "startup", "outcome": "ok"}]
