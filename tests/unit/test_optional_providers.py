"""Tests for optional providers when keys are absent."""

from __future__ import annotations

from pathlib import Path

from isa_system.data.providers.alpha_vantage import AlphaVantageProvider
from isa_system.data.providers.fmp import FMPProvider
from isa_system.data.providers.fred_api import FREDProvider


def test_missing_keys_return_empty_frames(tmp_path: Path) -> None:
    """Optional convenience providers degrade gracefully."""

    assert AlphaVantageProvider(None, tmp_path).daily_adjusted("AAPL").empty
    assert FMPProvider(None, tmp_path).company_profile("AAPL").empty
    assert FREDProvider(None, tmp_path).observations("DGS10").empty
