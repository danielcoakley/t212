"""Financial Modeling Prep convenience adapter."""

from __future__ import annotations

from pathlib import Path

import httpx
import pandas as pd

from isa_system.data.providers.base import empty_frame
from isa_system.utils.time import now_utc


class FMPProvider:
    """Convenience adapter for profiles, ratios, and earnings data."""

    BASE_URL = "https://financialmodelingprep.com/api/v3"

    def __init__(
        self, api_key: str | None, cache_path: Path, transport: httpx.BaseTransport | None = None
    ) -> None:
        self.api_key = api_key
        self.cache_path = cache_path
        self.client = httpx.Client(timeout=20, transport=transport)

    def company_profile(self, symbol: str) -> pd.DataFrame:
        """Return company profile rows or an empty schema-valid frame."""

        if not self.api_key:
            return empty_frame(["symbol", "sector", "industry", "country", "retrieved_at_utc"])
        response = self.client.get(
            f"{self.BASE_URL}/profile/{symbol}", params={"apikey": self.api_key}
        )
        response.raise_for_status()
        rows = response.json()
        for row in rows:
            row["retrieved_at_utc"] = now_utc()
        return pd.DataFrame(rows)
