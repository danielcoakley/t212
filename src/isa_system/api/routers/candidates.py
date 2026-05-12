"""Candidate API routes."""

from __future__ import annotations

from fastapi import APIRouter

from isa_system.api.routers.discovery import latest_discovery_result
from isa_system.discovery.models import Candidate

router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.get("/latest", response_model=list[Candidate])
def latest_candidates() -> list[Candidate]:
    """Return candidates from the latest discovery run."""

    latest = latest_discovery_result()
    if latest is None:
        return []
    return latest.candidates
