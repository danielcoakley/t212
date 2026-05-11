"""Dashboard dataframe tests for the simplified MVP recommendation queue."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from isa_system.dashboard.cache_policy import MarketCacheWindow
from isa_system.dashboard.recommendation_charts import (
    consolidated_recommendation_frame,
    identity_diagnostics_frame,
    recommendation_source_freshness_rows,
)
from isa_system.data.providers.trading212 import Trading212Instrument
from isa_system.services.instrument_validation import validate_recommendation_instruments
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot
from isa_system.services.recommendation_handoff import build_recommendation_handoff
from isa_system.services.recommendations import build_recommendations_from_static_data
from isa_system.services.valuation import DailyAdjustedClose, HoldingValuationData, ValuationMetrics


def test_consolidated_recommendation_view_contains_mvp_gate_columns() -> None:
    """The front-stage table contains action, blockers, broker check, research, and preview."""

    response = build_recommendations_from_static_data(
        BrokerPortfolioSnapshot(
            status="live",
            environment="live",
            retrieved_at_utc=datetime(2026, 5, 10, tzinfo=UTC),
            positions=[],
            warnings=[],
        ),
        {
            "GOOD.L": HoldingValuationData(
                symbol="GOOD.L",
                retrieved_at_utc=datetime(2026, 5, 10, tzinfo=UTC),
                daily_adjusted_closes=[
                    DailyAdjustedClose(
                        ts_utc=datetime(2025, 1, 1, tzinfo=UTC) + timedelta(days=index),
                        adj_close=float(index + 1),
                    )
                    for index in range(260)
                ],
                valuation=ValuationMetrics(trailing_pe=8.0, dividend_yield=0.05),
            )
        },
        candidates=["GOOD.L"],
        include_default_candidates=False,
        as_of_utc=datetime(2026, 5, 10, tzinfo=UTC),
    )
    validation = validate_recommendation_instruments(
        response,
        instruments=[Trading212Instrument(ticker="GOODl_EQ", currencyCode="GBX", type="STOCK")],
    )
    handoff = build_recommendation_handoff(response, instrument_validation=validation)

    frame = consolidated_recommendation_frame(response, handoff, validation)

    assert {
        "action",
        "review_state",
        "broker_gate",
        "research_gate",
        "evidence_coverage",
        "source_caveats",
        "preview_blockers",
        "broker_validation",
        "instrument_validation_confidence",
        "identity_caveats",
        "isin",
        "research_review_status",
        "preview_eligible",
    }.issubset(frame.columns)
    assert frame.loc[0, "action"] == "REVIEW_BUY"
    assert frame.loc[0, "broker_validation"] == "BROKER_MATCHED"
    assert frame.loc[0, "instrument_validation_confidence"] == "MEDIUM"
    assert "confidence MEDIUM" in frame.loc[0, "broker_gate"]
    assert "ISIN_MISSING" in frame.loc[0, "identity_caveats"]
    assert frame.loc[0, "review_state"] == "Needs research"
    assert frame.loc[0, "research_gate"] == "Required: MISSING"
    assert "OFFICIAL_SOURCE_REVIEW_REQUIRED" in frame.loc[0, "source_caveats"]
    assert "ISIN_MISSING" in frame.loc[0, "source_caveats"]
    assert "DEEP_RESEARCH_REQUIRED" in frame.loc[0, "preview_blockers"]


def test_identity_diagnostics_frame_exposes_mismatch_caveats() -> None:
    """Focused identity helper shows broker candidates, confidence, and caveats."""

    response = build_recommendations_from_static_data(
        BrokerPortfolioSnapshot(
            status="live",
            environment="live",
            retrieved_at_utc=datetime(2026, 5, 10, tzinfo=UTC),
            positions=[],
            warnings=[],
        ),
        {
            "ABC": HoldingValuationData(
                symbol="ABC",
                retrieved_at_utc=datetime(2026, 5, 10, tzinfo=UTC),
                daily_adjusted_closes=[
                    DailyAdjustedClose(
                        ts_utc=datetime(2025, 1, 1, tzinfo=UTC) + timedelta(days=index),
                        adj_close=float(index + 1),
                    )
                    for index in range(260)
                ],
                valuation=ValuationMetrics(trailing_pe=8.0, dividend_yield=0.05),
            )
        },
        candidates=["ABC"],
        include_default_candidates=False,
        as_of_utc=datetime(2026, 5, 10, tzinfo=UTC),
    )
    validation = validate_recommendation_instruments(
        response,
        instruments=[
            Trading212Instrument(ticker="ABC_US_EQ", currencyCode="USD", type="STOCK"),
            Trading212Instrument(ticker="ABCl_EQ", currencyCode="GBX", type="STOCK"),
        ],
    )

    frame = identity_diagnostics_frame(validation)

    assert frame.loc[0, "research_symbol"] == "ABC"
    assert frame.loc[0, "validation_status"] == "NEEDS_MAPPING"
    assert frame.loc[0, "validation_confidence"] == "LOW"
    assert frame.loc[0, "candidate_broker_tickers"] == "ABC_US_EQ, ABCl_EQ"
    assert "MULTIPLE_BROKER_TICKERS_REQUIRE_MAPPING" in frame.loc[0, "mismatch_caveats"]


def test_recommendation_view_exposes_source_freshness_and_stale_caveats() -> None:
    """Dashboard-only freshness columns make stale provider context visible."""

    response = build_recommendations_from_static_data(
        BrokerPortfolioSnapshot(
            status="live",
            environment="live",
            retrieved_at_utc=datetime(2026, 5, 10, 10, tzinfo=UTC),
            positions=[],
            warnings=[],
        ),
        {
            "GOOD.L": HoldingValuationData(
                symbol="GOOD.L",
                retrieved_at_utc=datetime(2026, 5, 10, 10, tzinfo=UTC),
                daily_adjusted_closes=[
                    DailyAdjustedClose(
                        ts_utc=datetime(2025, 1, 1, tzinfo=UTC) + timedelta(days=index),
                        adj_close=float(index + 1),
                    )
                    for index in range(260)
                ],
                valuation=ValuationMetrics(trailing_pe=8.0, dividend_yield=0.05),
            )
        },
        candidates=["GOOD.L"],
        include_default_candidates=False,
        as_of_utc=datetime(2026, 5, 10, 10, tzinfo=UTC),
    )
    validation = validate_recommendation_instruments(
        response,
        instruments=[Trading212Instrument(ticker="GOODl_EQ", currencyCode="GBX", type="STOCK")],
    )
    handoff = build_recommendation_handoff(response, instrument_validation=validation)
    window = _window(
        opened_at=datetime(2026, 5, 11, 8, tzinfo=UTC),
        next_refresh_at=datetime(2026, 5, 11, 14, tzinfo=UTC),
    )

    rows = recommendation_source_freshness_rows(
        response,
        handoff,
        validation,
        cache_window=window,
        cache_source="disk cache",
        as_of_utc=datetime(2026, 5, 11, 9, tzinfo=UTC),
    )
    frame = consolidated_recommendation_frame(
        response,
        handoff,
        validation,
        cache_window=window,
        cache_source="disk cache",
        as_of_utc=datetime(2026, 5, 11, 9, tzinfo=UTC),
    )
    rows_by_item = {row["Source item"]: row for row in rows}

    assert rows_by_item["Recommendation bundle"]["Status"] == "Stale"
    assert rows_by_item["Broker metadata validation"]["Status"] == "Stale"
    assert "source_freshness" in frame.columns
    assert frame.loc[0, "source_freshness"] == "Stale"
    assert "Recommendation bundle: 23h 0m old" in frame.loc[0, "source_age"]
    assert frame.loc[0, "cache_context"] == "London open cache; disk cache"
    assert "SOURCE_REFRESH_RECOMMENDED" in frame.loc[0, "source_caveats"]


def _window(opened_at: datetime, next_refresh_at: datetime) -> MarketCacheWindow:
    return MarketCacheWindow(
        key="20260511-london_open",
        label="London open cache",
        opened_at_utc=opened_at,
        next_refresh_at_utc=next_refresh_at,
        manual_refresh_hint="Refresh manually when broker state changes.",
    )
