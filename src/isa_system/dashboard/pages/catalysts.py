"""Catalyst dashboard page."""

from __future__ import annotations

import streamlit as st

from isa_system.dashboard.catalyst_context import (
    catalyst_event_frame,
    catalyst_summary,
    news_context_frame,
    official_source_coverage_frame,
)
from isa_system.dashboard.charts import positions_frame, render_snapshot_context
from isa_system.dashboard.data import broker_snapshot, holdings_valuation
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot


def render(snapshot: BrokerPortfolioSnapshot | None = None) -> None:
    """Render upcoming catalysts."""

    snapshot = snapshot or broker_snapshot()
    broker_frame = positions_frame(snapshot)
    valuation_snapshot = holdings_valuation(snapshot)
    events = catalyst_event_frame(valuation_snapshot)
    news = news_context_frame(valuation_snapshot)
    summary = catalyst_summary(events, news, len(valuation_snapshot.holdings))

    st.title("Upcoming Catalysts")
    st.warning(
        "Event vetoes and blackout windows appear here before live submission. Current "
        "provider events are convenience context until official filings, RNS, NSM, and "
        "short-disclosure validation are wired into the point-in-time lake."
    )
    render_snapshot_context(snapshot, broker_frame, include_broker=False)

    cols = st.columns(5)
    cols[0].metric("Holdings", str(summary["holding_count"]))
    cols[1].metric("Event rows", str(summary["event_count"]))
    cols[2].metric("Blackout rows", str(summary["blackout_count"]))
    cols[3].metric("With events", str(summary["holdings_with_events"]))
    cols[4].metric("With news", str(summary["holdings_with_news"]))

    st.subheader("Provider Event Context")
    st.caption(
        "Rows inside the default no-buy window are flagged, but all event rows still need "
        "official-source validation before they can influence live order decisions."
    )
    if events.empty:
        st.info("No upcoming provider events were available for the current holdings.")
    else:
        st.dataframe(
            events,
            width="stretch",
            hide_index=True,
            column_config={
                "symbol": st.column_config.TextColumn("Symbol"),
                "research_symbol": st.column_config.TextColumn("Research symbol"),
                "event_type": st.column_config.TextColumn("Event"),
                "event_at_utc": st.column_config.DatetimeColumn("Event time UTC"),
                "days_to_event": st.column_config.NumberColumn("Days"),
                "blackout": st.column_config.CheckboxColumn("Blackout"),
                "validation_status": st.column_config.TextColumn("Validation"),
                "source": st.column_config.TextColumn("Source"),
                "title": st.column_config.TextColumn("Title"),
                "url": st.column_config.LinkColumn("Link"),
            },
        )

    st.subheader("Recent Information Context")
    st.caption(
        "News and social-style sentiment remain low-weight overlays. Official announcement tone, "
        "PDMR transactions, and disclosed short interest are higher priority roadmap items."
    )
    if news.empty:
        st.info("No recent provider headlines were available for the current holdings.")
    else:
        st.dataframe(
            news,
            width="stretch",
            hide_index=True,
            column_config={
                "symbol": st.column_config.TextColumn("Symbol"),
                "research_symbol": st.column_config.TextColumn("Research symbol"),
                "headline": st.column_config.TextColumn("Headline"),
                "published_at_utc": st.column_config.DatetimeColumn("Published UTC"),
                "source": st.column_config.TextColumn("Source"),
                "sentiment": st.column_config.TextColumn("Sentiment"),
                "url": st.column_config.LinkColumn("Link"),
            },
        )

    st.subheader("Official Validation Coverage")
    st.dataframe(
        official_source_coverage_frame(),
        width="stretch",
        hide_index=True,
        column_config={
            "source": st.column_config.TextColumn("Source"),
            "market": st.column_config.TextColumn("Market"),
            "purpose": st.column_config.TextColumn("Purpose"),
            "dashboard_status": st.column_config.TextColumn("Status"),
            "current_guardrail": st.column_config.TextColumn("Current guardrail"),
        },
    )


if __name__ == "__main__":
    render()
