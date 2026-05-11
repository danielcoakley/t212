"""Recommendation dashboard charts and tables."""

from __future__ import annotations

from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

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


def _score(scores: dict[str, Any], key: str) -> float | None:
    """Return a nested component score."""

    component = scores.get(key) or {}
    value = component.get("score")
    return float(value) if value is not None else None
