"""Composite score models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from isa_system.scoring.factor_scores import FactorScore


class CompositeScore(BaseModel):
    """Composite opportunity score with explanations."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    total_score: float
    factor_scores: list[FactorScore]
    data_quality_score: float
    boosts: list[str] = Field(default_factory=list)
    penalties: list[str] = Field(default_factory=list)
    explanation: str
    scored_at_utc: datetime
