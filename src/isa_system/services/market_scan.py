"""Config-backed wider-market scan universe."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import httpx
import yaml
from pydantic import BaseModel, Field

from isa_system.data.providers.base import ProviderNotConfigured
from isa_system.data.providers.trading212 import Trading212Instrument
from isa_system.services.instrument_validation import load_trading212_instruments
from isa_system.services.recommendations import DEFAULT_MARKET_CANDIDATES
from isa_system.settings import Settings

DEFAULT_UNIVERSE_CONFIG_PATH = Path("configs/universe.example.yaml")
DEFAULT_BROKER_SCAN_LIMIT = 250
DEFAULT_DISPLAY_LIMIT = 50


class MarketScanUniverse(BaseModel):
    """Configured market-scan symbols and caveats."""

    name: str
    source_path: str | None = None
    symbols: list[str]
    blocked_symbols: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def load_market_scan_universe(
    path: Path | None = None, *, max_symbols: int = 50
) -> MarketScanUniverse:
    """Load the configured wider-market scan universe with safe fallbacks."""

    config_path = path or DEFAULT_UNIVERSE_CONFIG_PATH
    if not config_path.exists():
        return MarketScanUniverse(
            name="fallback_default_candidates",
            source_path=str(config_path),
            symbols=list(DEFAULT_MARKET_CANDIDATES),
            warnings=["Universe config was not found; using built-in starter scan candidates."],
        )

    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        return MarketScanUniverse(
            name="invalid_universe_config",
            source_path=str(config_path),
            symbols=list(DEFAULT_MARKET_CANDIDATES),
            warnings=[
                "Universe config did not contain a mapping; using built-in starter scan candidates."
            ],
        )

    include_tickers = _normalise_symbols(payload.get("include_tickers"))
    block_tickers = {symbol.upper() for symbol in _normalise_symbols(payload.get("block_tickers"))}
    symbols = [symbol for symbol in include_tickers if symbol.upper() not in block_tickers]
    warnings: list[str] = []
    if len(symbols) > max_symbols:
        symbols = symbols[:max_symbols]
        warnings.append(f"Market scan universe was capped at {max_symbols} symbols.")
    if not symbols:
        symbols = list(DEFAULT_MARKET_CANDIDATES)
        warnings.append(
            "Universe config had no included tickers; using built-in starter candidates."
        )
    return MarketScanUniverse(
        name=str(payload.get("name") or "configured_universe"),
        source_path=str(config_path),
        symbols=symbols,
        blocked_symbols=sorted(block_tickers),
        warnings=warnings,
    )


def load_broker_market_scan_universe(
    path: Path | None = None,
    *,
    settings: Settings | None = None,
    instruments: Sequence[Trading212Instrument] | None = None,
    max_loaded: int = DEFAULT_BROKER_SCAN_LIMIT,
    max_symbols: int = DEFAULT_DISPLAY_LIMIT,
) -> MarketScanUniverse:
    """Load a Trading 212 ISA-accessible scan universe with YAML fallback."""

    config_path = path or DEFAULT_UNIVERSE_CONFIG_PATH
    payload, config_warnings = _load_config_payload(config_path)
    warnings = list(config_warnings)
    supplied_instruments = instruments is not None
    if instruments is None:
        try:
            instruments = load_trading212_instruments(settings)
        except ProviderNotConfigured:
            return _fallback_universe(
                config_path,
                max_symbols=max_symbols,
                warning="Trading 212 metadata is not configured; using YAML market-scan fallback.",
            )
        except httpx.HTTPStatusError as exc:
            return _fallback_universe(
                config_path,
                max_symbols=max_symbols,
                warning=(
                    "Trading 212 metadata failed with "
                    f"HTTP {exc.response.status_code}; using YAML market-scan fallback."
                ),
            )
        except httpx.HTTPError as exc:
            return _fallback_universe(
                config_path,
                max_symbols=max_symbols,
                warning=(
                    f"Trading 212 metadata failed: {exc.__class__.__name__}; "
                    "using YAML market-scan fallback."
                ),
            )

    limited = list(instruments)
    if len(limited) > max_loaded:
        limited = limited[:max_loaded]
        warnings.append(f"Trading 212 broker universe was capped at {max_loaded} instruments.")

    filters = _broker_filters(payload)
    block_tickers = {symbol.upper() for symbol in _normalise_symbols(payload.get("block_tickers"))}
    symbols = _broker_research_symbols(limited, filters=filters, block_tickers=block_tickers)
    if len(symbols) > max_symbols:
        symbols = symbols[:max_symbols]
        warnings.append(f"Displayed broker scan universe was capped at {max_symbols} symbols.")
    if not symbols:
        fallback = load_market_scan_universe(config_path, max_symbols=max_symbols)
        fallback.warnings.append(
            "Trading 212 metadata produced no eligible instruments; using YAML fallback."
        )
        return fallback

    if not supplied_instruments:
        warnings.append(
            "Trading 212 instrument metadata is read-only universe discovery, not order approval."
        )
    return MarketScanUniverse(
        name=str(payload.get("name") or "trading212_broker_universe"),
        source_path="trading212:/equity/metadata/instruments",
        symbols=symbols,
        blocked_symbols=sorted(block_tickers),
        warnings=warnings,
    )


def _normalise_symbols(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        raw_values = [value]
    elif isinstance(value, list):
        raw_values = [str(item) for item in value]
    else:
        return []

    rows: list[str] = []
    seen: set[str] = set()
    for raw in raw_values:
        for part in raw.replace("\n", ",").split(","):
            symbol = part.strip()
            key = symbol.upper()
            if symbol and key not in seen:
                rows.append(symbol)
                seen.add(key)
    return rows


def _fallback_universe(config_path: Path, *, max_symbols: int, warning: str) -> MarketScanUniverse:
    universe = load_market_scan_universe(config_path, max_symbols=max_symbols)
    universe.warnings.append(warning)
    return universe


def _load_config_payload(config_path: Path) -> tuple[dict[str, Any], list[str]]:
    if not config_path.exists():
        return {}, ["Universe config was not found; broker scan will use default filters."]
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        return {}, ["Universe config did not contain a mapping; broker scan will use defaults."]
    return payload, []


def _broker_filters(payload: dict[str, Any]) -> dict[str, set[str]]:
    return {
        "allowed_asset_types": _upper_set(
            _normalise_symbols(payload.get("allowed_asset_types")) or ["STOCK", "ETF"]
        ),
        "allowed_currencies": _upper_set(
            _normalise_symbols(payload.get("allowed_currencies")) or ["GBP", "GBX", "USD"]
        ),
        "allowed_countries": _upper_set(
            _normalise_symbols(payload.get("allowed_countries")) or ["GB", "US", "IE"]
        ),
    }


def _broker_research_symbols(
    instruments: Sequence[Trading212Instrument],
    *,
    filters: dict[str, set[str]],
    block_tickers: set[str],
) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for instrument in instruments:
        symbol = _research_symbol_for_instrument(instrument)
        key = symbol.upper()
        if not symbol or key in seen or key in block_tickers:
            continue
        if instrument.ticker.upper() in block_tickers:
            continue
        if not _instrument_allowed(instrument, filters):
            continue
        rows.append(symbol)
        seen.add(key)
    return rows


def _instrument_allowed(instrument: Trading212Instrument, filters: dict[str, set[str]]) -> bool:
    asset_type = (instrument.type or "").upper()
    currency = (instrument.currency_code or "").upper()
    country = _instrument_country(instrument)
    return (
        asset_type in filters["allowed_asset_types"]
        and currency in filters["allowed_currencies"]
        and country in filters["allowed_countries"]
    )


def _research_symbol_for_instrument(instrument: Trading212Instrument) -> str:
    ticker = instrument.ticker.strip()
    upper = ticker.upper()
    if upper.endswith("_US_EQ"):
        return ticker[: -len("_US_EQ")].upper()
    if upper.endswith("_GB_EQ"):
        return f"{ticker[: -len('_GB_EQ')].upper()}.L"
    if upper.endswith("_EQ"):
        root = ticker[:-3]
        if root.endswith("l"):
            root = root[:-1]
        return f"{root.upper()}.L" if _instrument_country(instrument) == "GB" else root.upper()
    return ticker.upper()


def _instrument_country(instrument: Trading212Instrument) -> str:
    currency = (instrument.currency_code or "").upper()
    ticker = instrument.ticker
    upper_ticker = ticker.upper()
    if currency in {"GBP", "GBX"} or "_GB_" in upper_ticker or ticker.endswith("l_EQ"):
        return "GB"
    if currency == "USD" or "_US_" in upper_ticker:
        return "US"
    if currency == "EUR":
        return "IE"
    return "UNKNOWN"


def _upper_set(values: Sequence[str]) -> set[str]:
    return {value.upper() for value in values}
