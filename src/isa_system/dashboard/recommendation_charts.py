"""Recommendation dashboard charts and tables."""

from __future__ import annotations

from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

from isa_system.services.instrument_validation import InstrumentValidationResponse
from isa_system.services.recommendation_handoff import RecommendationHandoffResponse
from isa_system.services.recommendations import RecommendationsResponse
from isa_system.utils.time import to_london


def recommendation_frame(response: RecommendationsResponse) -> pd.DataFrame:
    """Flatten recommendation rows for dashboard display."""

    rows: list[dict[str, Any]] = []
    for item in response.recommendations:
        payload = item.model_dump(mode="json")
        candidate = payload["candidate"]
        scores = payload["scores"]
        llm = payload.get("llm_rationale") or {}
        rows.append(
            {
                "symbol": candidate["symbol"],
                "research_symbol": candidate["research_symbol"],
                "source": candidate["source"],
                "name": candidate.get("name"),
                "action": payload["action"],
                "composite": scores["composite"],
                "fundamental": _score(scores, "fundamental_valuation"),
                "technical": _score(scores, "technical"),
                "sentiment": _score(scores, "sentiment_news"),
                "catalysts": _score(scores, "catalysts"),
                "risk_flags": ", ".join(payload.get("risk_flags") or []),
                "rationale": " ".join(payload.get("rationale") or []),
                "llm_enabled": llm.get("enabled"),
                "llm_headline": llm.get("headline"),
                "warnings": "; ".join(payload.get("warnings") or []),
            }
        )
    return pd.DataFrame(rows)


def render_recommendation_summary(response: RecommendationsResponse, frame: pd.DataFrame) -> None:
    """Render recommendation coverage metrics."""

    action_counts = frame["action"].value_counts().to_dict() if not frame.empty else {}
    cols = st.columns(5)
    cols[0].metric("Recommendations", str(len(frame)))
    cols[1].metric("Review buys", str(action_counts.get("REVIEW_BUY", 0)))
    cols[2].metric("Holds", str(action_counts.get("HOLD", 0)))
    cols[3].metric("Watch", str(action_counts.get("WATCH", 0)))
    cols[4].metric("Blocked", str(action_counts.get("BLOCKED", 0)))
    retrieved = to_london(response.retrieved_at_utc)
    st.caption(
        f"Recommendations generated from {response.provider} at "
        f"{retrieved:%Y-%m-%d %H:%M:%S %Z}. Actions are review-only."
    )
    for warning in response.warnings:
        st.warning(warning)


def render_action_chart(frame: pd.DataFrame) -> None:
    """Render composite score by action."""

    if frame.empty:
        st.info("No recommendation rows are available.")
        return
    st.altair_chart(
        alt.Chart(frame)
        .mark_bar(size=28)
        .encode(
            x=alt.X("composite:Q", title="Composite score", scale=alt.Scale(domain=[-1, 1])),
            y=alt.Y("research_symbol:N", sort="-x", title=None),
            color=alt.Color("action:N", title="Action"),
            tooltip=[
                alt.Tooltip("research_symbol:N", title="Symbol"),
                alt.Tooltip("source:N", title="Source"),
                alt.Tooltip("action:N", title="Action"),
                alt.Tooltip("composite:Q", title="Composite", format=",.2f"),
                alt.Tooltip("risk_flags:N", title="Risk flags"),
            ],
        )
        .properties(height=max(220, 34 * len(frame))),
        width="stretch",
    )


def render_component_heatmap(frame: pd.DataFrame) -> None:
    """Render component score heatmap."""

    if frame.empty:
        st.info("No component scores are available.")
        return
    heatmap = frame.melt(
        id_vars=["research_symbol"],
        value_vars=["fundamental", "technical", "sentiment", "catalysts"],
        var_name="component",
        value_name="score",
    )
    st.altair_chart(
        alt.Chart(heatmap)
        .mark_rect()
        .encode(
            x=alt.X("component:N", title=None),
            y=alt.Y("research_symbol:N", title=None),
            color=alt.Color(
                "score:Q",
                title="Score",
                scale=alt.Scale(scheme="redblue", domain=[-1, 1]),
            ),
            tooltip=[
                alt.Tooltip("research_symbol:N", title="Symbol"),
                alt.Tooltip("component:N", title="Component"),
                alt.Tooltip("score:Q", title="Score", format=",.2f"),
            ],
        )
        .properties(height=max(220, 30 * frame["research_symbol"].nunique())),
        width="stretch",
    )


