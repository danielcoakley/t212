"""Health and metrics routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from isa_system.api.deps import ControlState, get_state
from isa_system.api.schemas import HealthResponse
from isa_system.settings import get_settings

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health(state: ControlState = Depends(get_state)) -> HealthResponse:
    """Return local subsystem status."""

    settings = get_settings()
    broker_status = (
        f"configured_{settings.trading212_environment}_read_only"
        if settings.trading212_api_key and settings.trading212_api_secret
        else "not_configured_ok"
    )
    return HealthResponse(
        status="ok",
        mode=state.mode,
        live_armed=state.live_armed,
        kill_switch_enabled=state.kill_switch_enabled,
        subsystems={
            "database": "ok",
            "broker": broker_status,
            "data_lake": "ok",
            "openbb": "not_checked",
            "live_trading": "not_implemented",
        },
    )


@router.get("/metrics")
def metrics() -> dict[str, float | str]:
    """Return starter process metrics."""

    return {"status": "ok", "pending_order_batches": 0, "stale_data_warnings": 0}
