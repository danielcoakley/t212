"""Scoring API routes."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from isa_system.api.routers.discovery import latest_discovery_result
from isa_system.api.routers.enrichment import latest_enrichment_packets
from isa_system.scoring.composite_score import CompositeScore
from isa_system.scoring.ranking import RankingService

router = APIRouter(tags=["scores"])

_LATEST_SCORES: list[CompositeScore] = []


class ScoreRunRequest(BaseModel):
    """Request to score the latest candidate set."""

    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=10, ge=1, le=100)


@router.post("/scores/run", response_model=list[CompositeScore])
def run_scores(request: ScoreRunRequest | None = None) -> list[CompositeScore]:
    """Score the latest discovered candidates using latest enrichment packets."""

    global _LATEST_SCORES
    request = request or ScoreRunRequest()
    latest = latest_discovery_result()
    candidates = [] if latest is None else latest.candidates
    _LATEST_SCORES = RankingService().top_n(
        candidates,
        latest_enrichment_packets(),
        limit=request.limit,
    )
    return _LATEST_SCORES


@router.get("/scores/latest", response_model=list[CompositeScore])
def latest_scores() -> list[CompositeScore]:
    """Return the latest score snapshot."""

    return _LATEST_SCORES


@router.get("/candidates/top10", response_model=list[CompositeScore])
def top10_candidates() -> list[CompositeScore]:
    """Return the latest top 10 candidate scores."""

    return _LATEST_SCORES[:10]


def latest_score_snapshot() -> list[CompositeScore]:
    """Return latest scores for later phases."""

    return _LATEST_SCORES
