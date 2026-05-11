"""Reusable Streamlit charts for broker portfolio views."""

from __future__ import annotations

from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

from isa_system.services.portfolio_state import BrokerPortfolioSnapshot
from isa_system.utils.time import to_london

POSITION_COLUMNS = [
    "symbol",
    "name",
    "currency",
    "quantity",
    "average_price_paid",
    "current_price",
    "current_value",
    "weight",
    "unrealised_profit_loss",
    "unrealised_profit_loss_pct",
    "isin",
]


def positions_frame(snapshot: BrokerPortfolioSnapshot) -> pd.DataFrame:
    """Return a normalised positions frame with defensive value and P/L fallbacks."""

    rows: list[dict[str, Any]] = []
    raw_values: list[float] = []
    for position in snapshot.positions:
        quantity = float(position.quantity or 0.0)
        current_price = _float_or_none(position.current_price)
        average_price = _float_or_none(position.average_price_paid)
        current_value = _float_or_none(position.current_value)
        if current_value is None and current_price is not None:
            current_value = quantity * current_price

        cost_basis = quantity * average_price if average_price is not None else None
        unrealised_pl = _float_or_none(position.unrealised_profit_loss)
        if unrealised_pl is None and current_value is not None and cost_basis is not None:
            unrealised_pl = current_value - cost_basis
        unrealised_pl_pct = (
            unrealised_pl / cost_basis
            if unrealised_pl is not None and cost_basis is not None and cost_basis != 0.0
            else None
        )
        if current_value is not None:
            raw_values.append(current_value)

        rows.append(
            {
                "symbol": position.symbol,
                "name": position.name or position.symbol,
                "currency": position.currency or snapshot.account_currency or "Unknown",
                "quantity": quantity,
                "average_price_paid": average_price,
                "current_price": current_price,
                "current_value": current_value,
                "weight": None,
                "unrealised_profit_loss": unrealised_pl,
                "unrealised_profit_loss_pct": unrealised_pl_pct,
                "isin": position.isin,
            }
        )

    frame = pd.DataFrame(rows, columns=POSITION_COLUMNS)
    if frame.empty:
        return frame

    denominator = snapshot.total_value or sum(raw_values)
    if denominator and denominator > 0:
        frame["weight"] = frame["current_value"].fillna(0.0) / denominator
    return frame.sort_values("current_value", ascending=False, na_position="last")


def portfolio_totals(
    snapshot: BrokerPortfolioSnapshot,
    frame: pd.DataFrame,
) -> dict[str, float | None]:
    """Calculate headline portfolio totals used across dashboard pages."""

    invested = _safe_sum(frame, "current_value")
    cash = _float_or_none(snapshot.available_to_trade)
    reserved = _float_or_none(snapshot.reserved_for_orders)
    total = _float_or_none(snapshot.total_value)
    if total is None:
        total = invested + (cash or 0.0) + (reserved or 0.0)
    pnl = _safe_sum(frame, "unrealised_profit_loss")
    largest_weight = _float_or_none(frame["weight"].max()) if not frame.empty else None
    cash_weight = cash / total if total and cash is not None else None
    invested_weight = invested / total if total and total > 0 else None
    return {
        "total": total,
        "invested": invested,
        "cash": cash,
        "reserved": reserved,
        "pnl": pnl,
        "largest_weight": largest_weight,
        "cash_weight": cash_weight,
        "invested_weight": invested_weight,
    }


def render_snapshot_context(
    snapshot: BrokerPortfolioSnapshot,
    frame: pd.DataFrame,
    *,
    include_broker: bool = True,
) -> None:
    """Render headline portfolio and broker context metrics."""

    totals = portfolio_totals(snapshot, frame)
    currency = snapshot.account_currency
    cols = st.columns(5)
    cols[0].metric("Total value", format_money(totals["total"], currency))
    cols[1].metric("Invested", format_money(totals["invested"], currency))
    cols[2].metric("Available cash", format_money(totals["cash"], currency))
    cols[3].metric("Unrealised P/L", format_money(totals["pnl"], currency))
    if include_broker:
        cols[4].metric("Broker", f"{snapshot.status} / {snapshot.environment}")
    else:
        cols[4].metric("Largest holding", format_percent(totals["largest_weight"]))

    retrieved = to_london(snapshot.retrieved_at_utc)
    st.caption(
        "Broker data is read-only. Storage timestamps remain UTC; this page displays "
        f"the snapshot time as {retrieved:%Y-%m-%d %H:%M:%S %Z}."
    )


