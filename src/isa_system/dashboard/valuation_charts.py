"""Valuation and technical indicator widgets for the Streamlit dashboard."""

from __future__ import annotations

from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

from isa_system.dashboard.charts import format_money, format_percent
from isa_system.utils.time import to_london

VALUATION_COLUMNS = [
    "symbol",
    "research_symbol",
    "name",
    "market_value",
    "currency",
    "trailing_pe",
    "forward_pe",
    "price_to_book",
    "dividend_yield",
    "market_cap",
    "beta",
    "rsi14",
    "sma50",
    "sma200",
    "momentum_1m",
    "momentum_3m",
    "momentum_6m",
    "momentum_12m",
    "trend_state",
    "next_event",
    "latest_headline",
    "sentiment_label",
    "data_source",
    "warnings",
]


def valuation_frame(snapshot: Any) -> pd.DataFrame:
    """Return a stable holdings valuation frame from a Pydantic model or mapping."""

    rows: list[dict[str, Any]] = []
    holdings = getattr(snapshot, "holdings", None)
    provider = getattr(snapshot, "provider", None)
    if holdings is None and isinstance(snapshot, dict):
        holdings = snapshot.get("holdings")
        provider = snapshot.get("provider")
    for holding in holdings or []:
        row = holding.model_dump(mode="json") if hasattr(holding, "model_dump") else dict(holding)
        event = _first_item(row.get("upcoming_events"))
        item = _first_item(row.get("information_items"))
        rows.append(
            {
                "symbol": row.get("symbol"),
                "research_symbol": row.get("research_symbol"),
                "name": row.get("name") or row.get("symbol"),
                "market_value": row.get("market_value") or row.get("current_value"),
                "currency": row.get("currency"),
                "trailing_pe": _nested_value(row, "valuation", "trailing_pe"),
                "forward_pe": _nested_value(row, "valuation", "forward_pe"),
                "price_to_book": _nested_value(row, "valuation", "price_to_book"),
                "dividend_yield": _nested_value(row, "valuation", "dividend_yield"),
                "market_cap": _nested_value(row, "valuation", "market_cap"),
                "beta": _nested_value(row, "valuation", "beta"),
                "rsi14": _nested_value(row, "technicals", "rsi14"),
                "sma50": _nested_value(row, "technicals", "sma50"),
                "sma200": _nested_value(row, "technicals", "sma200"),
                "momentum_1m": _nested_value(row, "technicals", "momentum_1m"),
                "momentum_3m": _nested_value(row, "technicals", "momentum_3m"),
                "momentum_6m": _nested_value(row, "technicals", "momentum_6m"),
                "momentum_12m": _nested_value(row, "technicals", "momentum_12m"),
                "trend_state": _trend_state(
                    _nested_value(row, "technicals", "sma50"),
                    _nested_value(row, "technicals", "sma200"),
                    _nested_value(row, "technicals", "momentum_3m"),
                ),
                "next_event": _event_label(event),
                "latest_headline": item.get("headline") if isinstance(item, dict) else None,
                "sentiment_label": _nested_value(row, "sentiment", "label"),
                "data_source": row.get("data_source") or row.get("provider") or provider,
                "warnings": "; ".join(row.get("warnings") or []),
            }
        )
    frame = pd.DataFrame(rows, columns=VALUATION_COLUMNS)
    if frame.empty:
        return frame
    return frame.sort_values("market_value", ascending=False, na_position="last")


def render_valuation_context(snapshot: Any, frame: pd.DataFrame) -> None:
    """Render freshness and coverage metrics for the valuation snapshot."""

    retrieved_at = getattr(snapshot, "retrieved_at_utc", None)
    warnings = getattr(snapshot, "warnings", [])
    if isinstance(snapshot, dict):
        retrieved_at = snapshot.get("retrieved_at_utc")
        warnings = snapshot.get("warnings", [])

    coverage = _ratio(frame["trailing_pe"].notna().sum(), len(frame)) if not frame.empty else None
    technical_coverage = (
        _ratio(frame["rsi14"].notna().sum(), len(frame)) if not frame.empty else None
    )
    event_coverage = (
        _ratio(frame["next_event"].notna().sum(), len(frame)) if not frame.empty else None
    )

    cols = st.columns(4)
    cols[0].metric("Holdings covered", str(len(frame)))
    cols[1].metric("Valuation coverage", format_percent(coverage))
    cols[2].metric("Technical coverage", format_percent(technical_coverage))
    cols[3].metric("Event coverage", format_percent(event_coverage))

    if retrieved_at is not None:
        retrieved = pd.Timestamp(retrieved_at).to_pydatetime()
        st.caption(
            "Valuation and technical overlays are convenience research data. Storage timestamps "
            "remain UTC; this page displays freshness as "
            f"{to_london(retrieved):%Y-%m-%d %H:%M:%S %Z}."
        )
    for warning in warnings:
        st.warning(str(warning))


