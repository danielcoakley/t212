"""Tests for explainable screener funnel stages."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from isa_system.data.providers.trading212 import Trading212Instrument
from isa_system.services.instrument_validation import validate_recommendation_instruments
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot
from isa_system.services.recommendation_handoff import build_recommendation_handoff
from isa_system.services.recommendations import build_recommendations_from_static_data
from isa_system.services.screener_funnel import build_screener_funnel
from isa_system.services.valuation import DailyAdjustedClose, HoldingValuationData, ValuationMetrics


def test_screener_funnel_explains_additive_filters() -> None:
    """The funnel shows universe, evidence removals, and final research candidates."""

    as_of = datetime(2026, 5, 10, tzinfo=UTC)
    response = build_recommendations_from_static_data(
        BrokerPortfolioSnapshot(
            status="live",
            environment="live",
            retrieved_at_utc=as_of,
            positions=[],
            warnings=[],
        ),
        {
            "GOOD.L": HoldingValuationData(
                symbol="GOOD.L",
                retrieved_at_utc=as_of,
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
        candidates=["GOOD.L", "NODATA.L"],
        include_default_candidates=False,
        as_of_utc=as_of,
    )
    validation = validate_recommendation_instruments(
        response,
        instruments=[
            Trading212Instrument(ticker="GOODl_EQ", currencyCode="GBX", type="STOCK"),
            Trading212Instrument(ticker="NODATAl_EQ", currencyCode="GBX", type="STOCK"),
        ],
    )
    handoff = build_recommendation_handoff(response, instrument_validation=validation)

    funnel = build_screener_funnel(
        response,
        validation,
        handoff,
        universe_symbols=["GOOD.L", "NODATA.L", "UNSCORED.L"],
    )

    assert funnel.universe_count == 3
    assert funnel.scored_count == 2
    assert funnel.unscored_count == 1
    seed_stage = next(stage for stage in funnel.stages if stage.stage_id == "seed")
    assert seed_stage.starting_count == 3
    assert seed_stage.removal_reasons["NOT_SCORED_AFTER_PROVIDER_NORMALISATION"] == 1
    evidence_stage = next(
        stage for stage in funnel.stages if stage.stage_id == "evidence_available"
    )
    assert any(row.research_symbol == "NODATA.L" for row in evidence_stage.removed_rows)
    assert any(
        reason == "MISSING_FUNDAMENTALS"
        for row in evidence_stage.removed_rows
        for reason in row.reasons
    )
    assert [row.research_symbol for row in funnel.final_candidates] == ["GOOD.L"]
