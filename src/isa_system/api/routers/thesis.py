"""Investment thesis API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from isa_system.api.routers.enrichment import latest_enrichment_packets
from isa_system.api.routers.scores import latest_score_snapshot
from isa_system.thesis.lifecycle import ThesisLifecycleService
from isa_system.thesis.models import Thesis
from isa_system.thesis.thesis_generator import ThesisGenerator
from isa_system.thesis.thesis_tracker import ThesisTracker

router = APIRouter(prefix="/thesis", tags=["thesis"])


@router.post("/generate/{symbol}", response_model=Thesis)
def generate_thesis(symbol: str) -> Thesis:
    """Generate and persist a thesis for a scored symbol."""

    score = _score_for_symbol(symbol)
    packet = latest_enrichment_packets().get(symbol.upper())
    thesis = ThesisGenerator().generate(score, packet)
    return ThesisTracker().save(thesis)


@router.get("/watchlist", response_model=list[Thesis])
def thesis_watchlist() -> list[Thesis]:
    """Return tracked watchlist theses."""

    lifecycle = ThesisLifecycleService()
    return ThesisTracker().list_by_status(lifecycle.watchlist_statuses)


@router.get("/active", response_model=list[Thesis])
def active_theses() -> list[Thesis]:
    """Return active holding theses."""

    lifecycle = ThesisLifecycleService()
    return ThesisTracker().list_by_status(lifecycle.active_statuses)


@router.get("/{symbol}", response_model=Thesis | None)
def get_thesis(symbol: str) -> Thesis | None:
    """Return the latest thesis for a symbol."""

    return ThesisTracker().latest_for_symbol(symbol)


@router.post("/review/{symbol}", response_model=Thesis)
def review_thesis(symbol: str) -> Thesis:
    """Regenerate and persist a thesis review for a symbol."""

    return generate_thesis(symbol)


def _score_for_symbol(symbol: str):
    for score in latest_score_snapshot():
        if score.symbol == symbol.upper():
            return score
    raise HTTPException(status_code=404, detail=f"No score found for {symbol.upper()}.")
