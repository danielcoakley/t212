"""Execution mode routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from isa_system.api.deps import ControlState, get_state
from isa_system.domain.enums import RuntimeMode

router = APIRouter()


@router.post("/modes/paper")
def paper_mode(state: ControlState = Depends(get_state)) -> dict[str, str]:
    """Switch to paper mode."""

    state.mode = RuntimeMode.PAPER
    state.live_armed = False
    return {"mode": state.mode.value}


@router.post("/modes/live")
def live_mode(state: ControlState = Depends(get_state)) -> dict[str, str]:
    """Switch to live mode without arming."""

    state.mode = RuntimeMode.LIVE
    state.live_armed = False
    return {"mode": state.mode.value, "live_armed": str(state.live_armed)}


@router.post("/live/arm")
def arm_live(state: ControlState = Depends(get_state)) -> dict[str, str]:
    """Arm live trading after mode selection."""

    state.mode = RuntimeMode.LIVE
    state.live_armed = True
    return {"mode": state.mode.value, "live_armed": "true"}


@router.post("/live/disarm")
def disarm_live(state: ControlState = Depends(get_state)) -> dict[str, str]:
    """Disarm live trading."""

    state.live_armed = False
    return {"mode": state.mode.value, "live_armed": "false"}


@router.post("/control/pause")
def pause_all_trading(state: ControlState = Depends(get_state)) -> dict[str, str]:
    """Enable the local kill switch and disarm live trading."""

    state.kill_switch_enabled = True
    state.live_armed = False
    return {
        "mode": state.mode.value,
        "live_armed": "false",
        "kill_switch_enabled": "true",
    }


@router.post("/control/resume")
def resume_trading(state: ControlState = Depends(get_state)) -> dict[str, str]:
    """Disable the local kill switch without arming live trading."""

    state.kill_switch_enabled = False
    state.live_armed = False
    return {
        "mode": state.mode.value,
        "live_armed": "false",
        "kill_switch_enabled": "false",
    }