def render_valuation_table(frame: pd.DataFrame, account_currency: str | None) -> None:
    """Render a formatted valuation and context table."""

    if frame.empty:
        st.info("No live holdings are available for valuation analysis.")
        return

    display = frame.copy()
    for column in ["dividend_yield", "momentum_1m", "momentum_3m", "momentum_6m", "momentum_12m"]:
        display[column] = display[column].map(format_percent)
    st.dataframe(
        display,
        width="stretch",
        hide_index=True,
        column_config={
            "symbol": st.column_config.TextColumn("Symbol"),
            "research_symbol": st.column_config.TextColumn("Research symbol"),
            "name": st.column_config.TextColumn("Name"),
            "market_value": st.column_config.NumberColumn(
                f"Value ({account_currency or 'account'})",
                format="%.2f",
            ),
            "currency": st.column_config.TextColumn("Currency"),
            "trailing_pe": st.column_config.NumberColumn("Trailing P/E", format="%.2f"),
            "forward_pe": st.column_config.NumberColumn("Forward P/E", format="%.2f"),
            "price_to_book": st.column_config.NumberColumn("P/B", format="%.2f"),
            "dividend_yield": st.column_config.TextColumn("Dividend yield"),
            "market_cap": st.column_config.NumberColumn("Market cap", format="%.0f"),
            "beta": st.column_config.NumberColumn("Beta", format="%.2f"),
            "rsi14": st.column_config.NumberColumn("RSI 14", format="%.1f"),
            "sma50": st.column_config.NumberColumn("SMA 50", format="%.2f"),
            "sma200": st.column_config.NumberColumn("SMA 200", format="%.2f"),
            "momentum_1m": st.column_config.TextColumn("1m momentum"),
            "momentum_3m": st.column_config.TextColumn("3m momentum"),
            "momentum_6m": st.column_config.TextColumn("6m momentum"),
            "momentum_12m": st.column_config.TextColumn("12m momentum"),
            "trend_state": st.column_config.TextColumn("Trend"),
            "next_event": st.column_config.TextColumn("Next event"),
            "latest_headline": st.column_config.TextColumn("Latest context"),
            "sentiment_label": st.column_config.TextColumn("Sentiment"),
            "data_source": st.column_config.TextColumn("Source"),
            "warnings": st.column_config.TextColumn("Warnings"),
        },
    )


def render_relative_valuation(frame: pd.DataFrame) -> None:
    """Render relative valuation bars for holdings with available ratios."""

    if frame.empty:
        st.info("No holdings are available for valuation charts.")
        return
    melted = frame.melt(
        id_vars=["symbol"],
        value_vars=["trailing_pe", "forward_pe", "price_to_book"],
        var_name="metric",
        value_name="value",
    ).dropna(subset=["value"])
    if melted.empty:
        st.info("No valuation ratio data was available from the configured convenience feeds.")
        return
    st.altair_chart(
        alt.Chart(melted)
        .mark_bar(size=22)
        .encode(
            x=alt.X("value:Q", title="Ratio"),
            y=alt.Y("symbol:N", sort="-x", title=None),
            color=alt.Color("metric:N", title="Metric"),
            tooltip=[
                alt.Tooltip("symbol:N", title="Symbol"),
                alt.Tooltip("metric:N", title="Metric"),
                alt.Tooltip("value:Q", title="Value", format=",.2f"),
            ],
        )
        .properties(height=max(180, 36 * len(frame))),
        width="stretch",
    )


def render_technical_heatmap(frame: pd.DataFrame) -> None:
    """Render momentum and RSI indicators as a compact heatmap."""

    if frame.empty:
        st.info("No holdings are available for technical charts.")
        return
    technical = frame.melt(
        id_vars=["symbol"],
        value_vars=["momentum_1m", "momentum_3m", "momentum_6m", "momentum_12m"],
        var_name="metric",
        value_name="value",
    ).dropna(subset=["value"])
    if technical.empty:
        st.info("No momentum history was available for the current holdings.")
        return
    technical["value_pct"] = technical["value"] * 100.0
    st.altair_chart(
        alt.Chart(technical)
        .mark_rect()
        .encode(
            x=alt.X("metric:N", title=None),
            y=alt.Y("symbol:N", title=None),
            color=alt.Color(
                "value_pct:Q",
                title="Momentum %",
                scale=alt.Scale(scheme="redblue", domainMid=0),
            ),
            tooltip=[
                alt.Tooltip("symbol:N", title="Symbol"),
                alt.Tooltip("metric:N", title="Window"),
                alt.Tooltip("value_pct:Q", title="Momentum %", format=",.2f"),
            ],
        )
        .properties(height=max(160, 32 * len(frame))),
        width="stretch",
    )


