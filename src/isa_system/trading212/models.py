"""Trading 212 read-only and preview models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class BrokerMode(StrEnum):
    """Supported broker modes."""

    DEMO = "demo"
    LIVE = "live"


class Trading212Config(BaseModel):
    """Trading 212 local configuration."""

    model_config = ConfigDict(extra="forbid")

    mode: BrokerMode = BrokerMode.DEMO
    api_key_configured: bool = False
    live_trading_enabled: bool = False
    demo_base_url: str = "https://demo.trading212.com/api/v0"
    live_base_url: str = "https://live.trading212.com/api/v0"

    @property
    def base_url(self) -> str:
        """Return base URL for read-only calls."""

        return self.live_base_url if self.mode == BrokerMode.LIVE else self.demo_base_url


class BrokerAccountSummary(BaseModel):
    """Read-only account summary."""

    model_config = ConfigDict(extra="allow")

    status: str
    mode: BrokerMode
    currency: str | None = None
    total_value: float | None = None
    cash: float | None = None
    retrieved_at_utc: datetime | None = None
    warnings: list[str] = Field(default_factory=list)


class BrokerPosition(BaseModel):
    """Read-only broker position."""

    model_config = ConfigDict(extra="allow")

    ticker: str
    quantity: float
    average_price: float | None = None
    current_price: float | None = None
    currency: str | None = None


class BrokerInstrumentMetadata(BaseModel):
    """Broker instrument metadata."""

    model_config = ConfigDict(extra="allow")

    ticker: str
    name: str | None = None
    isin: str | None = None
    currency: str | None = None
    type: str | None = None


class OrderPreviewRequest(BaseModel):
    """Local order preview request."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    side: str
    estimated_trade_value: float
    current_price: float | None = None
    currency: str = "GBP"
    target_weight: float | None = None
    post_trade_target_weight: float | None = None


class OrderPreview(BaseModel):
    """Local order preview response; never a broker order."""

    model_config = ConfigDict(extra="forbid")

    preview_id: str
    symbol: str
    side: str
    quantity: float | None
    estimated_trade_value: float
    estimated_fx_impact: float
    estimated_sdrt: float
    cash_buffer_effect: float
    post_trade_target_weight: float | None
    risk_warnings: list[str]
    manual_approval_required: bool = True
    duplicate_order_hash: str
    created_at_utc: datetime
