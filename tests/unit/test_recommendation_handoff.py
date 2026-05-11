"""Tests for review-only recommendation hand-off logic."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from isa_system.services.portfolio_state import BrokerPortfolioSnapshot, BrokerPosition
from isa_system.services.recommendation_handoff import (
    HandoffStatus,
    build_recommendation_handoff,
)
from isa_system.services.recommendations import (
    RecommendationAction,
    build_recommendations_from_static_data,
)
from isa_system.services.valuation import DailyAdjustedClose, HoldingValuationData, ValuationMetrics


def test_weak_holding_review_sell_is_preview_eligible() -> None:
    """A weak existing holding can be handed to preview review as a sell candidate."""

    response = build_recommendations_from_static_data(
        _snapshot(),
        {
            "SHEL.L": _provider_row(
                "SHEL.L",
                valuation=ValuationMetrics(
                    trailing_pe=80.0,
                    forward_pe=70.0,
                    price_to_book=12.0,
                    dividend_yield=0.0,
                ),
                closes=_declining_closes(260),
            )
        },
        include_default_candidates=False,
        as_of_utc=datetime(2026, 5, 10, tzinfo=UTC),
    )

    handoff = build_recommendation_handoff(response)
    row = handoff.rows[0]

    assert row.recommendation_action == RecommendationAction.REVIEW_SELL
    assert row.handoff_status == HandoffStatus.ELIGIBLE
    assert row.proposed_preview_action == "SELL"
    assert handoff.eligible_count == 1


def test_market_scan_review_buy_needs_broker_validation() -> None:
    """A wider-market review buy stays blocked from preview until instrument validation."""

    response = build_recommendations_from_static_data(
        _snapshot(positions=[]),
        {
            "GOOD.L": _provider_row(
                "GOOD.L",
                valuation=ValuationMetrics(
                    trailing_pe=8.0,
                    forward_pe=7.0,
                    price_to_book=1.0,
                    dividend_yield=0.05,
                ),
                closes=_rising_closes(260),
            )
        },
        candidates=["GOOD.L"],
        include_default_candidates=False,
        as_of_utc=datetime(2026, 5, 10, tzinfo=UTC),
    )

    handoff = build_recommendation_handoff(response)
    row = handoff.rows[0]

    assert row.recommendation_action == RecommendationAction.REVIEW_BUY
    assert row.handoff_status == HandoffStatus.REVIEW_REQUIRED
    assert row.proposed_preview_action == "BUY"
    assert "BROKER_INSTRUMENT_VALIDATION_REQUIRED" in row.blockers
    assert handoff.review_required_count == 1


def test_blocked_recommendation_does_not_hand_off_to_preview() -> None:
    """Rows blocked by missing data remain blocked in the hand-off layer."""

    response = build_recommendations_from_static_data(
        _snapshot(positions=[]),
        {},
        candidates=["UNKNOWN.L"],
        include_default_candidates=False,
        as_of_utc=datetime(2026, 5, 10, tzinfo=UTC),
    )

    handoff = build_recommendation_handoff(response)
    row = handoff.rows[0]

    assert row.recommendation_action == RecommendationAction.BLOCKED
    assert row.handoff_status == HandoffStatus.BLOCKED
    assert row.proposed_preview_action == "HOLD"
    assert "MISSING_FUNDAMENTALS" in row.blockers
    assert "MISSING_TECHNICALS" in row.blockers


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
                symbol="SHEL.L",
                broker_ticker="SHEL_GB_EQ",
                name="Shell",
                currency="GBP",
                quantity=10,
                current_value=250,
            )
        ],
        warnings=[],
    )


def _provider_row(
    symbol: str,
    *,
    valuation: ValuationMetrics,
    closes: list[DailyAdjustedClose],
) -> HoldingValuationData:
    return HoldingValuationData(
        symbol=symbol,
        retrieved_at_utc=datetime(2026, 5, 10, 10, 1, tzinfo=UTC),
        daily_adjusted_closes=closes,
        valuation=valuation,
    )


def _rising_closes(count: int) -> list[DailyAdjustedClose]:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    return [
        DailyAdjustedClose(ts_utc=start + timedelta(days=index), adj_close=float(index + 1))
        for index in range(count)
    ]


def _declining_closes(count: int) -> list[DailyAdjustedClose]:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    return [
        DailyAdjustedClose(ts_utc=start + timedelta(days=index), adj_close=float(count - index))
        for index in range(count)
    ]
