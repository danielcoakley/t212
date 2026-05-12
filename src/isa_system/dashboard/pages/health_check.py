"""Current-holdings health check page."""

from __future__ import annotations

from typing import Any

import streamlit as st

from isa_system.dashboard.data import broker_snapshot, holdings_valuation
from isa_system.services.holding_health import (
    HealthPriceTargets,
    HoldingHealthAction,
    HoldingHealthReport,
    HoldingHealthUpdate,
    HoldingHealthUpdateRequest,
    accept_holding_health_update,
    get_holding_health_report_detail,
    list_holding_health_reports,
    run_holding_health_report,
)
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot
from isa_system.utils.time import to_london

ACTION_OPTIONS = [action.value for action in HoldingHealthAction]


def render(snapshot: BrokerPortfolioSnapshot | None = None) -> None:
    """Render the holdings health report workflow."""

    snapshot = snapshot or broker_snapshot()
    st.title("Health Check")
    st.caption(
        "Run an on-demand health report for current holdings. Reports are stored in "
        "history. Accepted target/action updates remain review-only and do not create "
        "broker order authority."
    )

    cols = st.columns(4)
    cols[0].metric("Broker", snapshot.status)
    cols[1].metric("Environment", snapshot.environment)
    cols[2].metric("Holdings", len(snapshot.positions))
    cols[3].metric(
        "Account value",
        "n/a" if snapshot.total_value is None else f"{snapshot.total_value:,.2f}",
    )

    if st.button("Run holdings health report", type="primary"):
        with st.status("Generating holdings health report...", expanded=True) as status:
            st.write("Loading valuation overlays for current broker holdings.")
            valuation = holdings_valuation(snapshot)
            st.write("Running the configured OpenAI health model or local fallback.")
            report = run_holding_health_report(snapshot, valuation)
            status.update(label="Health report generated and stored.", state="complete")
        st.success(f"Stored report {report.id}.")

    reports = list_holding_health_reports(limit=20)
    if not reports:
        st.info("No holdings health report has been generated yet.")
        for warning in snapshot.warnings:
            st.warning(warning)
        return

    selected_report_id = st.selectbox(
        "Report history",
        options=[report.id for report in reports],
        format_func=lambda report_id: _report_label(report_id, reports),
    )
    detail = get_holding_health_report_detail(selected_report_id)
    if detail is None:
        st.warning("Selected report could not be loaded.")
        return

    _render_report_summary(detail.report)
    rows = health_report_rows(detail.report, detail.updates)
    edited_rows = st.data_editor(
        rows,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Accept": st.column_config.CheckboxColumn("Accept", help="Carry this row forward."),
            "Carried action": st.column_config.SelectboxColumn(
                "Carried action",
                options=ACTION_OPTIONS,
                help="Action label to carry forward for operator review.",
            ),
            "Accepted bear": st.column_config.NumberColumn("Accepted bear", format="%.2f"),
            "Accepted base": st.column_config.NumberColumn("Accepted base", format="%.2f"),
            "Accepted bull": st.column_config.NumberColumn("Accepted bull", format="%.2f"),
        },
        disabled=[
            "Symbol",
            "Name",
            "Current price",
            "Current weight %",
            "Recommended action",
            "Model bear",
            "Model base",
            "Model bull",
            "Confidence",
            "Already carried",
        ],
    )

    if st.button("Accept selected target/action updates"):
        requests = acceptance_requests_from_rows(edited_rows)
        if not requests:
            st.info("Select at least one row to accept or adjust.")
            return
        for symbol, request in requests:
            accept_holding_health_update(detail.report.id, symbol, request)
        st.success(f"Stored {len(requests)} health update(s) for carry-forward.")

    _render_assessment_details(detail.report, rows)


def health_report_rows(
    report: HoldingHealthReport, updates: list[HoldingHealthUpdate] | None = None
) -> list[dict[str, Any]]:
    """Flatten a health report into editable dashboard table rows."""

    updates_by_symbol = {update.symbol.upper(): update for update in updates or []}
    rows: list[dict[str, Any]] = []
    for assessment in report.assessments:
        update = updates_by_symbol.get(assessment.symbol.upper())
        carried_targets = (
            update.accepted_price_targets if update is not None else assessment.price_targets
        )
        carried_action = (
            update.carried_forward_action if update is not None else assessment.recommended_action
        )
        rows.append(
            {
                "Accept": update is not None,
                "Already carried": "Yes" if update is not None else "No",
                "Symbol": assessment.symbol,
                "Name": assessment.company_name or "",
                "Current price": assessment.current_price,
                "Current weight %": assessment.current_weight_pct,
                "Recommended action": assessment.recommended_action.value,
                "Carried action": carried_action.value,
                "Model bear": assessment.price_targets.bear,
                "Model base": assessment.price_targets.base,
                "Model bull": assessment.price_targets.bull,
                "Accepted bear": carried_targets.bear,
                "Accepted base": carried_targets.base,
                "Accepted bull": carried_targets.bull,
                "Confidence": assessment.confidence_score,
            }
        )
    return rows