def render_indicator_bars(frame: pd.DataFrame) -> None:
    """Render RSI by holding with a neutral 30-70 context band."""

    chart_frame = frame[["symbol", "rsi14"]].dropna(subset=["rsi14"]) if not frame.empty else frame
    if chart_frame.empty:
        st.info("No RSI data was available from the configured price history feed.")
        return
    bars = (
        alt.Chart(chart_frame)
        .mark_bar(size=24)
        .encode(
            x=alt.X("rsi14:Q", title="RSI 14", scale=alt.Scale(domain=[0, 100])),
            y=alt.Y("symbol:N", sort="-x", title=None),
            color=alt.condition(
                "datum.rsi14 < 30 || datum.rsi14 > 70",
                alt.value("#b42318"),
                alt.value("#247a4d"),
            ),
            tooltip=[
                alt.Tooltip("symbol:N", title="Symbol"),
                alt.Tooltip("rsi14:Q", title="RSI 14", format=",.1f"),
            ],
        )
    )
    band = (
        alt.Chart(pd.DataFrame([{"low": 30, "high": 70}]))
        .mark_rect(opacity=0.12, color="#4c78a8")
        .encode(x="low:Q", x2="high:Q")
    )
    st.altair_chart(
        (band + bars).properties(height=max(160, 32 * len(chart_frame))), width="stretch"
    )


def render_information_panel(frame: pd.DataFrame) -> None:
    """Render event, news, sentiment, and missing-data context for each holding."""

    if frame.empty:
        st.info("No holdings context is available.")
        return
    panel = frame[
        ["symbol", "next_event", "latest_headline", "sentiment_label", "data_source", "warnings"]
    ].copy()
    st.dataframe(panel, width="stretch", hide_index=True)


def valuation_warning_count(snapshot: Any) -> int:
    """Return the number of warnings attached to a valuation snapshot."""

    warnings = getattr(snapshot, "warnings", [])
    if isinstance(snapshot, dict):
        warnings = snapshot.get("warnings", [])
    count = len(warnings or [])
    holdings = getattr(snapshot, "holdings", None)
    if holdings is None and isinstance(snapshot, dict):
        holdings = snapshot.get("holdings")
    for holding in holdings or []:
        row = holding.model_dump(mode="json") if hasattr(holding, "model_dump") else dict(holding)
        count += len(row.get("warnings") or [])
    return count


def format_market_value(value: float | None, currency: str | None) -> str:
    """Format a market value for compact captions."""

    return format_money(value, currency)


def _first_item(value: Any) -> dict[str, Any] | None:
    """Return the first mapping from a provider list-like value."""

    if not value:
        return None
    first = value[0]
    return first.model_dump(mode="json") if hasattr(first, "model_dump") else dict(first)


def _nested_value(row: dict[str, Any], parent: str, child: str) -> Any:
    """Return nested provider data while tolerating flattened rows."""

    flattened = f"{parent}_{child}"
    if flattened in row:
        return row.get(flattened)
    parent_value = row.get(parent)
    if parent_value is None:
        return row.get(child)
    if hasattr(parent_value, "model_dump"):
        parent_value = parent_value.model_dump(mode="json")
    if isinstance(parent_value, dict):
        return parent_value.get(child)
    return None


def _trend_state(sma50: Any, sma200: Any, momentum_3m: Any) -> str | None:
    """Derive a compact trend state for display from available indicators."""

    if sma50 is None or sma200 is None:
        return None
    if sma50 > sma200 and (momentum_3m is None or momentum_3m >= 0):
        return "Uptrend"
    if sma50 < sma200 and (momentum_3m is None or momentum_3m <= 0):
        return "Downtrend"
    return "Mixed"


def _event_label(event: dict[str, Any] | None) -> str | None:
    """Format a compact event label."""

    if not event:
        return None
    name = event.get("event_type") or event.get("type") or "event"
    event_at = event.get("event_at_utc") or event.get("ts_utc") or event.get("event_date")
    if event_at is None:
        return str(name)
    try:
        event_ts = pd.Timestamp(event_at).to_pydatetime()
        return f"{name}: {to_london(event_ts):%Y-%m-%d}"
    except (TypeError, ValueError):
        return f"{name}: {event_at}"


def _ratio(numerator: int, denominator: int) -> float | None:
    """Return a ratio, preserving n/a for empty denominators."""

    if denominator <= 0:
        return None
    return numerator / denominator