def render_recommendation_table(frame: pd.DataFrame) -> None:
    """Render recommendations as a review queue."""

    if frame.empty:
        st.info("No recommendations are available.")
        return
    st.dataframe(
        frame,
        width="stretch",
        hide_index=True,
        column_config={
            "symbol": st.column_config.TextColumn("Broker symbol"),
            "research_symbol": st.column_config.TextColumn("Research symbol"),
            "source": st.column_config.TextColumn("Source"),
            "name": st.column_config.TextColumn("Name"),
            "action": st.column_config.TextColumn("Review action"),
            "composite": st.column_config.NumberColumn("Composite", format="%.2f"),
            "fundamental": st.column_config.NumberColumn("Fundamental", format="%.2f"),
            "technical": st.column_config.NumberColumn("Technical", format="%.2f"),
            "sentiment": st.column_config.NumberColumn("Sentiment/news", format="%.2f"),
            "catalysts": st.column_config.NumberColumn("Catalysts", format="%.2f"),
            "risk_flags": st.column_config.TextColumn("Risk flags"),
            "rationale": st.column_config.TextColumn("Deterministic rationale"),
            "llm_enabled": st.column_config.CheckboxColumn("LLM"),
            "llm_headline": st.column_config.TextColumn("LLM headline"),
            "warnings": st.column_config.TextColumn("Warnings"),
        },
    )


def handoff_frame(response: RecommendationHandoffResponse) -> pd.DataFrame:
    """Flatten recommendation hand-off rows for dashboard display."""

    rows: list[dict[str, Any]] = []
    for item in response.rows:
        payload = item.model_dump(mode="json")
        rows.append(
            {
                "symbol": payload["symbol"],
                "research_symbol": payload["research_symbol"],
                "source": payload["source"],
                "recommendation_action": payload["recommendation_action"],
                "preview_action": payload["proposed_preview_action"],
                "handoff_status": payload["handoff_status"],
                "composite_score": payload["composite_score"],
                "reason": payload["reason"],
                "blockers": ", ".join(payload.get("blockers") or []),
                "next_step": payload["next_step"],
            }
        )
    return pd.DataFrame(rows)


def render_handoff_summary(response: RecommendationHandoffResponse, frame: pd.DataFrame) -> None:
    """Render hand-off readiness metrics and warnings."""

    cols = st.columns(4)
    cols[0].metric("Preview eligible", str(response.eligible_count))
    cols[1].metric("Needs validation", str(response.review_required_count))
    cols[2].metric("Blocked", str(response.blocked_count))
    cols[3].metric("Rows", str(len(frame)))
    generated = to_london(response.generated_at_utc)
    st.caption(
        f"Hand-off generated from {response.provider} at "
        f"{generated:%Y-%m-%d %H:%M:%S %Z}. It is still preview-only."
    )


def render_handoff_chart(frame: pd.DataFrame) -> None:
    """Render hand-off readiness by recommendation symbol."""

    if frame.empty:
        st.info("No hand-off rows are available.")
        return
    st.altair_chart(
        alt.Chart(frame)
        .mark_bar(size=28)
        .encode(
            x=alt.X(
                "composite_score:Q",
                title="Composite score",
                scale=alt.Scale(domain=[-1, 1]),
            ),
            y=alt.Y("research_symbol:N", sort="-x", title=None),
            color=alt.Color("handoff_status:N", title="Hand-off status"),
            tooltip=[
                alt.Tooltip("research_symbol:N", title="Symbol"),
                alt.Tooltip("recommendation_action:N", title="Recommendation"),
                alt.Tooltip("preview_action:N", title="Preview action"),
                alt.Tooltip("handoff_status:N", title="Status"),
                alt.Tooltip("blockers:N", title="Blockers"),
            ],
        )
        .properties(height=max(220, 34 * len(frame))),
        width="stretch",
    )


