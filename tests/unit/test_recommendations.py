"""Tests for offline-safe recommendation service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from isa_system.services.portfolio_state import BrokerPortfolioSnapshot, BrokerPosition
from isa_system.services.recommendations import (
    RecommendationAction,
    build_recommendations_from_static_data,
)
from isa_system.services.valuation import (
    DailyAdjustedClose,
    HoldingValuationData,
    SentimentSnapshot,
    UpcomingEvent,
    ValuationMetrics,
)


def test_recommendations_cover_holdings_and_default_market_scan_offline() -> None:
    """Static provider data produces holdings plus wider market recommendations."""

    response = build_recommendations_from_static_data(
        _snapshot(),
        {
            "SHEL.L": _provider_row(
                "SHEL.L",
                valuation=ValuationMetrics(
                    trailing_pe=8.0,
                    forward_pe=7.5,
                    price_to_book=1.1,
                    dividend_yield=0.05,
                    beta=0.9,
                ),
                sentiment=SentimentSnapshot(label="positive", score=0.4),
            ),
            "AAPL": _provider_row(
                "AAPL",
                valuation=ValuationMetrics(
                    trailing_pe=20.0,
                    forward_pe=18.0,
                    price_to_book=4.0,
                    dividend_yield=0.006,
                ),
            ),
        },
        as_of_utc=datetime(2026, 5, 10, tzinfo=UTC),
    )

    symbols = {item.candidate.research_symbol for item in response.recommendations}

    assert response.provider == "static"
    assert {"SHEL.L", "AAPL", "MSFT", "TSCO.L"}.issubset(symbols)
    shell = next(
        item for item in response.recommendations if item.candidate.research_symbol == "SHEL.L"
    )
    assert shell.candidate.source == "holding"
    assert shell.action == RecommendationAction.HOLD
    assert shell.scores.fundamental_valuation.score is not None
    assert shell.scores.technical.score is not None
    assert shell.risk_flags == []


def test_recommendations_block_when_minimum_data_is_missing() -> None:
    """Missing provider data degrades to blocked review rows instead of failing."""

    response = build_recommendations_from_static_data(
        _snapshot(),
        {},
        candidates=["VOD.L"],
        include_default_candidates=False,
        as_of_utc=datetime(2026, 5, 10, tzinfo=UTC),
    )

    vod = next(
        item for item in response.recommendations if item.candidate.research_symbol == "VOD.L"
    )

    assert vod.action == RecommendationAction.BLOCKED
    assert "MISSING_FUNDAMENTALS" in vod.risk_flags
    assert "MISSING_TECHNICALS" in vod.risk_flags
    assert "No valuation provider data for VOD.L." in response.warnings


def test_recommendations_use_configured_default_candidates() -> None:
    """The wider-market scan can be supplied by a config-backed universe."""

    response = build_recommendations_from_static_data(
        _snapshot(),
        {
            "GSK.L": _provider_row(
                "GSK.L",
                valuation=ValuationMetrics(trailing_pe=11.0, dividend_yield=0.04),
            )
        },
        include_default_candidates=True,
        default_candidates=["GSK.L"],
        as_of_utc=datetime(2026, 5, 10, tzinfo=UTC),
    )

    symbols = {item.candidate.research_symbol for item in response.recommendations}

    assert "GSK.L" in symbols
    assert "AAPL" not in symbols


def test_recommendations_block_near_catalyst_blackout() -> None:
    """Upcoming catalysts inside the no-buy window block a candidate."""

    response = build_recommendations_from_static_data(
        _snapshot(),
        {
            "MSFT": _provider_row(
                "MSFT",
                valuation=ValuationMetrics(
                    trailing_pe=12.0,
                    forward_pe=10.0,
                    price_to_book=1.2,
                    dividend_yield=0.03,
                ),
                events=[
                    UpcomingEvent(
                        event_type="earnings",
                        ts_utc=datetime(2026, 5, 12, tzinfo=UTC),
                        title="MSFT earnings",
                    )
                ],
            )
        },
        candidates=["MSFT"],
        include_default_candidates=False,
        as_of_utc=datetime(2026, 5, 10, tzinfo=UTC),
    )

    msft = next(
        item for item in response.recommendations if item.candidate.research_symbol == "MSFT"
    )

    assert msft.action == RecommendationAction.BLOCKED
    assert "CATALYST_BLACKOUT" in msft.risk_flags
    assert msft.scores.catalysts.label == "blackout"


def test_recommendations_can_attach_deterministic_llm_fallback() -> None:
    """Optional LLM rationale degrades safely when no OpenAI key is configured."""

    response = build_recommendations_from_static_data(
        _snapshot(),
        {
            "SHEL.L": _provider_row(
                "SHEL.L",
                valuation=ValuationMetrics(trailing_pe=8.0, dividend_yield=0.05),
            )
        },
        include_default_candidates=False,
        include_llm_rationale=True,
        as_of_utc=datetime(2026, 5, 10, tzinfo=UTC),
    )

    shell = response.recommendations[0]

    assert shell.llm_rationale is not None
    assert not shell.llm_rationale.enabled
    assert shell.llm_rationale.provider == "deterministic"


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
    sentiment: SentimentSnapshot | None = None,
    events: list[UpcomingEvent] | None = None,
) -> HoldingValuationData:
    return HoldingValuationData(
        symbol=symbol,
        retrieved_at_utc=datetime(2026, 5, 10, 10, 1, tzinfo=UTC),
        daily_adjusted_closes=_closes(260),
        valuation=valuation,
        sentiment=sentiment,
        upcoming_events=events or [],
    )


def _closes(count: int) -> list[DailyAdjustedClose]:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    return [
        DailyAdjustedClose(ts_utc=start + timedelta(days=index), adj_close=float(index + 1))
        for index in range(count)
    ]
