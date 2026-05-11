"""Config-backed wider-market scan universe."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from isa_system.services.recommendations import DEFAULT_MARKET_CANDIDATES

DEFAULT_UNIVERSE_CONFIG_PATH = Path("configs/universe.example.yaml")


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
    block_tickers = set(_normalise_symbols(payload.get("block_tickers")))
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
