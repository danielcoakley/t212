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


@router.post("/rebalances/submit")
def submit(request: SubmitRequest, state: ControlState = Depends(get_state)) -> dict[str, str]:
    """Submit a paper batch or reject unsafe live submit."""

    if state.kill_switch_enabled:
        raise HTTPException(status_code=423, detail="Kill switch is enabled.")
    if request.mode == RuntimeMode.LIVE and not state.live_armed:
        raise HTTPException(status_code=403, detail="Live trading is not armed.")
    return {"status": "accepted", "batch_hash": request.batch_hash, "mode": request.mode.value}
