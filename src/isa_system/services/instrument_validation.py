"""Trading 212 instrument metadata validation for recommendation candidates."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from enum import StrEnum

import httpx
from pydantic import BaseModel, Field

from isa_system.data.providers.base import ProviderNotConfigured
from isa_system.data.providers.trading212 import Trading212Client, Trading212Instrument
from isa_system.services.portfolio_state import trading212_settings_from_app
from isa_system.services.recommendations import RecommendationsResponse, TradeRecommendation
from isa_system.settings import Settings
from isa_system.utils.time import now_utc, require_utc

CACHE_TTL_SECONDS = 3600
_INSTRUMENT_CACHE: list[Trading212Instrument] | None = None
_INSTRUMENT_CACHE_AT_UTC: datetime | None = None


class InstrumentValidationStatus(StrEnum):
    """Read-only broker instrument validation status."""

    HOLDING_CONFIRMED = "HOLDING_CONFIRMED"
    BROKER_MATCHED = "BROKER_MATCHED"
    NEEDS_MAPPING = "NEEDS_MAPPING"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    ERROR = "ERROR"


class InstrumentValidationRow(BaseModel):
    """Validation result for one recommendation candidate."""

    symbol: str
    research_symbol: str
    source: str
    status: InstrumentValidationStatus
    broker_ticker: str | None = None
    name: str | None = None
    isin: str | None = None
    currency: str | None = None
    asset_type: str | None = None
    candidate_broker_tickers: list[str] = Field(default_factory=list)
    isa_eligibility: str
    reason: str


class InstrumentValidationResponse(BaseModel):
    """Read-only broker metadata validation response."""

    status: str
    environment: str
    retrieved_at_utc: datetime
    provider: str = "trading212"
    instrument_count: int
    rows: list[InstrumentValidationRow]
    warnings: list[str] = Field(default_factory=list)


def validate_recommendation_instruments(
    response: RecommendationsResponse,
    *,
    instruments: Sequence[Trading212Instrument] | None = None,
    settings: Settings | None = None,
) -> InstrumentValidationResponse:
    """Validate recommendation symbols against Trading 212 instrument metadata."""

    retrieved_at_utc = now_utc()
    supplied_instruments = instruments is not None
    warnings: list[str] = []

    if instruments is None:
        try:
            instruments = _load_trading212_instruments(settings)
        except ProviderNotConfigured:
            return _not_configured_response(response, retrieved_at_utc)
        except httpx.HTTPStatusError as exc:
            return _error_response(
                response,
                retrieved_at_utc,
                f"Trading 212 instrument metadata failed with HTTP {exc.response.status_code}.",
            )
        except httpx.HTTPError as exc:
            return _error_response(
                response,
                retrieved_at_utc,
                f"Trading 212 instrument metadata failed: {exc.__class__.__name__}.",
            )

    index = _build_index(instruments)
    rows = [_validate_row(item, index, supplied_instruments) for item in response.recommendations]
    if not supplied_instruments:
        warnings.append(
            "Trading 212 instrument metadata is read-only validation and does not submit orders."
        )
    warnings.append(
        "Broker metadata matches still require ISA, liquidity, official-source, "
        "and operator review."
    )
    return InstrumentValidationResponse(
        status=response.status,
        environment=response.environment,
        retrieved_at_utc=require_utc(response.retrieved_at_utc),
        instrument_count=len(instruments),
        rows=rows,
        warnings=warnings,
    )


def clear_instrument_cache() -> None:
    """Clear cached Trading 212 instrument metadata."""

    global _INSTRUMENT_CACHE, _INSTRUMENT_CACHE_AT_UTC
    _INSTRUMENT_CACHE = None
    _INSTRUMENT_CACHE_AT_UTC = None


def load_trading212_instruments(settings: Settings | None = None) -> list[Trading212Instrument]:
    """Load cached Trading 212 instrument metadata for read-only services."""

    return _load_trading212_instruments(settings)


def _load_trading212_instruments(settings: Settings | None) -> list[Trading212Instrument]:
    cached = _cached_instruments()
    if cached is not None:
        return cached
    client_settings = trading212_settings_from_app(settings)
    if not client_settings.configured:
        raise ProviderNotConfigured("Trading 212 credentials are not configured.")
    instruments = Trading212Client(client_settings).instruments()
    _store_instruments(instruments, settings)
    return instruments


def _cached_instruments() -> list[Trading212Instrument] | None:
    if _INSTRUMENT_CACHE is None or _INSTRUMENT_CACHE_AT_UTC is None:
        return None
    if now_utc() - _INSTRUMENT_CACHE_AT_UTC > timedelta(seconds=CACHE_TTL_SECONDS):
        return None
    return _INSTRUMENT_CACHE


def _store_instruments(
    instruments: Sequence[Trading212Instrument], settings: Settings | None
) -> None:
    if settings is not None:
        return
    global _INSTRUMENT_CACHE, _INSTRUMENT_CACHE_AT_UTC
    _INSTRUMENT_CACHE = list(instruments)
    _INSTRUMENT_CACHE_AT_UTC = now_utc()


def _build_index(
    instruments: Sequence[Trading212Instrument],
) -> Mapping[str, list[Trading212Instrument]]:
    index: dict[str, list[Trading212Instrument]] = {}
    for instrument in instruments:
        for key in _instrument_keys(instrument):
            index.setdefault(key, []).append(instrument)
    return index


def _validate_row(
    item: TradeRecommendation,
    index: Mapping[str, list[Trading212Instrument]],
    supplied_instruments: bool,
) -> InstrumentValidationRow:
    candidate = item.candidate
    matches = _matches(candidate.research_symbol, candidate.symbol, index)
    preferred = _preferred_match(candidate.research_symbol, matches)
    if candidate.source == "holding":
        instrument = preferred or (matches[0] if matches else None)
        return InstrumentValidationRow(
            symbol=candidate.symbol,
            research_symbol=candidate.research_symbol,
            source=candidate.source,
            status=InstrumentValidationStatus.HOLDING_CONFIRMED,
            broker_ticker=instrument.ticker if instrument else candidate.symbol,
            name=instrument.name if instrument else candidate.name,
            isin=instrument.isin if instrument else None,
            currency=_currency(instrument) or candidate.currency,
            asset_type=instrument.type if instrument else None,
            candidate_broker_tickers=[match.ticker for match in matches[:5]],
            isa_eligibility=_isa_eligibility_text(),
            reason="Existing holding is confirmed by the broker positions endpoint.",
        )

    if preferred is not None and len(matches) == 1:
        return _matched_row(item, preferred)

    if preferred is not None and _is_symbol_specific(candidate.research_symbol):
        return _matched_row(item, preferred)

    if matches:
        return InstrumentValidationRow(
            symbol=candidate.symbol,
            research_symbol=candidate.research_symbol,
            source=candidate.source,
            status=InstrumentValidationStatus.NEEDS_MAPPING,
            candidate_broker_tickers=[match.ticker for match in matches[:10]],
            isa_eligibility=_isa_eligibility_text(),
            reason=(
                "Multiple Trading 212 instruments matched the research symbol; "
                "choose the exact broker ticker before preview."
            ),
        )

    reason = (
        "No matching Trading 212 instrument metadata was supplied by the test fixture."
        if supplied_instruments
        else "No matching Trading 212 instrument metadata was found in the live metadata feed."
    )
    return InstrumentValidationRow(
        symbol=candidate.symbol,
        research_symbol=candidate.research_symbol,
        source=candidate.source,
        status=InstrumentValidationStatus.NEEDS_MAPPING,
        isa_eligibility=_isa_eligibility_text(),
        reason=reason,
    )


def _matched_row(
    item: TradeRecommendation, instrument: Trading212Instrument
) -> InstrumentValidationRow:
    candidate = item.candidate
    return InstrumentValidationRow(
        symbol=candidate.symbol,
        research_symbol=candidate.research_symbol,
        source=candidate.source,
        status=InstrumentValidationStatus.BROKER_MATCHED,
        broker_ticker=instrument.ticker,
        name=instrument.name,
        isin=instrument.isin,
        currency=_currency(instrument),
        asset_type=instrument.type,
        candidate_broker_tickers=[instrument.ticker],
        isa_eligibility=_isa_eligibility_text(),
        reason="Research symbol matched a Trading 212 instrument metadata row.",
    )


def _matches(
    research_symbol: str,
    broker_symbol: str,
    index: Mapping[str, list[Trading212Instrument]],
) -> list[Trading212Instrument]:
    seen: set[str] = set()
    matches: list[Trading212Instrument] = []
    for key in _symbol_keys(research_symbol, broker_symbol):
        for instrument in index.get(key, []):
            if instrument.ticker not in seen:
                seen.add(instrument.ticker)
                matches.append(instrument)
    return matches


def _preferred_match(
    research_symbol: str, matches: Sequence[Trading212Instrument]
) -> Trading212Instrument | None:
    if not matches:
        return None
    symbol = research_symbol.upper()
    if symbol.endswith(".L"):
        for match in matches:
            if _is_london_listing(match):
                return match
    if "." not in symbol:
        for match in matches:
            if _currency(match) == "USD" or "_US_" in match.ticker.upper():
                return match
    return matches[0] if len(matches) == 1 else None


def _instrument_keys(instrument: Trading212Instrument) -> set[str]:
    ticker = instrument.ticker
    keys = {ticker.upper(), _base_symbol(ticker)}
    if instrument.isin:
        keys.add(instrument.isin.upper())
    return {key for key in keys if key}


def _symbol_keys(research_symbol: str, broker_symbol: str) -> set[str]:
    keys: set[str] = set()
    for value in [research_symbol, broker_symbol]:
        cleaned = value.strip().upper()
        if not cleaned:
            continue
        keys.add(cleaned)
        keys.add(_base_symbol(cleaned))
    return {key for key in keys if key}


def _base_symbol(symbol: str) -> str:
    raw = symbol.strip()
    cleaned = raw.upper()
    if cleaned.endswith(".L"):
        return cleaned[:-2]
    for suffix in ["_US_EQ", "_GB_EQ"]:
        if cleaned.endswith(suffix):
            return cleaned[: -len(suffix)]
    if cleaned.endswith("_EQ"):
        root = raw[:-3]
        if root.endswith("l"):
            root = root[:-1]
        return root.upper()
    if "_" in cleaned:
        cleaned = cleaned.split("_", 1)[0]
    return cleaned


def _currency(instrument: Trading212Instrument | None) -> str | None:
    return instrument.currency_code if instrument else None


def _is_symbol_specific(research_symbol: str) -> bool:
    return "." in research_symbol or "_" in research_symbol


def _is_london_listing(instrument: Trading212Instrument) -> bool:
    ticker = instrument.ticker
    upper_ticker = ticker.upper()
    return (
        _currency(instrument) in {"GBP", "GBX"} or "_GB_" in upper_ticker or ticker.endswith("l_EQ")
    )


def _isa_eligibility_text() -> str:
    return "requires_account_and_instrument_review"


def _not_configured_response(
    response: RecommendationsResponse, retrieved_at_utc: datetime
) -> InstrumentValidationResponse:
    return InstrumentValidationResponse(
        status="not_configured",
        environment=response.environment,
        retrieved_at_utc=require_utc(retrieved_at_utc),
        instrument_count=0,
        rows=[
            _status_row(item, InstrumentValidationStatus.NOT_CONFIGURED)
            for item in response.recommendations
        ],
        warnings=["Trading 212 credentials are not configured; instrument validation is offline."],
    )


def _error_response(
    response: RecommendationsResponse, retrieved_at_utc: datetime, message: str
) -> InstrumentValidationResponse:
    return InstrumentValidationResponse(
        status="error",
        environment=response.environment,
        retrieved_at_utc=require_utc(retrieved_at_utc),
        instrument_count=0,
        rows=[
            _status_row(item, InstrumentValidationStatus.ERROR) for item in response.recommendations
        ],
        warnings=[message],
    )


def _status_row(
    item: TradeRecommendation, status: InstrumentValidationStatus
) -> InstrumentValidationRow:
    return InstrumentValidationRow(
        symbol=item.candidate.symbol,
        research_symbol=item.candidate.research_symbol,
        source=item.candidate.source,
        status=status,
        isa_eligibility=_isa_eligibility_text(),
        reason="Trading 212 instrument metadata could not be loaded.",
    )
