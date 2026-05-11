"""Tests for read-only broker portfolio analytics."""

from __future__ import annotations

from datetime import UTC, datetime

from isa_system.services.portfolio_analytics import summarise_portfolio
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot, BrokerPosition


def test_summarise_portfolio_calculates_read_only_analytics() -> None:
    """Portfolio analytics include totals, exposures, P/L and missing-value warnings."""

    snapshot = BrokerPortfolioSnapshot(
        status="live",
        environment="live",
        retrieved_at_utc=datetime(2026, 5, 10, 9, 30, tzinfo=UTC),
        account_currency="GBP",
        total_value=10_000.0,
        available_to_trade=1_500.0,
        reserved_for_orders=100.0,
        positions=[
            BrokerPosition(
                symbol="AAPL",
                broker_ticker="AAPL_US_EQ",
                name="Apple",
                currency="USD",
                quantity=5.0,
                current_value=3_000.0,
                unrealised_profit_loss=250.0,
            ),
            BrokerPosition(
                symbol="TSCO.L",
                broker_ticker="TSCO_GB_EQ",
                name="Tesco",
                currency="GBP",
                quantity=100.0,
                current_value=2_000.0,
                unrealised_profit_loss=-50.0,
            ),
            BrokerPosition(
                symbol="MISSING",
                broker_ticker="MISSING_EQ",
                currency="GBP",
                quantity=3.0,
                current_value=None,
                unrealised_profit_loss=None,
            ),
        ],
        warnings=["source warning"],
    )

    summary = summarise_portfolio(snapshot, top_n=2)

    assert summary.total_value == 10_000.0
    assert summary.invested_value == 5_000.0
    assert summary.cash_fraction == 0.15
    assert summary.unrealised_profit_loss_total == 200.0
    assert summary.concentration.position_count == 2
    assert summary.concentration.max_position_weight == 0.3
    assert summary.concentration.top_five_weight == 0.5
    assert summary.top_positions[0].symbol == "AAPL"
    assert {row.currency: row.weight for row in summary.currency_exposure} == {
        "GBP": 0.2,
        "USD": 0.3,
    }
    assert "source warning" in summary.warnings
    assert any("Missing current_value" in warning for warning in summary.warnings)


def test_summarise_portfolio_derives_total_when_broker_total_missing() -> None:
    """A missing broker total uses known valued positions and cash with a warning."""

    snapshot = BrokerPortfolioSnapshot(
        status="live",
        environment="live",
        retrieved_at_utc=datetime(2026, 5, 10, 9, 30, tzinfo=UTC),
        available_to_trade=500.0,
        reserved_for_orders=50.0,
        positions=[
            BrokerPosition(
                symbol="MSFT",
                broker_ticker="MSFT_US_EQ",
                currency="USD",
                quantity=2.0,
                current_value=1_000.0,
            )
        ],
        warnings=[],
    )

    summary = summarise_portfolio(snapshot)

    assert summary.total_value == 1_550.0
    assert summary.cash_fraction == 500.0 / 1_550.0
    assert any("derived read-only estimate" in warning for warning in summary.warnings)
