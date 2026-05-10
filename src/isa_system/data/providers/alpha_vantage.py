"""Alpha Vantage convenience adapter with graceful missing-key behaviour."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pandas as pd

from isa_system.data.providers.base import empty_frame
from isa_system.utils.time import now_utc


class AlphaVantageProvider:
    """Convenience provider for daily prices and selected fundamentals."""

    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(
        self, api_key: str | None, cache_path: Path, transport: httpx.BaseTransport | None = None
    ) -> None:
        self.api_key = api_key
        self.cache_path = cache_path
        self.client = httpx.Client(timeout=20, transport=transport)

    def configured(self) -> bool:
        """Return whether an API key is available."""

        return bool(self.api_key)

    def daily_adjusted(self, symbol: str) -> pd.DataFrame:
        """Fetch daily adjusted bars where the endpoint is available."""

        if not self.configured():
            return empty_frame(
                [
                    "symbol",
                    "ts_utc",
                    "open",
                    "high",
                    "low",
                    "close",
                    "adj_close",
                    "volume",
                    "retrieved_at_utc",
                ]
            )
        response = self.client.get(
            self.BASE_URL,
            params={
                "function": "TIME_SERIES_DAILY_ADJUSTED",
                "symbol": symbol,
                "apikey": self.api_key,
                "outputsize": "compact",
            },
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        rows = []
        for day, values in payload.get("Time Series (Daily)", {}).items():
            rows.append(
                {
                    "symbol": symbol,
                    "ts_utc": pd.Timestamp(day, tz="UTC"),
                    "open": float(values["1. open"]),
                    "high": float(values["2. high"]),
                    "low": float(values["3. low"]),
                    "close": float(values["4. close"]),
                    "adj_close": float(values.get("5. adjusted close", values["4. close"])),
                    "volume": float(values["6. volume"]),
                    "retrieved_at_utc": now_utc(),
                }
            )
        return pd.DataFrame(rows).sort_values("ts_utc")