def render_handoff_table(frame: pd.DataFrame) -> None:
    """Render review hand-off rows."""

    if frame.empty:
        st.info("No hand-off rows are available.")
        return
    st.dataframe(
        frame,
        width="stretch",
        hide_index=True,
        column_config={
            "symbol": st.column_config.TextColumn("Broker symbol"),
            "research_symbol": st.column_config.TextColumn("Research symbol"),
            "source": st.column_config.TextColumn("Source"),
            "recommendation_action": st.column_config.TextColumn("Recommendation"),
            "preview_action": st.column_config.TextColumn("Preview action"),
            "handoff_status": st.column_config.TextColumn("Hand-off status"),
            "composite_score": st.column_config.NumberColumn("Composite", format="%.2f"),
            "reason": st.column_config.TextColumn("Reason"),
            "blockers": st.column_config.TextColumn("Blockers"),
            "next_step": st.column_config.TextColumn("Next step"),
        },
    )


def instrument_validation_frame(response: InstrumentValidationResponse) -> pd.DataFrame:
    """Flatten instrument validation rows for dashboard display."""

    rows: list[dict[str, Any]] = []
    for item in response.rows:
        payload = item.model_dump(mode="json")
        rows.append(
            {
                "research_symbol": payload["research_symbol"],
                "source": payload["source"],
                "status": payload["status"],
                "broker_ticker": payload.get("broker_ticker"),
                "name": payload.get("name"),
                "isin": payload.get("isin"),
                "currency": payload.get("currency"),
                "asset_type": payload.get("asset_type"),
                "candidate_broker_tickers": ", ".join(
                    payload.get("candidate_broker_tickers") or []
                ),
                "isa_eligibility": payload["isa_eligibility"],
                "reason": payload["reason"],
            }
        )
    return pd.DataFrame(rows)


def render_instrument_validation_summary(
    response: InstrumentValidationResponse, frame: pd.DataFrame
) -> None:
    """Render broker metadata validation metrics."""

    counts = frame["status"].value_counts().to_dict() if not frame.empty else {}
    cols = st.columns(4)
    cols[0].metric("Broker matched", str(counts.get("BROKER_MATCHED", 0)))
    cols[1].metric("Holdings confirmed", str(counts.get("HOLDING_CONFIRMED", 0)))
    cols[2].metric("Needs mapping", str(counts.get("NEEDS_MAPPING", 0)))
    cols[3].metric("Metadata rows", str(response.instrument_count))
    retrieved = to_london(response.retrieved_at_utc)
    st.caption(
        f"Trading 212 metadata validation at {retrieved:%Y-%m-%d %H:%M:%S %Z}. "
        "A broker match is not an order approval."
    )
    for warning in response.warnings:
        st.warning(warning)


def render_instrument_validation_table(frame: pd.DataFrame) -> None:
    """Render Trading 212 instrument validation results."""

    if frame.empty:
        st.info("No instrument validation rows are available.")
        return
    st.dataframe(
        frame,
        width="stretch",
        hide_index=True,
        column_config={
            "research_symbol": st.column_config.TextColumn("Research symbol"),
            "source": st.column_config.TextColumn("Source"),
            "status": st.column_config.TextColumn("Broker validation"),
            "broker_ticker": st.column_config.TextColumn("Broker ticker"),
            "name": st.column_config.TextColumn("Name"),
            "isin": st.column_config.TextColumn("ISIN"),
            "currency": st.column_config.TextColumn("Currency"),
            "asset_type": st.column_config.TextColumn("Type"),
            "candidate_broker_tickers": st.column_config.TextColumn("Candidate tickers"),
            "isa_eligibility": st.column_config.TextColumn("ISA state"),
            "reason": st.column_config.TextColumn("Reason"),
        },
    )


def _score(scores: dict[str, Any], key: str) -> float | None:
    """Return a nested component score."""

    component = scores.get(key) or {}
    value = component.get("score")
    return float(value) if value is not None else None
