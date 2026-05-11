"""Rebalance preview and submit routes."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException

from isa_system.api.deps import ControlState, get_state
from isa_system.api.schemas import RebalancePreviewRequest, SubmitRequest
from isa_system.domain.enums import RuntimeMode
from isa_system.domain.models import TargetWeight
from isa_system.portfolio.costs import CostModel
from isa_system.portfolio.rebalancer import build_rebalance_plan
from isa_system.services.portfolio_state import load_trading212_portfolio
from isa_system.services.rebalance_preview import (
    RebalancePreviewSnapshot,
    build_preview_from_holdings,
)
from isa_system.services.valuation import value_current_holdings

router = APIRouter()


@router.post("/rebalances/preview")
def preview(request: RebalancePreviewRequest) -> dict[str, object]:
    """Create a starter rebalance preview."""

    plan = build_rebalance_plan(
        run_id=request.run_id,
        current_weights={"TSCO.L": 0.02},
        targets=[
            TargetWeight("TSCO.L", 0.04),
            TargetWeight("AAPL", 0.05),
            TargetWeight("MSFT", 0.05),
        ],
        prices={"TSCO.L": Decimal("2.90"), "AAPL": Decimal("190"), "MSFT": Decimal("420")},
        total_equity_gbp=Decimal(str(request.total_equity_gbp)),
        cost_model=CostModel(),
    )
    return {
        "run_id": plan.run_id,
        "batch_hash": plan.batch_hash,
        "estimated_total_cost": str(plan.estimated_total_cost),
        "turnover": plan.turnover,
        "warnings": list(plan.warnings),
        "trades": [trade.__dict__ | {"side": trade.side.value} for trade in plan.trades],
    }


@router.get("/rebalances/live-preview", response_model=RebalancePreviewSnapshot)
def live_preview() -> RebalancePreviewSnapshot:
    """Return a preview-only plan from the current read-only broker snapshot."""

    snapshot = load_trading212_portfolio()
    valuation = value_current_holdings(snapshot)
    return build_preview_from_holdings(snapshot, valuation)


@router.post("/rebalances/submit")
def submit(request: SubmitRequest, state: ControlState = Depends(get_state)) -> dict[str, str]:
    """Submit a paper batch or reject unsafe live submit."""

    if state.kill_switch_enabled:
        raise HTTPException(status_code=423, detail="Kill switch is enabled.")
    if request.mode == RuntimeMode.LIVE and not state.live_armed:
        raise HTTPException(status_code=403, detail="Live trading is not armed.")
    return {"status": "accepted", "batch_hash": request.batch_hash, "mode": request.mode.value}
