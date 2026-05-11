"""Tests for preview-only rebalance planning."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

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


def test_build_preview_from_holdings_blocks_trade_rows() -> None:
    """Preview target drift is costed but not made submittable."""

    preview = build_preview_from_holdings(
        _broker_snapshot(),
        _valuation_snapshot(),
        preview_settings=RebalancePreviewSettings(min_trade_notional_gbp=Decimal("1")),
    )

    assert preview.mode.value == "preview"
    assert preview.rows
    assert any(row.status == "preview_blocked" for row in preview.rows)
    assert preview.estimated_total_cost >= Decimal("0")
    assert preview.batch_hash
    assert any(check.name == "duplicate_order_prevention" for check in preview.risk_checks)


def test_non_gbp_buy_gets_fx_cost_and_sdrt_is_uk_only() -> None:
    """Cost components are separated for FX and UK share taxes."""

    preview = build_preview_from_holdings(
        _broker_snapshot(),
        _valuation_snapshot(),
        preview_settings=RebalancePreviewSettings(min_trade_notional_gbp=Decimal("1")),
    )
    rows = {row.symbol: row for row in preview.rows}

    assert rows["AAPL_US_EQ"].costs.fx_cost >= Decimal("0")
    assert rows["AAPL_US_EQ"].costs.sdrt == Decimal("0.00")
    if rows["SHEL_GB_EQ"].side == "BUY":
        assert rows["SHEL_GB_EQ"].costs.sdrt >= Decimal("0")


def _broker_snapshot() -> BrokerPortfolioSnapshot:
    return BrokerPortfolioSnapshot(
        status="live",
        environment="live",
        retrieved_at_utc=datetime(2026, 5, 11, tzinfo=UTC),
        account_currency="GBP",
        total_value=1000,
        available_to_trade=10,
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
