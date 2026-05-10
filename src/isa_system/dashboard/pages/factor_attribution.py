"""Factor attribution dashboard page."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from isa_system.dashboard.data import broker_snapshot, holdings_valuation
from isa_system.dashboard.factor_context import (
    factor_attribution_frame,
    factor_coverage_summary,
    factor_methodology_frame,
)
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot


def render(snapshot: BrokerPortfolioSnapshot | None = None) -> None:
    """Render factor attribution."""

    snapshot = snapshot or broker_snapshot()
    valuation_snapshot = holdings_valuation(snapshot)
    frame = factor_attribution_frame(valuation_snapshot)
    coverage = factor_coverage_summary(frame)

    st.title("Factor Attribution")
    st.warning(
        "This page is a transparent starter attribution from convenience valuation and "
        "technical overlays. The production factor engine still needs official point-in-time "
        "fundamentals before any live ranking should depend on it."
    )

    cols = st.columns(5)
    cols[0].metric("Holdings", str(coverage["holdings"]))
    cols[1].metric("Momentum coverage", f"{coverage['momentum']}/{coverage['holdings']}")
    cols[2].metric("Value coverage", f"{coverage['value']}/{coverage['holdings']}")
    cols[3].metric("Dividend coverage", f"{coverage['dividend']}/{coverage['holdings']}")
    cols[4].metric("Quality coverage", f"{coverage['quality']}/{coverage['holdings']}")

    st.subheader("Composite Starter Scores")
    if frame.empty:
        st.info("No holdings are available for factor attribution.")
    else:
        _render_score_chart(frame)
        st.dataframe(
            frame,
            width="stretch",
            hide_index=True,
            column_config={
                "rank": st.column_config.NumberColumn("Rank"),
                "symbol": st.column_config.TextColumn("Symbol"),
                "research_symbol": st.column_config.TextColumn("Research symbol"),
                "name": st.column_config.TextColumn("Name"),
                "provider": st.column_config.TextColumn("Provider"),
                "momentum_raw": st.column_config.NumberColumn("Momentum raw", format="%.4f"),
                "value_raw": st.column_config.NumberColumn("Value raw", format="%.4f"),
                "dividend_raw": st.column_config.NumberColumn("Dividend raw", format="%.4f"),
                "quality_raw": st.column_config.NumberColumn("Quality raw", format="%.4f"),
                "momentum_z": st.column_config.NumberColumn("Momentum z", format="%.2f"),
                "value_z": st.column_config.NumberColumn("Value z", format="%.2f"),
                "dividend_z": st.column_config.NumberColumn("Dividend z", format="%.2f"),
                "quality_z": st.column_config.NumberColumn("Quality z", format="%.2f"),
                "composite_score": st.column_config.NumberColumn("Composite", format="%.2f"),
                "missing_factors": st.column_config.TextColumn("Missing factors"),
                "warnings": st.column_config.TextColumn("Warnings"),
            },
        )

    st.subheader("Method and Roadmap Guardrails")
    st.dataframe(factor_methodology_frame(), width="stretch", hide_index=True)


def _render_score_chart(frame: pd.DataFrame) -> None:
    """Render composite scores by holding."""

    chart = (
        alt.Chart(frame)
        .mark_bar(size=28)
        .encode(
            x=alt.X("composite_score:Q", title="Composite starter score"),
            y=alt.Y("symbol:N", sort="-x", title=None),
            color=alt.Color("composite_score:Q", scale=alt.Scale(scheme="redblue"), legend=None),
            tooltip=[
                alt.Tooltip("symbol:N", title="Symbol"),
                alt.Tooltip("research_symbol:N", title="Research symbol"),
                alt.Tooltip("momentum_z:Q", title="Momentum z", format=",.2f"),
                alt.Tooltip("value_z:Q", title="Value z", format=",.2f"),
                alt.Tooltip("dividend_z:Q", title="Dividend z", format=",.2f"),
                alt.Tooltip("composite_score:Q", title="Composite", format=",.2f"),
            ],
        )
        .properties(height=max(180, 34 * len(frame)))
    )
    st.altair_chart(chart, width="stretch")


if __name__ == "__main__":
    render()
