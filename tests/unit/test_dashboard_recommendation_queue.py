"""Dashboard dataframe tests for the simplified MVP recommendation queue."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from isa_system.dashboard.recommendation_charts import consolidated_recommendation_frame
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
        "research_review_status",
        "preview_eligible",
    }.issubset(frame.columns)
    assert frame.loc[0, "action"] == "REVIEW_BUY"
    assert frame.loc[0, "broker_validation"] == "BROKER_MATCHED"
    assert frame.loc[0, "review_state"] == "Needs research"
    assert frame.loc[0, "research_gate"] == "Required: MISSING"
    assert "OFFICIAL_SOURCE_REVIEW_REQUIRED" in frame.loc[0, "source_caveats"]
    assert "DEEP_RESEARCH_REQUIRED" in frame.loc[0, "preview_blockers"]
