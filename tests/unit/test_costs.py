"""Tests for transaction costs."""

from __future__ import annotations

from decimal import Decimal

from isa_system.portfolio.costs import CostModel, InstrumentCostFlags


def test_sdrt_applies_only_when_configured_or_heuristic_matches() -> None:
    """UK stock buys include SDRT, US buys include FX but not SDRT."""

    model = CostModel()
    uk = model.estimate(
        Decimal("1000"),
        side="BUY",
        instrument=InstrumentCostFlags(currency="GBP", country="GB", asset_type="STOCK"),
    )
    us = model.estimate(
        Decimal("1000"),
        side="BUY",
        instrument=InstrumentCostFlags(currency="USD", country="US", asset_type="STOCK"),
    )
    assert uk > us
    assert (
        model.is_sdrt_applicable(
            InstrumentCostFlags(currency="GBP", country="GB", asset_type="ETF")
        )
        is False
    )
