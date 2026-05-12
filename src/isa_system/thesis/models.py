"""Investment thesis models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ThesisStatus(StrEnum):
    """Lifecycle status for an investment thesis."""

    DRAFT = "DRAFT"
    ACTIVE_HOLDING = "ACTIVE_HOLDING"
    WATCHLIST_WAIT_ENTRY = "WATCHLIST_WAIT_ENTRY"
    WATCHLIST_WAIT_CATALYST = "WATCHLIST_WAIT_CATALYST"
    REJECTED = "REJECTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    BROKEN = "BROKEN"
    TARGET_REACHED = "TARGET_REACHED"
    CLOSED = "CLOSED"


class InvestmentDecision(StrEnum):
    """Investment decision labels."""

    BUY_NOW = "BUY_NOW"
    WATCHLIST_WAIT_ENTRY = "WATCHLIST_WAIT_ENTRY"
    WATCHLIST_WAIT_CATALYST = "WATCHLIST_WAIT_CATALYST"
    HOLD_EXISTING = "HOLD_EXISTING"
    REJECT = "REJECT"


class Thesis(BaseModel):
    """Persistent investment thesis record."""

    model_config = ConfigDict(extra="forbid")

    id: str
    symbol: str
    company_name: str | None = None
    status: ThesisStatus
    decision: InvestmentDecision
    one_line_thesis: str
    business_summary: str
    growth_case: str
    quality_case: str
    valuation_case: str
    technical_setup: str
    sentiment_context: str
    catalyst_path: str
    key_risks: list[str] = Field(default_factory=list)
    entry_conditions: list[str] = Field(default_factory=list)
    exit_conditions: list[str] = Field(default_factory=list)
    invalidation_triggers: list[str] = Field(default_factory=list)
    target_price: float | None = None
    downside_case_price: float | None = None
    preferred_entry_price: float | None = None
    max_buy_price: float | None = None
    stop_or_review_level: float | None = None
    expected_holding_period: str = "6-36 months"
    conviction_score: float
    confidence_score: float
    data_quality_score: float
    current_price: float | None = None
    upside_to_target_pct: float | None = None
    downside_to_review_pct: float | None = None
    upside_downside_ratio: float | None = None
    catalyst_status: str = "UNKNOWN"
    next_review_date: datetime
    created_at_utc: datetime
    updated_at_utc: datetime
    latest_report_id: str | None = None
    rationale: list[str] = Field(default_factory=list)
    missing_data_notes: list[str] = Field(default_factory=list)
