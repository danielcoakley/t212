"""Companies House adapter for UK company matching and filing metadata."""

from __future__ import annotations

from pathlib import Path

import httpx
import pandas as pd

from isa_system.data.providers.base import empty_frame
from isa_system.domain.enums import TimestampPrecision
from isa_system.utils.time import now_utc


class CompaniesHouseProvider:
    """Companies House Public Data API client."""

    BASE_URL = "https://api.company-information.service.gov.uk"

    def __init__(
        self, api_key: str | None, cache_path: Path, transport: httpx.BaseTransport | None = None
    ) -> None:
        self.api_key = api_key
        self.cache_path = cache_path
        self.client = httpx.Client(timeout=20, transport=transport, auth=(api_key or "", ""))

    def search_companies(self, query: str) -> pd.DataFrame:
        """Search company metadata for issuer matching."""

        if not self.api_key:
            return empty_frame(["company_number", "title", "retrieved_at_utc"])
        response = self.client.get(f"{self.BASE_URL}/search/companies", params={"q": query})
        response.raise_for_status()
        rows = response.json().get("items", [])
        for row in rows:
            row["retrieved_at_utc"] = now_utc()
        return pd.DataFrame(rows)

    def filing_history(self, company_number: str) -> pd.DataFrame:
        """Return filing history metadata with conservative timestamp precision."""

        if not self.api_key:
            return empty_frame(
                ["company_number", "source_document_id", "available_at_utc", "timestamp_precision"]
            )
        response = self.client.get(f"{self.BASE_URL}/company/{company_number}/filing-history")
        response.raise_for_status()
        rows = []
        for item in response.json().get("items", []):
            date = item.get("date")
            if not date:
                continue
            available = pd.Timestamp(date, tz="UTC")
            rows.append(
                {
                    "company_number": company_number,
                    "source_document_id": item.get("transaction_id", ""),
                    "description": item.get("description", ""),
                    "available_at_utc": available,
                    "retrieved_at_utc": now_utc(),
                    "timestamp_precision": TimestampPrecision.DATE.value,
                }
            )
        return pd.DataFrame(rows)
