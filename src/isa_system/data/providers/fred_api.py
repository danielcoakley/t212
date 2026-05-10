"""FRED macro provider with graceful missing-key behaviour."""

from __future__ import annotations

from pathlib import Path

import httpx
import pandas as pd

from isa_system.data.providers.base import empty_frame
from isa_system.utils.time import now_utc


class FREDProvider:
    """Fetch macro series from FRED when configured."""

    BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

    def __init__(
        self, api_key: str | None, cache_path: Path, transport: httpx.BaseTransport | None = None
    ) -> None:
        self.api_key = api_key
        self.cache_path = cache_path
        self.client = httpx.Client(timeout=20, transport=transport)

    def observations(self, series_id: str) -> pd.DataFrame:
        """Fetch a FRED series or return an empty frame."""

        if not self.api_key:
            return empty_frame(["series_id", "ts_utc", "value", "retrieved_at_utc"])
        response = self.client.get(
            self.BASE_URL,
            params={"series_id": series_id, "api_key": self.api_key, "file_type": "json"},
        )
        response.raise_for_status()
        rows = []
        for item in response.json().get("observations", []):
            rows.append(
                {
                    "series_id": series_id,
                    "ts_utc": pd.Timestamp(item["date"], tz="UTC"),
                    "value": pd.to_numeric(item["value"], errors="coerce"),
                    "retrieved_at_utc": now_utc(),
                }
            )
        return pd.DataFrame(rows)
