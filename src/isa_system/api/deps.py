"""FastAPI dependencies and in-memory local control state."""

from __future__ import annotations

from dataclasses import dataclass

from isa_system.domain.enums import RuntimeMode


@dataclass
class ControlState:
    """Local mode state for the starter control plane."""

    mode: RuntimeMode = RuntimeMode.PREVIEW
    live_armed: bool = False
    kill_switch_enabled: bool = False


STATE = ControlState()


def get_state() -> ControlState:
    """Return process-local control state."""

    return STATE
