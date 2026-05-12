"""Research memo models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from isa_system.thesis.models import InvestmentDecision


class MemoSection(StrEnum):
    """Standard structured memo section names."""

    EXECUTIVE_SUMMARY = "Executive summary"
    BUSINESS_OVERVIEW = "Business overview"
    SCREEN_REASON = "Why it appeared in the screen"
    FUNDAMENTAL_GROWTH = "Fundamental growth case"
    QUALITY_BALANCE_SHEET = "Quality and balance sheet"
    VALUATION = "Valuation snapshot"
    TECHNICAL_SETUP = "Technical setup"
    SENTIMENT_OWNERSHIP = "Sentiment and ownership context"
    CATALYST_PATH = "Catalyst path"
    BULL_CASE = "Bull case"
    BEAR_CASE = "Bear case"
    ENTRY_PLAN = "Entry plan"
    EXIT_PLAN = "Exit plan"
    INVALIDATION = "Invalidation triggers"
    PORTFOLIO_FIT = "Portfolio fit"
    DECISION = "Decision"
    MISSING_DATA = "Missing data and confidence notes"


class ResearchReport(BaseModel):
    """Persisted structured research memo."""

    model_config = ConfigDict(extra="forbid")

    id: str
    symbol: str
    thesis_id: str
    decision: InvestmentDecision
    sections: dict[str, str] = Field(default_factory=dict)
    markdown: str
    markdown_path: str | None = None
    generated_at_utc: datetime
