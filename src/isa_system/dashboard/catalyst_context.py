"""Catalyst and information-context helpers for dashboard pages."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pandas as pd

from isa_system.services.valuation import HoldingsValuationResponse
from isa_system.utils.time import now_utc

EVENT_BLACKOUT_DAYS_BEFORE = 5
EVENT_BLACKOUT_DAYS_AFTER = 2


def catalyst_event_frame(
    snapshot: HoldingsValuationResponse,
    *,
    as_of_utc: datetime | None = None,
) -> pd.DataFrame:
    """Return upcoming catalyst rows for current holdings."""

    as_of = as_of_utc or now_utc()
    rows: list[dict[str, Any]] = []
    for holding in snapshot.holdings:
        for event in holding.upcoming_events:
            event_at = _ensure_utc_or_none(event.ts_utc)
            days_to_event = _days_to_event(as_of, event_at)
            rows.append(
                {
                    "symbol": holding.symbol,
                    "research_symbol": holding.research_symbol,
                    "event_type": event.event_type,
                    "event_at_utc": event_at,
                    "days_to_event": days_to_event,
                    "blackout": _is_blackout(days_to_event),
                    "validation_status": "Convenience feed, official validation pending",
                    "source": event.source or snapshot.provider,
                    "title": event.title,
                    "url": event.url,
                }
            )
    frame = pd.DataFrame(rows, columns=_event_columns())
    if frame.empty:
        return frame
    return frame.sort_values(["event_at_utc", "symbol"], na_position="last")


def news_context_frame(snapshot: HoldingsValuationResponse) -> pd.DataFrame:
    """Return recent news or information rows for current holdings."""

    rows: list[dict[str, Any]] = []
    for holding in snapshot.holdings:
        sentiment_label = holding.sentiment.label if holding.sentiment else "unscored"
        for item in holding.news:
            rows.append(
                {
                    "symbol": holding.symbol,
                    "research_symbol": holding.research_symbol,
                    "headline": item.headline,
                    "published_at_utc": _ensure_utc_or_none(item.published_at_utc),
                    "source": item.source or snapshot.provider,
                    "sentiment": sentiment_label,
                    "url": item.url,
                }
            )
    frame = pd.DataFrame(rows, columns=_news_columns())
    if frame.empty:
        return frame
    return frame.sort_values(["published_at_utc", "symbol"], ascending=[False, True])


def official_source_coverage_frame() -> pd.DataFrame:
    """Return official-source coverage status for the current starter build."""

    return pd.DataFrame(
        [
            {
                "source": "SEC EDGAR",
                "market": "US",
                "purpose": "Official filings and company facts",
                "dashboard_status": "Planned",
                "current_guardrail": "Treat convenience fundamentals as provisional.",
            },
            {
                "source": "Companies House",
                "market": "UK",
                "purpose": "Issuer identity and filing history",
                "dashboard_status": "Planned",
                "current_guardrail": "Require issuer crosswalk before PIT factor use.",
            },
            {
                "source": "LSE RNS",
                "market": "UK",
                "purpose": "Official announcement validation",
                "dashboard_status": "Planned",
                "current_guardrail": "No automatic trade near unvalidated UK events.",
            },
            {
                "source": "FCA NSM",
                "market": "UK",
                "purpose": "Archive validation for regulated information",
                "dashboard_status": "Planned",
                "current_guardrail": "Use as validation, not as a real-time feed.",
            },
            {
                "source": "FCA short disclosures",
                "market": "UK",
                "purpose": "Official short-interest sentiment proxy",
                "dashboard_status": "Planned",
                "current_guardrail": "Parser must be versioned around 2026-07-13 rule changes.",
            },
        ]
    )


def catalyst_summary(
    events: pd.DataFrame,
    news: pd.DataFrame,
    holding_count: int,
) -> dict[str, int]:
    """Return compact catalyst page summary counts."""

    blackout_count = int(events["blackout"].sum()) if not events.empty else 0
    holdings_with_events = int(events["symbol"].nunique()) if not events.empty else 0
    holdings_with_news = int(news["symbol"].nunique()) if not news.empty else 0
    return {
        "holding_count": holding_count,
        "event_count": len(events),
        "blackout_count": blackout_count,
        "holdings_with_events": holdings_with_events,
        "holdings_with_news": holdings_with_news,
    }


def _event_columns() -> list[str]:
    """Return stable event columns."""

    return [
        "symbol",
        "research_symbol",
        "event_type",
        "event_at_utc",
        "days_to_event",
        "blackout",
        "validation_status",
        "source",
        "title",
        "url",
    ]


def _news_columns() -> list[str]:
    """Return stable news columns."""

    return [
        "symbol",
        "research_symbol",
        "headline",
        "published_at_utc",
        "source",
        "sentiment",
        "url",
    ]


def _days_to_event(as_of_utc: datetime, event_at_utc: datetime | None) -> int | None:
    """Return calendar days to an event."""

    if event_at_utc is None:
        return None
    return (event_at_utc.date() - as_of_utc.date()).days


def _is_blackout(days_to_event: int | None) -> bool:
    """Return whether an event falls inside the default no-buy blackout window."""

    if days_to_event is None:
        return False
    return -EVENT_BLACKOUT_DAYS_AFTER <= days_to_event <= EVENT_BLACKOUT_DAYS_BEFORE


def _ensure_utc_or_none(value: datetime | None) -> datetime | None:
    """Normalise optional datetimes to UTC."""

    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
