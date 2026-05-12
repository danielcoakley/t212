"""Portfolio holding models for thesis comparison."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PortfolioHolding(BaseModel):
    """Current holding context used for portfolio comparison."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    company_name: str | None = None
    quantity: float = 0.0
    average_price: float = 0.0
    current_price: float = 0.0
    market_value: float = 0.0
    target_weight: float = 0.0
    current_weight: float = 0.0
    sleeve: str = "core"
    thesis_id: str | None = None
    thesis_status: str | None = None
    conviction_score: float = 0.0
    expected_upside_pct: float | None = None
    downside_risk_pct: float | None = None
    next_review_date: datetime | None = None
    last_trade_at_utc: datetime | None = None
    notes: str = ""
