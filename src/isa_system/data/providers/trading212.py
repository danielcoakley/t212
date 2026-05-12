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

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from time import monotonic, sleep, time
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field

from isa_system.data.providers.base import ProviderNotConfigured
from isa_system.domain.enums import OrderSide, OrderType, RuntimeMode
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
    respect_rate_limits: bool = True

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
    max_open_quantity: float | None = Field(default=None, alias="maxOpenQuantity")
    short_name: str | None = Field(default=None, alias="shortName")
    working_schedule_id: int | None = Field(default=None, alias="workingScheduleId")
    extended_hours: bool | None = Field(default=None, alias="extendedHours")


class Trading212Exchange(BaseModel):
    """Exchange metadata response subset."""

    model_config = ConfigDict(extra="allow")

    id: int
    name: str | None = None
    working_schedules: list[dict[str, Any]] = Field(default_factory=list, alias="workingSchedules")


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


class Trading212Report(BaseModel):
    """CSV report response subset."""

    model_config = ConfigDict(extra="allow")

    report_id: int | None = Field(default=None, alias="reportId")
    status: str | None = None
    download_link: str | None = Field(default=None, alias="downloadLink")


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

    ENDPOINT_RATE_LIMITS: dict[tuple[str, str], tuple[int, int]] = {
        ("GET", "/equity/account/summary"): (1, 5),
        ("GET", "/equity/history/dividends"): (6, 60),
        ("GET", "/equity/history/exports"): (1, 60),
        ("POST", "/equity/history/exports"): (1, 30),
        ("GET", "/equity/history/orders"): (6, 60),
        ("GET", "/equity/history/transactions"): (6, 60),
        ("GET", "/equity/metadata/exchanges"): (1, 30),
        ("GET", "/equity/metadata/instruments"): (1, 50),
        ("GET", "/equity/orders"): (1, 5),
        ("DELETE", "/equity/orders/{id}"): (50, 60),
        ("GET", "/equity/orders/{id}"): (1, 1),
        ("POST", "/equity/orders/limit"): (1, 2),
        ("POST", "/equity/orders/market"): (50, 60),
        ("POST", "/equity/orders/stop"): (1, 2),
        ("POST", "/equity/orders/stop_limit"): (1, 2),
        ("GET", "/equity/positions"): (1, 1),
    }

    def __init__(
        self,
        settings: Trading212Settings,
        transport: httpx.BaseTransport | None = None,
        sleep_func: Callable[[float], None] = sleep,
    ) -> None:
        self.settings = settings
        self._sleep = sleep_func
        self._last_request_at: dict[tuple[str, str], float] = {}
        self._client = httpx.Client(
            base_url=settings.base_url,
            timeout=settings.timeout_seconds,
            transport=transport,
            auth=(settings.api_key or "", settings.api_secret or ""),
        )

    def _request(self, method: str, path: str, *, json: dict[str, Any] | None = None) -> Any:
        if not self.settings.configured:
            raise ProviderNotConfigured("Trading 212 credentials are not configured.")
        endpoint_key = self._endpoint_key(method, path)
        self._throttle(endpoint_key)
        response = self._client.request(method, path, json=json)
        if response.status_code == 429 and method.upper() == "GET":
            self._sleep(_retry_after_seconds(response))
            response = self._client.request(method, path, json=json)
        response.raise_for_status()
        return response.json() if response.content else None

    def _throttle(self, endpoint_key: tuple[str, str]) -> None:
        """Apply simple local pacing for documented Trading 212 rate limits."""

        if not self.settings.respect_rate_limits:
            return
        limit = self.ENDPOINT_RATE_LIMITS.get(endpoint_key)
        if not limit:
            return
        requests, period = limit
        min_interval = period / requests
        last = self._last_request_at.get(endpoint_key)
        current = monotonic()
        if last is not None:
            wait_for = min_interval - (current - last)
            if wait_for > 0:
                self._sleep(wait_for)
        self._last_request_at[endpoint_key] = monotonic()

    def _endpoint_key(self, method: str, path: str) -> tuple[str, str]:
        """Map a request path to its documented rate-limit key."""

        method_key = method.upper()
        clean_path = path.split("?", 1)[0]
        if clean_path.startswith("/api/v0"):
            clean_path = clean_path.removeprefix("/api/v0")
        order_leaf = clean_path.rsplit("/", 1)[-1]
        order_actions = {"limit", "market", "stop", "stop_limit"}
        if (
            clean_path.startswith("/equity/orders/")
            and clean_path.count("/") == 3
            and order_leaf not in order_actions
        ):
            return (method_key, "/equity/orders/{id}")
        return (method_key, clean_path)

    def account_summary(self) -> Trading212AccountSummary:
        """Fetch `/equity/account/summary`."""

        return Trading212AccountSummary.model_validate(
            self._request("GET", "/equity/account/summary")
        )

    def instruments(self) -> list[Trading212Instrument]:
        """Fetch documented instrument metadata."""

        payload = self._request("GET", "/equity/metadata/instruments")
        return [Trading212Instrument.model_validate(item) for item in payload]

    def exchanges(self) -> list[Trading212Exchange]:
        """Fetch documented exchange and working schedule metadata."""

        payload = self._request("GET", "/equity/metadata/exchanges")
        return [Trading212Exchange.model_validate(item) for item in payload]

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

    def cancel_order(self, order_id: int) -> None:
        """Cancel a documented pending order."""

        self._request("DELETE", f"/equity/orders/{order_id}")

    def history_orders(self, limit: int = 50) -> list[dict[str, Any]]:
        """Fetch documented historical orders with cursor pagination support."""

        return self._paginate(f"/equity/history/orders?limit={min(limit, 50)}")

    def history_dividends(self, limit: int = 50) -> list[dict[str, Any]]:
        """Fetch documented dividend history with cursor pagination support."""

        return self._paginate(f"/equity/history/dividends?limit={min(limit, 50)}")

    def history_transactions(self, limit: int = 50) -> list[dict[str, Any]]:
        """Fetch documented transaction history with cursor pagination support."""

        return self._paginate(f"/equity/history/transactions?limit={min(limit, 50)}")

    def list_exports(self) -> list[Trading212Report]:
        """List generated CSV reports."""

        payload = self._request("GET", "/equity/history/exports")
        if isinstance(payload, dict) and "items" in payload:
            payload = payload["items"]
        return [Trading212Report.model_validate(item) for item in payload or []]

    def request_export(
        self,
        *,
        time_from: str,
        time_to: str,
        include_orders: bool = True,
        include_dividends: bool = True,
        include_transactions: bool = True,
        include_interest: bool = True,
    ) -> int:
        """Request a CSV export and return the report id."""

        payload = {
            "timeFrom": time_from,
            "timeTo": time_to,
            "dataIncluded": {
                "includeOrders": include_orders,
                "includeDividends": include_dividends,
                "includeTransactions": include_transactions,
                "includeInterest": include_interest,
            },
        }
        response = self._request("POST", "/equity/history/exports", json=payload)
        report_id = response.get("reportId") if isinstance(response, dict) else None
        if report_id is None:
            raise ValueError("Trading 212 export response did not include reportId.")
        return int(report_id)

    def download_report(self, report: Trading212Report) -> bytes:
        """Download a finished CSV report from its broker-provided URL."""

        if not report.download_link:
            raise ValueError("Report has no download link.")
        response = self._client.get(report.download_link)
        response.raise_for_status()
        return response.content

    def _paginate(self, first_path: str) -> list[dict[str, Any]]:
        """Collect all items from a documented cursor-paginated endpoint."""

        items: list[dict[str, Any]] = []
        next_path: str | None = first_path
        while next_path:
            payload = self._request("GET", next_path)
            if not isinstance(payload, dict):
                raise ValueError("Paginated Trading 212 response was not an object.")
            items.extend(payload.get("items") or [])
            next_path = payload.get("nextPagePath")
        return items

    def submit_order(self, intent: OrderIntent) -> Trading212OrderResponse:
        """Submit a market or limit order using documented endpoint shapes.

        The caller is responsible for idempotency reservation and live-mode
        arming. This method intentionally does not retry POST requests.
        """

        if intent.order_type == OrderType.MARKET:
            payload = {
                "ticker": intent.broker_ticker,
                "quantity": float(_signed_quantity(intent.side, intent.quantity)),
                "extendedHours": False,
            }
            endpoint = "/equity/orders/market"
        elif intent.order_type == OrderType.LIMIT:
            if intent.limit_price is None:
                raise ValueError("Limit orders require a limit price.")
            payload = {
                "ticker": intent.broker_ticker,
                "quantity": float(_signed_quantity(intent.side, intent.quantity)),
                "limitPrice": float(intent.limit_price),
                "timeValidity": intent.time_validity,
            }
            endpoint = "/equity/orders/limit"
        elif intent.order_type == OrderType.STOP:
            if intent.stop_price is None:
                raise ValueError("Stop orders require a stop price.")
            payload = {
                "ticker": intent.broker_ticker,
                "quantity": float(_signed_quantity(intent.side, intent.quantity)),
                "stopPrice": float(intent.stop_price),
                "timeValidity": intent.time_validity,
            }
            endpoint = "/equity/orders/stop"
        elif intent.order_type == OrderType.STOP_LIMIT:
            if intent.stop_price is None or intent.limit_price is None:
                raise ValueError("Stop-limit orders require stop and limit prices.")
            payload = {
                "ticker": intent.broker_ticker,
                "quantity": float(_signed_quantity(intent.side, intent.quantity)),
                "stopPrice": float(intent.stop_price),
                "limitPrice": float(intent.limit_price),
                "timeValidity": intent.time_validity,
            }
            endpoint = "/equity/orders/stop_limit"
        else:
            raise NotImplementedError(
                f"Unsupported order type: {intent.order_type}"
            )
        return Trading212OrderResponse.model_validate(self._request("POST", endpoint, json=payload))


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
        """Submit a previously previewed batch when live mode is armed."""

        if batch.mode != RuntimeMode.LIVE:
            raise ValueError("Trading 212 live submit requires live mode.")
        if not live_armed:
            raise PermissionError("Live trading is not armed.")
        return [self.client.submit_order(order) for order in batch.orders]


def _signed_quantity(side: OrderSide, quantity: Decimal) -> Decimal:
    """Trading 212 uses negative quantity for sell orders."""

    return quantity if side == OrderSide.BUY else -quantity


def _retry_after_seconds(response: httpx.Response) -> float:
    """Return a conservative retry delay from rate-limit headers."""

    reset = response.headers.get("x-ratelimit-reset")
    if reset:
        try:
            return max(0.25, float(reset) - time())
        except ValueError:
            pass
    return 1.0
