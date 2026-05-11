"""Tests for preview-derived paper simulation."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from isa_system.services.paper_simulation import simulate_paper_fills
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot, BrokerPosition
from isa_system.services.rebalance_preview import (
    RebalancePreviewSettings,
    build_preview_from_holdings,
)
from isa_system.services.valuation import (
    HoldingsValuationResponse,
    HoldingValuation,
    TechnicalIndicators,
    ValuationMetrics,
)


def test_simulate_paper_fills_from_preview_rows() -> None:
    """Preview-blocked rows can be converted to local paper-fill rows."""

    preview = build_preview_from_holdings(
        _broker_snapshot(),
        _valuation_snapshot(),
        preview_settings=RebalancePreviewSettings(min_trade_notional_gbp=Decimal("1")),
    )
    simulation = simulate_paper_fills(preview)

    assert simulation.source_batch_hash == preview.batch_hash
    assert simulation.fill_count == len(simulation.fills)
    assert simulation.simulation_hash
    assert all(fill.status == "simulated" for fill in simulation.fills)
    assert any("no order is sent" in warning for warning in simulation.warnings)


def _broker_snapshot() -> BrokerPortfolioSnapshot:
    return BrokerPortfolioSnapshot(
        status="live",
        environment="live",
        retrieved_at_utc=datetime(2026, 5, 11, tzinfo=UTC),
        account_currency="GBP",
        total_value=1000,
        positions=[
            BrokerPosition(
                symbol="AAPL_US_EQ",
                broker_ticker="AAPL_US_EQ",
                name="Apple",
                currency="USD",
                quantity=2,
                current_value=500,
            ),
            BrokerPosition(
                symbol="SHEL_GB_EQ",
                broker_ticker="SHEL_GB_EQ",
                name="Shell",
                currency="GBP",
                quantity=20,
                current_value=490,
            ),
        ],
        warnings=[],
    )


def _valuation_snapshot() -> HoldingsValuationResponse:
    return HoldingsValuationResponse(
        status="live",
        environment="live",
        retrieved_at_utc=datetime(2026, 5, 11, tzinfo=UTC),
        provider="static",
        holdings=[
            HoldingValuation(
                symbol="AAPL_US_EQ",
                broker_ticker="AAPL_US_EQ",
                research_symbol="AAPL",
                name="Apple",
                currency="USD",
                quantity=2,
                current_value=500,
                valuation=ValuationMetrics(trailing_pe=25, dividend_yield=0.005),
                technicals=TechnicalIndicators(momentum_3m=0.2),
                upcoming_events=[],
                news=[],
                warnings=[],
            ),
            HoldingValuation(
                symbol="SHEL_GB_EQ",
                broker_ticker="SHEL_GB_EQ",
                research_symbol="SHEL.L",
                name="Shell",
                currency="GBP",
                quantity=20,
                current_value=490,
                valuation=ValuationMetrics(trailing_pe=8, dividend_yield=0.04),
                technicals=TechnicalIndicators(momentum_3m=0.05),
                upcoming_events=[],
                news=[],
                warnings=[],
            ),
        ],
        warnings=[],
    )
