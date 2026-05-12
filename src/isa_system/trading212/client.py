"""Read-only Trading 212 client wrapper."""

from __future__ import annotations

from typing import Any

import httpx

from isa_system.settings import Settings, get_settings
from isa_system.trading212.models import (
    BrokerAccountSummary,
    BrokerMode,
    BrokerPosition,
    Trading212Config,
)
from isa_system.utils.time import now_utc


class Trading212ReadOnlyClient:
    """Trading 212 client limited to read-only GET calls."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        mode = (
            BrokerMode.LIVE if self.settings.trading212_environment == "live" else BrokerMode.DEMO
        )
        api_key = self.settings.trading212_api_key
        self.api_key = api_key.get_secret_value() if api_key else ""
        self.config = Trading212Config(
            mode=mode,
            api_key_configured=bool(self.api_key),
            live_trading_enabled=self.settings.live_trading_enabled,
        )
        self.client = client

    def account_summary(self) -> BrokerAccountSummary:
        """Fetch or safely report read-only account summary."""

        if not self.api_key:
            return BrokerAccountSummary(
                status="not_configured",
                mode=self.config.mode,
                retrieved_at_utc=now_utc(),
                warnings=["Trading 212 API key is optional and not configured."],
            )
        data = self._get_json("/equity/account/summary")
        if not isinstance(data, dict):
            data = {}
        cash = data.get("cash")
        cash_value = cash.get("free") if isinstance(cash, dict) else data.get("cash")
        return BrokerAccountSummary(
            status="ok",
            mode=self.config.mode,
            currency=data.get("currency"),
            total_value=_float(data.get("totalValue") or data.get("total_value")),
            cash=_float(cash_value),
            retrieved_at_utc=now_utc(),
        )

    def positions(self) -> list[BrokerPosition]:
        """Fetch read-only positions or return an empty safe default."""

        if not self.api_key:
            return []
        payload = self._get_json("/equity/positions")
        if not isinstance(payload, list):
            return []
        return [
            BrokerPosition(
                ticker=str(item.get("ticker") or ""),
                quantity=float(item.get("quantity") or 0),
                average_price=_float(item.get("averagePricePaid") or item.get("average_price")),
                current_price=_float(item.get("currentPrice") or item.get("current_price")),
                currency=item.get("currencyCode") or item.get("currency"),
            )
            for item in payload
        ]

    def _get_json(self, path: str) -> dict[str, Any] | list[dict[str, Any]]:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        if self.client is not None:
            response = self.client.get(f"{self.config.base_url}{path}", headers=headers)
        else:
            with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                response = client.get(f"{self.config.base_url}{path}", headers=headers)
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, (dict, list)) else {}


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
