"""Safe Trading 212 Public API client and broker adapter.

The public API is currently documented as beta and enabled for Invest and
Stocks ISA accounts. Order POST endpoints are treated as non-idempotent:
the adapter never retries live POST requests blindly, and callers must
reserve a local idempotency key before submission.

TODO: The public docs do not document a broker-side order preview route.
This adapter therefore implements local preview only until a documented
route and payload contract exist.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field

from isa_system.data.providers.base import ProviderNotConfigured
from isa_system.domain.enums import OrderSide, RuntimeMode
from isa_system.execution.order_models import OrderBatch, OrderIntent
from isa_system.utils.hashing import make_idempotency_key, sha256_digest
from isa_system.utils.time import now_utc


class Trading212Settings(BaseModel):
    """Trading 212 connection settings."""

    api_key: str | None = None
    api_secret: str | None = None
    environment: Literal["demo", "live"] = "demo"
    demo_base_url: str = "https://demo.trading212.com/api/v0"
    live_base_url: str = "https://live.trading212.com/api/v0"
    timeout_seconds: float = 20.0

    @property
    def base_url(self) -> str:
        """Return the configured base URL."""

        return self.live_base_url if self.environment == "live" else self.demo_base_url

    @property
    def configured(self) -> bool:
        """Return whether credentials are available."""

        return bool(self.api_key and self.api_secret)


class Trading212Instrument(BaseModel):
    """Instrument metadata response subset."""

    model_config = ConfigDict(extra="allow")

    ticker: str
    name: str | None = None
    isin: str | None = None
    currency_code: str | None = Field(default=None, alias="currencyCode")
    type: str | None = None
    working_schedule_id: int | None = Field(default=None, alias="workingScheduleId")
    extended_hours: bool | None = Field(default=None, alias="extendedHours")


class Trading212AccountSummary(BaseModel):
    """Account summary response subset."""

    model_config = ConfigDict(extra="allow")

    id: int | None = None
    currency: str | None = None
    total_value: float | None = Field(default=None, alias="totalValue")
    cash: dict[str, Any] | None = None


class Trading212Position(BaseModel):
    """Position response subset."""

    model_config = ConfigDict(extra="allow")

    ticker: str | None = None
    quantity: float
    average_price_paid: float | None = Field(default=None, alias="averagePricePaid")
    current_price: float | None = Field(default=None, alias="currentPrice")
    instrument: dict[str, Any] | None = None
    wallet_impact: dict[str, Any] | None = Field(default=None, alias="walletImpact")


class Trading212OrderResponse(BaseModel):
    """Order response subset."""

    model_config = ConfigDict(extra="allow")

    id: int | None = None
    ticker: str | None = None
    status: str | None = None
    type: str | None = None
    quantity: float | None = None


class LocalPreview(BaseModel):
    """Local preview result when no broker preview endpoint is documented."""

    mode: RuntimeMode
    batch_hash: str
    idempotency_key: str
    orders: list[dict[str, Any]]
    warnings: list[str]
    generated_at_utc: str


class Trading212Client:
    """Thin documented Trading 212 HTTP client."""

    def __init__(
        self, settings: Trading212Settings, transport: httpx.BaseTransport | None = None
    ) -> None:
        self.settings = settings
        self._client = httpx.Client(
            base_url=settings.base_url,
            timeout=settings.timeout_seconds,
            transport=transport,
            auth=(settings.api_key or "", settings.api_secret or ""),
        )

    def _request(self, method: str, path: str, *, json: dict[str, Any] | None = None) -> Any:
        if not self.settings.configured:
            raise ProviderNotConfigured("Trading 212 credentials are not configured.")
        response = self._client.request(method, path, json=json)
        response.raise_for_status()
        return response.json()

    def account_summary(self) -> Trading212AccountSummary:
        """Fetch `/equity/account/summary`."""

        return Trading212AccountSummary.model_validate(
            self._request("GET", "/equity/account/summary")
        )

    def instruments(self) -> list[Trading212Instrument]:
        """Fetch documented instrument metadata."""

        payload = self._request("GET", "/equity/metadata/instruments")
        return [Trading212Instrument.model_validate(item) for item in payload]

    def positions(self) -> list[Trading212Position]:
        """Fetch documented open positions."""

        payload = self._request("GET", "/equity/positions")
        return [Trading212Position.model_validate(item) for item in payload]

    def active_orders(self) -> list[Trading212OrderResponse]:
        """Fetch documented active orders."""

        payload = self._request("GET", "/equity/orders")
        return [Trading212OrderResponse.model_validate(item) for item in payload]

    def get_order(self, order_id: int) -> Trading212OrderResponse:
        """Fetch a documented order by id."""

        return Trading212OrderResponse.model_validate(
            self._request("GET", f"/equity/orders/{order_id}")
        )

    def history_orders(self, limit: int = 50) -> dict[str, Any]:
        """Fetch documented historical orders with cursor pagination support."""

        return self._request("GET", f"/equity/history/orders?limit={min(limit, 50)}")

    def submit_order(self, intent: OrderIntent) -> Trading212OrderResponse:
        """Live order submission is not implemented in this unified build."""

        raise NotImplementedError("Live Trading 212 order submission is not implemented.")


class Trading212BrokerAdapter:
    """Higher-level broker adapter with preview and paper-safe paths."""

    def __init__(self, client: Trading212Client) -> None:
        self.client = client

    def local_preview(self, batch: OrderBatch, trading_date: date) -> LocalPreview:
        """Build a local preview and idempotency key without touching the broker."""

        payload = [order.model_dump(mode="json") for order in batch.orders]
        key = make_idempotency_key(
            strategy_run_id=batch.strategy_run_id,
            environment=self.client.settings.environment,
            payload=payload,
            trading_date=trading_date,
        )
        warnings = [
            "Local preview only: Trading 212 docs do not expose a broker-side preview endpoint."
        ]
        if batch.mode == RuntimeMode.LIVE:
            warnings.append(
                "Live submit requires a reserved local idempotency key and human arming."
            )
        return LocalPreview(
            mode=batch.mode,
            batch_hash=sha256_digest(payload),
            idempotency_key=key,
            orders=payload,
            warnings=warnings,
            generated_at_utc=now_utc().isoformat(),
        )

    def submit_live(self, batch: OrderBatch, *, live_armed: bool) -> list[Trading212OrderResponse]:
        """Live order submission is not implemented in this unified build."""

        raise NotImplementedError("Live Trading 212 order submission is not implemented.")


def _signed_quantity(side: OrderSide, quantity: Decimal) -> Decimal:
    """Trading 212 uses negative quantity for sell orders."""

    return quantity if side == OrderSide.BUY else -quantity
