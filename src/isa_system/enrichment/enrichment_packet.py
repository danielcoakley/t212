"""Candidate enrichment packet models and service."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from isa_system.enrichment.data_quality import score_data_quality
from isa_system.enrichment.openbb_client import OpenBBClient
from isa_system.enrichment.openbb_endpoints import OPENBB_ENDPOINTS
from isa_system.utils.time import now_utc


class CandidateEnrichmentPacket(BaseModel):
    """Combined enrichment packet for one candidate symbol."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    company_name: str | None = None
    sector: str | None = None
    industry: str | None = None
    country: str | None = None
    exchange: str | None = None
    currency: str | None = None
    market_cap: float | None = None
    price: float | None = None
    price_history_summary: dict[str, Any] | None = None
    fundamentals: dict[str, Any] | None = None
    valuation: dict[str, Any] | None = None
    technicals: dict[str, Any] | None = None
    news: list[dict[str, Any]] | None = None
    earnings: dict[str, Any] | list[dict[str, Any]] | None = None
    filings: list[dict[str, Any]] | None = None
    catalysts: list[dict[str, Any]] = Field(default_factory=list)
    sentiment: dict[str, Any] | None = None
    data_quality: dict[str, Any]
    retrieved_at_utc: datetime
    missing_sections: list[str] = Field(default_factory=list)
    section_errors: dict[str, str] = Field(default_factory=dict)


class EnrichmentService:
    """Build candidate enrichment packets from OpenBB or fixture data."""

    def __init__(self, client: OpenBBClient | None = None) -> None:
        self.client = client or OpenBBClient()

    def enrich_symbol(
        self,
        symbol: str,
        *,
        fixture_data: dict[str, Any] | None = None,
    ) -> CandidateEnrichmentPacket:
        """Create one enrichment packet, tolerating unavailable sections."""

        retrieved_at = now_utc()
        sections: dict[str, Any | None] = {}
        errors: dict[str, str] = {}

        fixture_mode = fixture_data is not None
        for section in OPENBB_ENDPOINTS:
            if fixture_data and section in fixture_data:
                sections[section] = fixture_data[section]
                continue
            if fixture_mode:
                sections[section] = None
                continue
            result = self.client.get_section(section, symbol)
            sections[section] = result.data if result.status == "ok" else None
            if result.error:
                errors[section] = result.error

        profile = _first_record(sections.get("company_profile"))
        price_history = _records(sections.get("price_history"))
        fundamentals = _first_record(sections.get("fundamentals")) or {}
        ratios = _first_record(sections.get("ratios")) or {}
        quality = score_data_quality(sections, retrieved_at_utc=retrieved_at)
        price_summary = _price_history_summary(price_history)

        return CandidateEnrichmentPacket(
            symbol=symbol.upper(),
            company_name=_value(profile, "name", "company_name"),
            sector=_value(profile, "sector"),
            industry=_value(profile, "industry"),
            country=_value(profile, "country"),
            exchange=_value(profile, "exchange"),
            currency=_value(profile, "currency"),
            market_cap=_float_value(profile, "market_cap"),
            price=price_summary.get("latest_close"),
            price_history_summary=price_summary,
            fundamentals=fundamentals or None,
            valuation=ratios or None,
            technicals=_first_record(sections.get("technicals")),
            news=_records(sections.get("news")) or None,
            earnings=sections.get("earnings"),
            filings=_records(sections.get("filings")) or None,
            catalysts=_derive_catalysts(sections),
            sentiment={"status": "not_available", "score": None},
            data_quality=quality,
            retrieved_at_utc=retrieved_at,
            missing_sections=_missing_sections(quality),
            section_errors=errors,
        )

    def enrich_symbols(
        self,
        symbols: list[str],
        *,
        fixture_data_by_symbol: dict[str, dict[str, Any]] | None = None,
    ) -> list[CandidateEnrichmentPacket]:
        """Create enrichment packets for a list of symbols."""

        return [
            self.enrich_symbol(
                symbol,
                fixture_data=(fixture_data_by_symbol or {}).get(symbol.upper()),
            )
            for symbol in symbols
        ]


def load_fixture_enrichment(symbol: str) -> dict[str, Any]:
    """Load offline OpenBB-style fixture data for tests and smoke runs."""

    fixture_dir = Path("tests/fixtures")
    data: dict[str, Any] = {}
    price_path = fixture_dir / "openbb_price_history.json"
    fundamentals_path = fixture_dir / "openbb_fundamentals.json"
    if price_path.exists():
        data["price_history"] = _read_json(price_path)
    if fundamentals_path.exists():
        payload = _read_json(fundamentals_path)
        data["company_profile"] = payload.get("company_profile")
        data["fundamentals"] = payload.get("fundamentals")
        data["ratios"] = payload.get("ratios")
    return {key: value for key, value in data.items() if value is not None}


def _read_json(path: Path) -> Any:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def _records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        data = value.get("data")
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        return [value]
    return []


def _first_record(value: Any) -> dict[str, Any] | None:
    records = _records(value)
    if not records:
        return None
    return records[0]


def _price_history_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        return {}
    closes = [_float(item.get("close") or item.get("adj_close")) for item in records]
    closes = [value for value in closes if value is not None]
    latest = closes[-1] if closes else None
    first = closes[0] if closes else None
    return {
        "bars": len(records),
        "first_date": records[0].get("date"),
        "latest_date": records[-1].get("date"),
        "latest_close": latest,
        "return_pct": _return_pct(first, latest),
    }


def _derive_catalysts(sections: dict[str, Any | None]) -> list[dict[str, Any]]:
    catalysts: list[dict[str, Any]] = []
    if sections.get("earnings"):
        catalysts.append({"type": "earnings", "description": "Earnings data available"})
    if sections.get("news"):
        catalysts.append({"type": "news", "description": "Recent news data available"})
    return catalysts


def _value(record: dict[str, Any] | None, *keys: str) -> str | None:
    if not record:
        return None
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def _float_value(record: dict[str, Any] | None, key: str) -> float | None:
    if not record:
        return None
    return _float(record.get(key))


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _missing_sections(quality: dict[str, Any]) -> list[str]:
    value = quality.get("missing_sections")
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def _return_pct(first: float | None, latest: float | None) -> float | None:
    if first is None or first == 0 or latest is None:
        return None
    return round(((latest - first) / first) * 100, 2)
