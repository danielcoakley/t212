"""Portfolio and catalyst read routes."""

from __future__ import annotations

from fastapi import APIRouter

from isa_system.services.portfolio_state import load_trading212_portfolio

router = APIRouter()


@router.get("/positions")
def positions() -> list[dict[str, object]]:
    """Return live broker positions when configured."""

    snapshot = load_trading212_portfolio()
    if snapshot.positions:
        return [position.model_dump(mode="json") for position in snapshot.positions]
    return [{"symbol": "TSCO.L", "weight": 0.02, "stale": False, "source": snapshot.status}]


@router.get("/holdings")
def holdings() -> list[dict[str, object]]:
    """Return live holdings with starter rationale columns."""

    snapshot = load_trading212_portfolio()
    if snapshot.positions:
        return [
            {
                **position.model_dump(mode="json"),
                "score": None,
                "rank": None,
                "rationale": "live broker holding",
            }
            for position in snapshot.positions
        ]
    return [
        {
            "symbol": "TSCO.L",
            "score": 0.42,
            "rank": 3,
            "rationale": "quality and dividend stability",
            "source": snapshot.status,
        }
    ]


@router.get("/catalysts/upcoming")
def catalysts() -> list[dict[str, str]]:
    """Return sample catalyst rows."""

    return [{"symbol": "AAPL", "event_type": "earnings", "date": "synthetic"}]
