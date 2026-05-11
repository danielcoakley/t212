"""Tests for Trading 212 instrument metadata validation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from isa_system.data.providers.trading212 import Trading212Instrument
from isa_system.services.instrument_validation import (
    InstrumentValidationStatus,
    validate_recommendation_instruments,
)
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot, BrokerPosition
from isa_system.services.recommendations import build_recommendations_from_static_data
from isa_system.services.valuation import DailyAdjustedClose, HoldingValuationData, ValuationMetrics


def test_market_candidate_matches_trading212_metadata() -> None:
    """A specific UK research symbol can match a Trading 212 broker ticker."""

    recommendations = build_recommendations_from_static_data(
        _snapshot(positions=[]),
        {
            "GOOD.L": _provider_row(
                "GOOD.L",
                ValuationMetrics(trailing_pe=8.0, price_to_book=1.0, dividend_yield=0.04),
            )
        },
        candidates=["GOOD.L"],
        include_default_candidates=False,
        as_of_utc=datetime(2026, 5, 10, tzinfo=UTC),
    )

    response = validate_recommendation_instruments(
        recommendations,
        instruments=[
            Trading212Instrument(
                ticker="GOODl_EQ",
                name="Good plc",
                isin="GB00GOOD0001",
                currencyCode="GBX",
                type="STOCK",
            )
        ],
    )

    row = response.rows[0]

    assert response.instrument_count == 1
    assert row.status == InstrumentValidationStatus.BROKER_MATCHED
    assert row.broker_ticker == "GOODl_EQ"
    assert row.isa_eligibility == "requires_account_and_instrument_review"


def test_uk_suffix_prefers_london_listing_over_us_match() -> None:
    """A `.L` research symbol should prefer the London-style Trading 212 ticker."""

    recommendations = build_recommendations_from_static_data(
        _snapshot(positions=[]),
        {"SHEL.L": _provider_row("SHEL.L", ValuationMetrics(trailing_pe=9.0))},
        candidates=["SHEL.L"],
        include_default_candidates=False,
        as_of_utc=datetime(2026, 5, 10, tzinfo=UTC),
    )

    response = validate_recommendation_instruments(
        recommendations,
        instruments=[
            Trading212Instrument(ticker="SHEL_US_EQ", currencyCode="USD", type="STOCK"),
            Trading212Instrument(ticker="SHELl_EQ", currencyCode="GBX", type="STOCK"),
        ],
    )

    row = response.rows[0]

    assert row.status == InstrumentValidationStatus.BROKER_MATCHED
    assert row.broker_ticker == "SHELl_EQ"


def test_ambiguous_symbol_requires_mapping() -> None:
    """Ambiguous ticker roots are not silently mapped to a broker ticker."""

    recommendations = build_recommendations_from_static_data(
        _snapshot(positions=[]),
        {"ABC": _provider_row("ABC", ValuationMetrics(trailing_pe=12.0))},
        candidates=["ABC"],
        include_default_candidates=False,
        as_of_utc=datetime(2026, 5, 10, tzinfo=UTC),
    )

    response = validate_recommendation_instruments(
        recommendations,
        instruments=[
            Trading212Instrument(ticker="ABC_US_EQ", currencyCode="USD", type="STOCK"),
            Trading212Instrument(ticker="ABCl_EQ", currencyCode="GBX", type="STOCK"),
        ],
    )

    row = response.rows[0]

    assert row.status == InstrumentValidationStatus.NEEDS_MAPPING
    assert row.candidate_broker_tickers == ["ABC_US_EQ", "ABCl_EQ"]


def test_existing_holding_is_confirmed_even_without_metadata_match() -> None:
    """Broker positions are already broker-known, even if metadata cache is incomplete."""

    recommendations = build_recommendations_from_static_data(
        _snapshot(),
        {"SHEL.L": _provider_row("SHEL.L", ValuationMetrics(trailing_pe=9.0))},
        include_default_candidates=False,
        as_of_utc=datetime(2026, 5, 10, tzinfo=UTC),
    )

    response = validate_recommendation_instruments(recommendations, instruments=[])
    row = response.rows[0]

    assert row.status == InstrumentValidationStatus.HOLDING_CONFIRMED
    assert row.broker_ticker == "SHEL_GB_EQ"
    assert row.reason == "Existing holding is confirmed by the broker positions endpoint."


def _snapshot(
    positions: list[BrokerPosition] | None = None,
) -> BrokerPortfolioSnapshot:
    return BrokerPortfolioSnapshot(
        status="live",
        environment="live",
        retrieved_at_utc=datetime(2026, 5, 10, 10, 0, tzinfo=UTC),
        positions=positions
        if positions is not None
        else [
            BrokerPosition(
                symbol="SHEL_GB_EQ",
                broker_ticker="SHEL_GB_EQ",
                name="Shell",
                currency="GBP",
                quantity=10,
                current_value=250,
            )
        ],
        warnings=[],
    )


def _provider_row(symbol: str, valuation: ValuationMetrics) -> HoldingValuationData:
    return HoldingValuationData(
        symbol=symbol,
        retrieved_at_utc=datetime(2026, 5, 10, 10, 1, tzinfo=UTC),
        daily_adjusted_closes=_closes(260),
        valuation=valuation,
    )


def _closes(count: int) -> list[DailyAdjustedClose]:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    return [
        DailyAdjustedClose(ts_utc=start + timedelta(days=index), adj_close=float(index + 1))
        for index in range(count)
    ]
