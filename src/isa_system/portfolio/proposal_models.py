"""Rebalance proposal models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ProposalType(StrEnum):
    """Rationale-based rebalance proposal types."""

    BUY_NEW = "BUY_NEW"
    ADD_TO_EXISTING = "ADD_TO_EXISTING"
    TRIM = "TRIM"
    SELL_THESIS_BROKEN = "SELL_THESIS_BROKEN"
    SELL_TARGET_REACHED = "SELL_TARGET_REACHED"
    REPLACE_WITH_CANDIDATE = "REPLACE_WITH_CANDIDATE"
    HOLD = "HOLD"
    WATCHLIST_WAIT_ENTRY = "WATCHLIST_WAIT_ENTRY"
    WATCHLIST_WAIT_CATALYST = "WATCHLIST_WAIT_CATALYST"


class RebalanceProposal(BaseModel):
    """Portfolio action proposal requiring manual review."""

    model_config = ConfigDict(extra="forbid")

    proposal_type: ProposalType
    symbol: str
    candidate_or_holding: str
    rationale: str
    target_weight: float | None = None
    current_weight: float | None = None
    estimated_trade_value: float | None = None
    funding_source: str | None = None
    expected_impact: str
    risks: list[str] = Field(default_factory=list)
    manual_approval_required: bool = True
    confidence_score: float
    created_at_utc: datetime
