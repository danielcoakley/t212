"""Tests for dashboard catalyst context helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from isa_system.dashboard.catalyst_context import (
    catalyst_event_frame,
    catalyst_summary,
    news_context_frame,
)
from isa_system.services.valuation import (
    HoldingsValuationResponse,
    HoldingValuation,
    NewsItem,
    SentimentSnapshot,
    TechnicalIndicators,
    UpcomingEvent,
    ValuationMetrics,
)


def test_catalyst_event_frame_flags_blackout_window() -> None:
    """Events near the as-of date are flagged for no-buy review."""

    as_of = datetime(2026, 5, 10, tzinfo=UTC)
    response = _response(event_at=as_of + timedelta(days=2))

    events = catalyst_event_frame(response, as_of_utc=as_of)
    summary = catalyst_summary(events, news_context_frame(response), 1)

    assert events.iloc[0]["symbol"] == "AAPL_US_EQ"
    assert events.iloc[0]["days_to_event"] == 2
    assert bool(events.iloc[0]["blackout"])
    assert summary["blackout_count"] == 1
    assert summary["holdings_with_events"] == 1


def test_news_context_frame_preserves_sentiment_label() -> None:
    """News rows expose the holding sentiment label when present."""

    response = _response(event_at=datetime(2026, 6, 1, tzinfo=UTC))

    news = news_context_frame(response)

    assert news.iloc[0]["headline"] == "Apple quarterly context"
    assert news.iloc[0]["sentiment"] == "neutral"


def _response(event_at: datetime) -> HoldingsValuationResponse:
    return HoldingsValuationResponse(
        status="live",
        environment="live",
        retrieved_at_utc=datetime(2026, 5, 10, tzinfo=UTC),
        provider="static",
        holdings=[
            HoldingValuation(
                symbol="AAPL_US_EQ",
                broker_ticker="AAPL_US_EQ",
                research_symbol="AAPL",
                name="Apple",
                currency="USD",
                quantity=1,
                current_value=200,
                valuation=ValuationMetrics(),
                technicals=TechnicalIndicators(),
                upcoming_events=[
                    UpcomingEvent(
                        event_type="Earnings Date",
                        ts_utc=event_at,
                        title="Apple earnings",
                        source="static",
                    )
                ],
                news=[
                    NewsItem(
                        headline="Apple quarterly context",
                        published_at_utc=datetime(2026, 5, 9, tzinfo=UTC),
                        source="static",
                    )
                ],
                sentiment=SentimentSnapshot(label="neutral", source="static"),
                warnings=[],
            )
        ],
        warnings=[],
    )
