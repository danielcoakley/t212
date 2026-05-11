"""Tests for offline-safe holdings valuation service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from isa_system.services.portfolio_state import BrokerPortfolioSnapshot, BrokerPosition
from isa_system.services.valuation import (
    DailyAdjustedClose,
    HoldingValuationData,
    StaticValuationProvider,
    UpcomingEvent,
    ValuationMetrics,
    _coerce_event_datetime,
    calculate_technicals,
    research_symbol_for_position,
    value_current_holdings,
)


def test_calculate_technicals_from_daily_adjusted_closes() -> None:
    """Daily adjusted closes produce core technical indicators."""

    closes = _closes(260)
    warnings: list[str] = []

    technicals = calculate_technicals(closes, warnings)

    assert technicals.sma50 == 235.5
    assert technicals.sma200 == 160.5
    assert technicals.rsi14 == 100.0
    assert technicals.momentum_1m == (260 / 239) - 1
    assert technicals.momentum_3m == (260 / 197) - 1
    assert technicals.momentum_6m == (260 / 134) - 1
    assert technicals.momentum_12m == (260 / 8) - 1
    assert warnings == []


def test_value_current_holdings_uses_static_provider_offline() -> None:
    """The valuation service can be fed deterministic provider data."""

    snapshot = _snapshot()
    provider = StaticValuationProvider(
        {
            "SHEL.L": HoldingValuationData(
                symbol="SHEL.L",
                retrieved_at_utc=datetime(2026, 5, 10, 10, 1, tzinfo=UTC),
                daily_adjusted_closes=_closes(260),
                valuation=ValuationMetrics(
                    trailing_pe=8.2,
                    forward_pe=7.9,
                    price_to_book=1.3,
                    dividend_yield=0.041,
                    market_cap=180_000_000_000,
                    beta=0.9,
                ),
            )
        }
    )

    response = value_current_holdings(snapshot, provider)

    assert response.provider == "static"
    assert response.retrieved_at_utc.tzinfo == UTC
    assert response.holdings[0].symbol == "SHEL.L"
    assert response.holdings[0].research_symbol == "SHEL.L"
    assert response.holdings[0].valuation.trailing_pe == 8.2
    assert response.holdings[0].technicals.sma50 == 235.5
    assert response.holdings[0].warnings == []


def test_value_current_holdings_warns_when_provider_data_missing() -> None:
    """Missing provider data creates warnings instead of failing."""

    response = value_current_holdings(_snapshot(), StaticValuationProvider())

    assert response.holdings[0].valuation.trailing_pe is None
    assert response.holdings[0].technicals.sma50 is None
    assert "No valuation provider data for SHEL.L." in response.warnings
    assert any(
        "Daily adjusted closes are missing" in item for item in response.holdings[0].warnings
    )


def test_research_symbol_mapping_handles_common_trading212_tickers() -> None:
    """Platform tickers are mapped conservatively for research convenience feeds."""

    us_position = BrokerPosition(
        symbol="AAPL_US_EQ",
        broker_ticker="AAPL_US_EQ",
        currency="USD",
        quantity=1,
    )
    uk_position = BrokerPosition(
        symbol="SHEL_GB_EQ",
        broker_ticker="SHEL_GB_EQ",
        currency="GBP",
        quantity=1,
    )

    assert research_symbol_for_position(us_position) == "AAPL"
    assert research_symbol_for_position(uk_position) == "SHEL.L"


def test_calendar_non_dates_are_rejected() -> None:
    """Provider estimate fields must not leak NaT values into API responses."""

    assert _coerce_event_datetime(float("nan")) is None
    event = UpcomingEvent(event_type="Earnings High", ts_utc=None)

    assert event.model_dump_json()


def _snapshot() -> BrokerPortfolioSnapshot:
    return BrokerPortfolioSnapshot(
        status="live",
        environment="live",
        retrieved_at_utc=datetime(2026, 5, 10, 10, 0, tzinfo=UTC),
        positions=[
            BrokerPosition(
                symbol="SHEL.L",
                broker_ticker="SHEL_GB_EQ",
                name="Shell",
                currency="GBP",
                quantity=25,
                current_price=40,
                current_value=1_000,
            )
        ],
        warnings=[],
    )


def _closes(count: int) -> list[DailyAdjustedClose]:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    return [
        DailyAdjustedClose(ts_utc=start + timedelta(days=index), adj_close=float(index + 1))
        for index in range(count)
    ]
