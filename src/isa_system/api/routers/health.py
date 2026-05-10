"""Health and metrics routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from isa_system.api.deps import ControlState, get_state
from isa_system.api.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health(state: ControlState = Depends(get_state)) -> HealthResponse:
    """Return local subsystem status."""

    return HealthResponse(
        status="ok",
        mode=state.mode,
        live_armed=state.live_armed,
        kill_switch_enabled=state.kill_switch_enabled,
        subsystems={"database": "ok", "broker": "not_configured_ok", "data_lake": "ok"},
    )


@router.get("/metrics")
def metrics() -> dict[str, float | str]:
    """Return starter process metrics."""

    return {"status": "ok", "pending_order_batches": 0, "stale_data_warnings": 0}