def acceptance_requests_from_rows(
    rows: list[dict[str, Any]] | Any,
) -> list[tuple[str, HoldingHealthUpdateRequest]]:
    """Build accept/update service requests from edited dashboard rows."""

    requests: list[tuple[str, HoldingHealthUpdateRequest]] = []
    for row in _row_records(rows):
        if not row.get("Accept"):
            continue
        symbol = str(row.get("Symbol") or "").strip()
        if not symbol:
            continue
        action_value = str(row.get("Carried action") or HoldingHealthAction.REVIEW.value)
        try:
            action = HoldingHealthAction(action_value)
        except ValueError:
            action = HoldingHealthAction.REVIEW
        requests.append(
            (
                symbol,
                HoldingHealthUpdateRequest(
                    price_targets=HealthPriceTargets(
                        bear=_optional_float(row.get("Accepted bear")),
                        base=_optional_float(row.get("Accepted base")),
                        bull=_optional_float(row.get("Accepted bull")),
                    ),
                    carried_forward_action=action,
                ),
            )
        )
    return requests


def _render_report_summary(report: HoldingHealthReport) -> None:
    generated = to_london(report.generated_at_utc)
    snapshot_at = to_london(report.holdings_snapshot_at_utc)
    cols = st.columns(5)
    cols[0].metric("Status", report.status.value)
    cols[1].metric("Model", report.model)
    cols[2].metric("Holdings", report.holding_count)
    cols[3].metric("Generated", f"{generated:%Y-%m-%d %H:%M}")
    cols[4].metric("Snapshot", f"{snapshot_at:%Y-%m-%d %H:%M}")
    st.write(report.summary)
    for note in report.portfolio_level_notes:
        st.info(note)
    for warning in report.warnings:
        st.warning(warning)


def _render_assessment_details(report: HoldingHealthReport, rows: list[dict[str, Any]]) -> None:
    st.subheader("Holding Details")
    accepted_by_symbol = {str(row["Symbol"]).upper(): row for row in rows if row.get("Accept")}
    for assessment in report.assessments:
        label = f"{assessment.symbol} - {assessment.recommended_action.value}"
        with st.expander(label):
            accepted = accepted_by_symbol.get(assessment.symbol.upper())
            if accepted is not None:
                st.caption(
                    "Carried forward: "
                    f"{accepted['Carried action']} with bear/base/bull "
                    f"{accepted['Accepted bear']}/{accepted['Accepted base']}/"
                    f"{accepted['Accepted bull']}."
                )
            st.write(assessment.action_rationale)
            cols = st.columns(3)
            cols[0].metric("Bear target", _target(assessment.price_targets.bear))
            cols[0].caption(assessment.bear_case)
            cols[1].metric("Base target", _target(assessment.price_targets.base))
            cols[1].caption(assessment.base_case)
            cols[2].metric("Bull target", _target(assessment.price_targets.bull))
            cols[2].caption(assessment.bull_case)
            if assessment.key_risks:
                st.warning("Key risks: " + "; ".join(assessment.key_risks))
            if assessment.evidence_gaps:
                st.info("Evidence gaps: " + "; ".join(assessment.evidence_gaps))


def _report_label(report_id: str, reports: list[HoldingHealthReport]) -> str:
    report = next(report for report in reports if report.id == report_id)
    generated = to_london(report.generated_at_utc)
    return f"{generated:%Y-%m-%d %H:%M} - {report.status.value} - {report.holding_count} holdings"


def _target(value: float | None) -> str:
    return "n/a" if value is None else f"{value:,.2f}"


def _optional_float(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _row_records(rows: list[dict[str, Any]] | Any) -> list[dict[str, Any]]:
    if isinstance(rows, list):
        return rows
    to_dict = getattr(rows, "to_dict", None)
    if callable(to_dict):
        records = to_dict("records")
        return records if isinstance(records, list) else []
    return []


if __name__ == "__main__":
    render()
