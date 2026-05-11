"""Rebalance preview dashboard page."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from isa_system.dashboard.charts import (
    portfolio_totals,
    positions_frame,
    render_cash_and_invested_chart,
    render_rebalance_hold_table,
    render_rebalance_safety_panel,
    render_snapshot_context,
    render_warnings,
)
from isa_system.dashboard.data import broker_snapshot, paper_simulation, rebalance_preview
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot


def render(snapshot: BrokerPortfolioSnapshot | None = None) -> None:
    """Render a safe rebalance preview surface with live trading blocked."""

    snapshot = snapshot or broker_snapshot()
    frame = positions_frame(snapshot)
    totals = portfolio_totals(snapshot, frame)
    preview = rebalance_preview(snapshot)
    simulation = paper_simulation(snapshot)
    preview_frame = _preview_frame(preview)
    simulation_frame = _simulation_frame(simulation)
    st.title("Rebalance Preview")
    st.error("Live submit is disabled. This page is a read-only preview and safety review.")
    render_snapshot_context(snapshot, frame)
    render_warnings(snapshot)

    st.subheader("Safety Gates")
    st.caption(
        "Every live order path must remain blocked until mode, arming, kill-switch, broker "
        "reconciliation, and duplicate-order checks all pass."
    )
    render_rebalance_safety_panel(snapshot)

    st.subheader("Sleeve and Cash Context")
    cols = st.columns(4)
    cols[0].metric("Configured algo sleeve", "20%")
    cols[1].metric("Configured core sleeve", "80%")
    cols[2].metric("Invested fraction", _percent(totals["invested_weight"]))
    cols[3].metric(
        "Estimated preview costs",
        f"{snapshot.account_currency or 'GBP'} {float(preview.estimated_total_cost):,.2f}",
    )
    render_cash_and_invested_chart(snapshot, frame)

    st.subheader("Preview Summary")
    summary_cols = st.columns(5)
    summary_cols[0].metric("Turnover", f"{float(preview.expected_turnover):,.2f}")
    summary_cols[1].metric("Turnover weight", _percent(preview.expected_turnover_weight))
    summary_cols[2].metric("Cash buffer", _percent(preview.cash_buffer_weight))
    summary_cols[3].metric("Blocked trade rows", str(_blocked_count(preview_frame)))
    summary_cols[4].metric("Batch hash", preview.batch_hash[:10])
    st.caption(
        "The target is a preview-only starter sleeve blend: 80% core keeps current exposure "
        "proportions, while 20% is tilted by provisional valuation/technical context. It is "
        "not an order recommendation."
    )
    _render_weight_drift_chart(preview_frame)

    st.subheader("Current vs Preview Target")
    _render_preview_table(snapshot, preview_frame)

    st.subheader("Cost Breakdown")
    _render_cost_chart(preview_frame)

    st.subheader("Risk Checks")
    _render_risk_checks(preview)

    st.subheader("Paper Fill Simulation")
    st.caption(
        "This simulates local paper fills from blocked preview rows. It does not reserve "
        "idempotency keys, persist fills, or send anything to Trading 212."
    )
    sim_cols = st.columns(4)
    sim_cols[0].metric("Simulated fills", str(simulation.fill_count))
    sim_cols[1].metric("Paper notional", f"{float(simulation.estimated_notional):,.2f}")
    sim_cols[2].metric("Paper fees", f"{float(simulation.estimated_fees):,.2f}")
    sim_cols[3].metric("Simulation hash", simulation.simulation_hash[:10])
    _render_simulation_table(simulation_frame)
    for warning in simulation.warnings:
        st.info(warning)

    if preview.warnings:
        st.subheader("Warnings")
        for warning in preview.warnings:
            st.warning(warning)

    with st.expander("Legacy HOLD preview"):
        render_rebalance_hold_table(snapshot, frame)


def _percent(value: float | None) -> str:
    """Format an optional ratio as a percentage."""

    if value is None or pd.isna(value):
        return "n/a"
    return f"{value * 100.0:,.2f}%"


def _preview_frame(preview: object) -> pd.DataFrame:
    """Flatten a preview snapshot for Streamlit display."""

    rows = []
    for row in getattr(preview, "rows", []):
        payload = row.model_dump(mode="json") if hasattr(row, "model_dump") else dict(row)
        costs = payload.get("costs") or {}
        rows.append(
            {
                "symbol": payload.get("symbol"),
                "name": payload.get("name"),
                "currency": payload.get("currency"),
                "current_weight": payload.get("current_weight"),
                "target_weight": payload.get("target_weight"),
                "drift_weight": (payload.get("target_weight") or 0)
                - (payload.get("current_weight") or 0),
                "current_value": payload.get("current_value"),
                "target_value": payload.get("target_value"),
                "drift_value": payload.get("drift_value"),
                "side": payload.get("side"),
                "estimated_quantity": payload.get("estimated_quantity"),
                "estimated_notional": payload.get("estimated_notional"),
                "commission": costs.get("commission"),
                "slippage": costs.get("slippage"),
                "fx_cost": costs.get("fx_cost"),
                "sdrt": costs.get("sdrt"),
                "ptm_levy": costs.get("ptm_levy"),
                "total_cost": costs.get("total"),
                "status": payload.get("status"),
                "rationale": payload.get("rationale"),
                "warnings": "; ".join(payload.get("warnings") or []),
            }
        )
    return pd.DataFrame(rows)


def _render_preview_table(snapshot: BrokerPortfolioSnapshot, frame: pd.DataFrame) -> None:
    """Render current-vs-preview rows."""

    if frame.empty:
        st.info("No holdings are available for rebalance preview.")
        return
    display = frame.copy()
    for column in ["current_weight", "target_weight", "drift_weight"]:
        display[column] = pd.to_numeric(display[column], errors="coerce").map(_percent)
    st.dataframe(
        display,
        width="stretch",
        hide_index=True,
        column_config={
            "symbol": st.column_config.TextColumn("Symbol"),
            "name": st.column_config.TextColumn("Name"),
            "currency": st.column_config.TextColumn("Currency"),
            "current_weight": st.column_config.TextColumn("Current weight"),
            "target_weight": st.column_config.TextColumn("Preview target"),
            "drift_weight": st.column_config.TextColumn("Drift"),
            "current_value": st.column_config.NumberColumn("Current value", format="%.2f"),
            "target_value": st.column_config.NumberColumn("Target value", format="%.2f"),
            "drift_value": st.column_config.NumberColumn("Trade value", format="%.2f"),
            "side": st.column_config.TextColumn("Side"),
            "estimated_quantity": st.column_config.NumberColumn("Est. quantity", format="%.6f"),
            "estimated_notional": st.column_config.NumberColumn("Notional", format="%.2f"),
            "total_cost": st.column_config.NumberColumn(
                f"Cost ({snapshot.account_currency or 'account'})",
                format="%.2f",
            ),
            "status": st.column_config.TextColumn("Status"),
            "rationale": st.column_config.TextColumn("Rationale"),
            "warnings": st.column_config.TextColumn("Warnings"),
        },
    )


def _render_weight_drift_chart(frame: pd.DataFrame) -> None:
    """Render target drift by holding."""

    if frame.empty:
        return
    chart_frame = frame[["symbol", "drift_weight", "side"]].copy()
    chart_frame["drift_pct"] = pd.to_numeric(chart_frame["drift_weight"], errors="coerce") * 100
    st.altair_chart(
        alt.Chart(chart_frame)
        .mark_bar(size=28)
        .encode(
            x=alt.X("drift_pct:Q", title="Target drift (%)"),
            y=alt.Y("symbol:N", sort="-x", title=None),
            color=alt.Color("side:N", title="Side"),
            tooltip=[
                alt.Tooltip("symbol:N", title="Symbol"),
                alt.Tooltip("side:N", title="Side"),
                alt.Tooltip("drift_pct:Q", title="Drift %", format=",.2f"),
            ],
        )
        .properties(height=max(180, 34 * len(chart_frame))),
        width="stretch",
    )


def _render_cost_chart(frame: pd.DataFrame) -> None:
    """Render cost component totals."""

    if frame.empty:
        st.info("No preview cost rows are available.")
        return
    cost_frame = (
        frame[["commission", "slippage", "fx_cost", "sdrt", "ptm_levy"]]
        .apply(pd.to_numeric, errors="coerce")
        .sum()
        .reset_index()
    )
    cost_frame.columns = ["component", "value"]
    if cost_frame["value"].sum() <= 0:
        st.info("No estimated costs for the current preview rows.")
        return
    st.altair_chart(
        alt.Chart(cost_frame)
        .mark_bar(size=32)
        .encode(
            x=alt.X("value:Q", title="Estimated cost"),
            y=alt.Y("component:N", sort="-x", title=None),
            color=alt.Color("component:N", legend=None),
            tooltip=[
                alt.Tooltip("component:N", title="Component"),
                alt.Tooltip("value:Q", title="Value", format=",.2f"),
            ],
        )
        .properties(height=180),
        width="stretch",
    )


def _render_risk_checks(preview: object) -> None:
    """Render risk checks as a table."""

    checks = [
        check.model_dump(mode="json") if hasattr(check, "model_dump") else dict(check)
        for check in getattr(preview, "risk_checks", [])
    ]
    if not checks:
        st.info("No risk checks are available for this preview.")
        return
    st.dataframe(pd.DataFrame(checks), width="stretch", hide_index=True)


def _simulation_frame(simulation: object) -> pd.DataFrame:
    """Flatten paper simulation rows for display."""

    rows = []
    for fill in getattr(simulation, "fills", []):
        rows.append(fill.model_dump(mode="json") if hasattr(fill, "model_dump") else dict(fill))
    return pd.DataFrame(rows)


def _render_simulation_table(frame: pd.DataFrame) -> None:
    """Render local paper fill simulation rows."""

    if frame.empty:
        st.info("No paper fills would be simulated from the current preview.")
        return
    st.dataframe(
        frame,
        width="stretch",
        hide_index=True,
        column_config={
            "symbol": st.column_config.TextColumn("Symbol"),
            "side": st.column_config.TextColumn("Side"),
            "quantity": st.column_config.NumberColumn("Quantity", format="%.6f"),
            "fill_price_account": st.column_config.NumberColumn(
                "Fill price in account currency",
                format="%.2f",
            ),
            "notional": st.column_config.NumberColumn("Notional", format="%.2f"),
            "estimated_fees": st.column_config.NumberColumn("Fees", format="%.2f"),
            "status": st.column_config.TextColumn("Status"),
            "note": st.column_config.TextColumn("Note"),
        },
    )


def _blocked_count(frame: pd.DataFrame) -> int:
    """Return blocked preview trade row count."""

    if frame.empty or "status" not in frame:
        return 0
    return int((frame["status"] == "preview_blocked").sum())


if __name__ == "__main__":
    render()
