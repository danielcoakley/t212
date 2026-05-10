"""Pydantic schemas for the control plane."""

from __future__ import annotations

from pydantic import BaseModel, Field

from isa_system.domain.enums import RuntimeMode


class HealthResponse(BaseModel):
    """Health endpoint response."""

    status: str
    mode: RuntimeMode
    live_armed: bool
    kill_switch_enabled: bool
    subsystems: dict[str, str]


class ConfigRequest(BaseModel):
    """Config create/update request."""

    name: str
    config_text: str
    version: int = 1


class ConfigResponse(BaseModel):
    """Config response."""

    config_id: str
    name: str
    version: int
    config_hash: str


class RebalancePreviewRequest(BaseModel):
    """Rebalance preview request."""

    run_id: str = "api-preview"
    total_equity_gbp: float = Field(default=10_000.0, gt=0)


class SubmitRequest(BaseModel):
    """Submit request."""

    batch_hash: str
    mode: RuntimeMode = RuntimeMode.PAPER
