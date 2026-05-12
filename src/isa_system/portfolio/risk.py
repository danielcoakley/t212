"""Risk constraints for rationale-based portfolio proposals."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class PortfolioRiskConfig(BaseModel):
    """Risk settings for proposal generation."""

    model_config = ConfigDict(extra="forbid")

    max_single_name_weight: float = 0.10
    max_strategy_sleeve_weight: float = 0.20
    min_cash_buffer_gbp: float = 250.0
    material_conviction_delta: float = 10.0
    material_ratio_delta: float = 0.5
    cooldown_days: int = 14
    default_new_position_weight: float = 0.04