def render_cash_and_invested_chart(snapshot: BrokerPortfolioSnapshot, frame: pd.DataFrame) -> None:
    """Render account value split across invested value, cash, reserved cash, and gaps."""

    totals = portfolio_totals(snapshot, frame)
    total = totals["total"] or 0.0
    invested = totals["invested"] or 0.0
    cash = totals["cash"] or 0.0
    reserved = totals["reserved"] or 0.0
    rows = [
        {"component": "Invested positions", "value": invested},
        {"component": "Available cash", "value": cash},
        {"component": "Reserved for orders", "value": reserved},
    ]
    known = invested + cash + reserved
    if total > known:
        rows.append({"component": "Other broker value", "value": total - known})
    chart_frame = pd.DataFrame(rows)
    if chart_frame["value"].sum() <= 0:
        st.info("No account value was available from the broker snapshot.")
        return

    st.altair_chart(
        alt.Chart(chart_frame)
        .mark_bar(size=34)
        .encode(
            x=alt.X("value:Q", title=f"Value ({snapshot.account_currency or 'account currency'})"),
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


def render_currency_allocation(snapshot: BrokerPortfolioSnapshot, frame: pd.DataFrame) -> None:
    """Render allocation by instrument currency, including available cash where known."""

    rows: list[dict[str, Any]] = []
    if not frame.empty:
        grouped = (
            frame.dropna(subset=["current_value"])
            .groupby("currency", dropna=False)["current_value"]
            .sum()
            .reset_index()
        )
        for row in grouped.to_dict("records"):
            rows.append(
                {
                    "currency": row["currency"] or "Unknown",
                    "value": float(row["current_value"]),
                    "source": "Positions",
                }
            )
    if snapshot.available_to_trade is not None:
        rows.append(
            {
                "currency": snapshot.account_currency or "Account",
                "value": float(snapshot.available_to_trade),
                "source": "Cash",
            }
        )

    chart_frame = pd.DataFrame(rows)
    if chart_frame.empty or chart_frame["value"].sum() <= 0:
        st.info("No currency allocation was available in the broker snapshot.")
        return

    st.altair_chart(
        alt.Chart(chart_frame)
        .mark_bar(size=32)
        .encode(
            x=alt.X("value:Q", title="Current value"),
            y=alt.Y("currency:N", sort="-x", title="Currency"),
            color=alt.Color("source:N", title="Source"),
            tooltip=[
                alt.Tooltip("currency:N", title="Currency"),
                alt.Tooltip("source:N", title="Source"),
                alt.Tooltip("value:Q", title="Value", format=",.2f"),
            ],
        )
        .properties(height=max(120, 46 * len(chart_frame["currency"].unique()))),
        width="stretch",
    )


def render_concentration_chart(frame: pd.DataFrame, *, limit: int = 10) -> None:
    """Render top holding concentration by current account weight."""

    if frame.empty or "weight" not in frame:
        st.info("No holdings are available for concentration analysis.")
        return
    chart_frame = frame[["symbol", "current_value", "weight"]].dropna(subset=["current_value"])
    if chart_frame.empty:
        st.info("The broker snapshot does not include current values for holdings.")
        return
    chart_frame = chart_frame.head(limit).copy()
    chart_frame["weight_pct"] = chart_frame["weight"].fillna(0.0) * 100.0
    st.altair_chart(
        alt.Chart(chart_frame)
        .mark_bar(size=28)
        .encode(
            x=alt.X("weight_pct:Q", title="Weight (%)"),
            y=alt.Y("symbol:N", sort="-x", title=None),
            color=alt.Color("weight_pct:Q", legend=None, scale=alt.Scale(scheme="blues")),
            tooltip=[
                alt.Tooltip("symbol:N", title="Symbol"),
                alt.Tooltip("current_value:Q", title="Current value", format=",.2f"),
                alt.Tooltip("weight_pct:Q", title="Weight", format=".2f"),
            ],
        )
        .properties(height=max(180, 34 * len(chart_frame))),
        width="stretch",
    )


def render_profit_loss_chart(snapshot: BrokerPortfolioSnapshot, frame: pd.DataFrame) -> None:
    """Render unrealised profit/loss by holding."""

    if frame.empty:
        st.info("No holdings are available for P/L analysis.")
        return
    chart_frame = frame[["symbol", "unrealised_profit_loss"]].dropna(
        subset=["unrealised_profit_loss"]
    )
    if chart_frame.empty:
        st.info("The broker snapshot does not include unrealised P/L fields.")
        return
    chart_frame = chart_frame.sort_values("unrealised_profit_loss", ascending=True)
    st.altair_chart(
        alt.Chart(chart_frame)
        .mark_bar(size=26)
        .encode(
            x=alt.X(
                "unrealised_profit_loss:Q",
                title=f"Unrealised P/L ({snapshot.account_currency or 'account currency'})",
            ),
            y=alt.Y("symbol:N", sort=None, title=None),
            color=alt.condition(
                alt.datum.unrealised_profit_loss >= 0,
                alt.value("#247a4d"),
                alt.value("#b42318"),
            ),
            tooltip=[
                alt.Tooltip("symbol:N", title="Symbol"),
                alt.Tooltip("unrealised_profit_loss:Q", title="Unrealised P/L", format=",.2f"),
            ],
        )
        .properties(height=max(180, 34 * len(chart_frame))),
        width="stretch",
    )


def render_holdings_table(frame: pd.DataFrame) -> None:
    """Render a formatted holdings table."""

    if frame.empty:
        st.info("No live holdings were returned by the broker.")
        return

    display_frame = frame.copy()
    display_frame["weight"] = display_frame["weight"].map(format_percent)
    display_frame["unrealised_profit_loss_pct"] = display_frame["unrealised_profit_loss_pct"].map(
        format_percent
    )
    st.dataframe(
        display_frame,
        width="stretch",
        hide_index=True,
        column_config={
            "symbol": st.column_config.TextColumn("Symbol"),
            "name": st.column_config.TextColumn("Name"),
            "currency": st.column_config.TextColumn("Currency"),
            "quantity": st.column_config.NumberColumn("Quantity", format="%.6f"),
            "average_price_paid": st.column_config.NumberColumn("Average price", format="%.4f"),
            "current_price": st.column_config.NumberColumn("Current price", format="%.4f"),
            "current_value": st.column_config.NumberColumn("Current value", format="%.2f"),
            "weight": st.column_config.TextColumn("Weight"),
            "unrealised_profit_loss": st.column_config.NumberColumn(
                "Unrealised P/L",
                format="%.2f",
            ),
            "unrealised_profit_loss_pct": st.column_config.TextColumn("Unrealised P/L %"),
            "isin": st.column_config.TextColumn("ISIN"),
        },
    )


def render_rebalance_safety_panel(snapshot: BrokerPortfolioSnapshot) -> None:
    """Render explicit safety gates before any rebalance submission can happen."""

    checks = pd.DataFrame(
        [
            {
                "gate": "Mode",
                "state": "Preview only",
                "result": "Blocked for live submit",
                "context": "The dashboard cannot submit orders from this view.",
            },
            {
                "gate": "Live arming",
                "state": "Disarmed",
                "result": "Blocked for live submit",
                "context": "Live mode still requires an explicit two-step arm flow.",
            },
            {
                "gate": "Kill switch",
                "state": "Clear",
                "result": "Pass",
                "context": "No live order path is enabled in this dashboard session.",
            },
            {
                "gate": "Broker data",
                "state": f"{snapshot.status} / {snapshot.environment}",
                "result": "Read-only",
                "context": "Only account and position read endpoints are used here.",
            },
            {
                "gate": "Duplicate order prevention",
                "state": "Required",
                "result": "Pending submit service",
                "context": "Any future submit path must pass local idempotency checks first.",
            },
        ]
    )
    st.dataframe(checks, width="stretch", hide_index=True)


def render_rebalance_hold_table(snapshot: BrokerPortfolioSnapshot, frame: pd.DataFrame) -> None:
    """Render a no-trade rebalance preview based on the current live snapshot."""

    if frame.empty:
        st.info("No positions are available, so no rebalance rows can be previewed.")
        return
    preview = frame[["symbol", "currency", "current_value", "weight"]].copy()
    preview["target_weight"] = preview["weight"]
    preview["trade_side"] = "HOLD"
    preview["estimated_commission"] = 0.0
    preview["estimated_slippage"] = 0.0
    preview["estimated_fx_cost"] = 0.0
    preview["estimated_sdrt"] = 0.0
    preview["warning"] = "No target-weight strategy run has been selected."
    preview["weight"] = preview["weight"].map(format_percent)
    preview["target_weight"] = preview["target_weight"].map(format_percent)
    st.dataframe(
        preview,
        width="stretch",
        hide_index=True,
        column_config={
            "symbol": st.column_config.TextColumn("Symbol"),
            "currency": st.column_config.TextColumn("Currency"),
            "current_value": st.column_config.NumberColumn(
                f"Current value ({snapshot.account_currency or 'account'})",
                format="%.2f",
            ),
            "weight": st.column_config.TextColumn("Current weight"),
            "target_weight": st.column_config.TextColumn("Preview target"),
            "trade_side": st.column_config.TextColumn("Side"),
            "estimated_commission": st.column_config.NumberColumn("Commission", format="%.2f"),
            "estimated_slippage": st.column_config.NumberColumn("Slippage", format="%.2f"),
            "estimated_fx_cost": st.column_config.NumberColumn("FX cost", format="%.2f"),
            "estimated_sdrt": st.column_config.NumberColumn("SDRT", format="%.2f"),
            "warning": st.column_config.TextColumn("Warning"),
        },
    )


def render_warnings(snapshot: BrokerPortfolioSnapshot) -> None:
    """Render broker warnings with consistent copy."""

    for warning in snapshot.warnings:
        st.warning(warning)


def format_money(value: float | None, currency: str | None) -> str:
    """Format optional monetary values for display."""

    if value is None:
        return "n/a"
    prefix = f"{currency} " if currency else ""
    return f"{prefix}{value:,.2f}"


def format_percent(value: float | None) -> str:
    """Format optional ratios as percentages."""

    if value is None or pd.isna(value):
        return "n/a"
    return f"{value * 100.0:,.2f}%"


def _safe_sum(frame: pd.DataFrame, column: str) -> float:
    """Return a numeric column sum from a possibly empty frame."""

    if frame.empty or column not in frame:
        return 0.0
    return float(pd.to_numeric(frame[column], errors="coerce").fillna(0.0).sum())


def _float_or_none(value: Any) -> float | None:
    """Coerce values from broker payloads into floats when possible."""

    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
