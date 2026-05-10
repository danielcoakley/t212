"""SEC EDGAR official US filings and company facts adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pandas as pd

from isa_system.domain.enums import TimestampPrecision
from isa_system.utils.time import now_utc


class SECEdgarProvider:
    """Conservative SEC EDGAR client."""

    BASE_URL = "https://data.sec.gov"

    def __init__(
        self, user_agent: str | None, cache_path: Path, transport: httpx.BaseTransport | None = None
    ) -> None:
        self.user_agent = user_agent
        self.cache_path = cache_path
        self.client = httpx.Client(
            timeout=20,
            transport=transport,
            headers={"User-Agent": user_agent or "isa-system-dev missing-contact"},
        )

    def submissions(self, cik: str) -> dict[str, Any]:
        """Fetch SEC submissions JSON for a zero-padded CIK."""

        if not self.user_agent:
            return {}
        response = self.client.get(f"{self.BASE_URL}/submissions/CIK{cik.zfill(10)}.json")
        response.raise_for_status()
        return response.json()

    def companyfacts(self, cik: str) -> dict[str, Any]:
        """Fetch SEC companyfacts JSON for a zero-padded CIK."""

        if not self.user_agent:
            return {}
        response = self.client.get(f"{self.BASE_URL}/api/xbrl/companyfacts/CIK{cik.zfill(10)}.json")
        response.raise_for_status()
        return response.json()

    def normalise_companyfacts(self, symbol: str, payload: dict[str, Any]) -> pd.DataFrame:
        """Normalise selected SEC facts into point-in-time rows."""

        rows: list[dict[str, Any]] = []
        facts = payload.get("facts", {}).get("us-gaap", {})
        for fact_name in ["Revenues", "NetIncomeLoss", "Assets", "StockholdersEquity"]:
            fact = facts.get(fact_name, {})
            for unit_values in fact.get("units", {}).values():
                for item in unit_values:
                    filed = item.get("filed")
                    if not filed or "val" not in item:
                        continue
                    filed_at = pd.Timestamp(filed, tz="UTC")
                    rows.append(
                        {
                            "symbol": symbol,
                            "fact_name": fact_name,
                            "value": item["val"],
                            "effective_date": item.get("end"),
                            "filed_at_utc": filed_at,
                            "published_at_utc": filed_at,
                            "retrieved_at_utc": now_utc(),
                            "available_at_utc": filed_at,
                            "source_name": "sec_edgar",
                            "source_document_id": item.get("accn", ""),
                            "timestamp_precision": TimestampPrecision.DATE.value,
                        }
                    )
        return pd.DataFrame(rows)
