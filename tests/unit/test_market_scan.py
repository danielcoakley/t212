"""Tests for config-backed market scan universe."""

from __future__ import annotations

from pathlib import Path

import pytest

from isa_system.data.providers.base import ProviderNotConfigured
from isa_system.data.providers.trading212 import Trading212Instrument
from isa_system.services.market_scan import (
    load_broker_market_scan_universe,
    load_market_scan_universe,
)


def test_market_scan_universe_loads_include_and_block_lists(tmp_path: Path) -> None:
    """Universe config supplies deduplicated scan candidates and removes blocks."""

    path = tmp_path / "universe.yaml"
    path.write_text(
        """
name: test_scan
include_tickers:
  - AAPL
  - MSFT
  - aapl
  - TSCO.L
block_tickers:
  - MSFT
""",
        encoding="utf-8",
    )

    universe = load_market_scan_universe(path)

    assert universe.name == "test_scan"
    assert universe.symbols == ["AAPL", "TSCO.L"]
    assert universe.blocked_symbols == ["MSFT"]


def test_market_scan_universe_falls_back_when_missing(tmp_path: Path) -> None:
    """Missing config degrades to starter candidates."""

    universe = load_market_scan_universe(tmp_path / "missing.yaml")

    assert {"AAPL", "MSFT", "TSCO.L", "SHEL.L"}.issubset(set(universe.symbols))
    assert universe.warnings


def test_broker_market_scan_filters_trading212_instruments(tmp_path: Path) -> None:
    """Trading 212 metadata becomes the preferred broad scan universe."""

    path = tmp_path / "universe.yaml"
    path.write_text(
        """
name: broker_scan
allowed_asset_types: [STOCK]
allowed_currencies: [GBP, GBX, USD]
allowed_countries: [GB, US]
block_tickers: [BLOCK.L]
""",
        encoding="utf-8",
    )

    universe = load_broker_market_scan_universe(
        path,
        instruments=[
            Trading212Instrument(ticker="GOODl_EQ", currencyCode="GBX", type="STOCK"),
            Trading212Instrument(ticker="AAPL_US_EQ", currencyCode="USD", type="STOCK"),
            Trading212Instrument(ticker="BOND_US_EQ", currencyCode="USD", type="ETF"),
            Trading212Instrument(ticker="BLOCKl_EQ", currencyCode="GBX", type="STOCK"),
            Trading212Instrument(ticker="EURO_EQ", currencyCode="EUR", type="STOCK"),
        ],
        max_loaded=10,
        max_symbols=10,
    )

    assert universe.source_path == "trading212:/equity/metadata/instruments"
    assert universe.symbols == ["GOOD.L", "AAPL"]
    assert universe.blocked_symbols == ["BLOCK.L"]


def test_broker_market_scan_falls_back_to_yaml_when_metadata_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unavailable broker metadata keeps the app runnable with YAML candidates."""

    path = tmp_path / "universe.yaml"
    path.write_text(
        """
name: fallback_scan
include_tickers: [AAPL, TSCO.L]
""",
        encoding="utf-8",
    )

    def raise_not_configured(settings=None):
        raise ProviderNotConfigured("missing")

    monkeypatch.setattr(
        "isa_system.services.market_scan.load_trading212_instruments",
        raise_not_configured,
    )

    universe = load_broker_market_scan_universe(path)

    assert universe.symbols == ["AAPL", "TSCO.L"]
    assert any("YAML market-scan fallback" in warning for warning in universe.warnings)
