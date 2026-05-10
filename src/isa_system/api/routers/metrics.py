"""Portfolio and catalyst read routes."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/positions")
def positions() -> list[dict[str, object]]:
    """Return sample positions."""

    return [{"symbol": "TSCO.L", "weight": 0.02, "stale": False}]


@router.get("/holdings")
def holdings() -> list[dict[str, object]]:
    """Return sample holdings with rationale columns."""

    return [
        {
            "symbol": "TSCO.L",
            "score": 0.42,
            "rank": 3,
            "rationale": "quality and dividend stability",
        }
    ]


@router.get("/catalysts/upcoming")
def catalysts() -> list[dict[str, str]]:
    """Return sample catalyst rows."""

    return [{"symbol": "AAPL", "event_type": "earnings", "date": "synthetic"}]
