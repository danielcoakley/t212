"""Tests for config-backed market scan universe."""

from __future__ import annotations

from pathlib import Path

from isa_system.services.market_scan import load_market_scan_universe


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
