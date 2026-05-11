"""Audit log dashboard page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from isa_system.dashboard.data import broker_snapshot
from isa_system.services.audit_status import AuditStatusSnapshot, load_audit_status
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot
from isa_system.utils.time import to_london


def render(snapshot: BrokerPortfolioSnapshot | None = None) -> None:
    """Render audit and status rows."""

    snapshot = snapshot or broker_snapshot()
    status = load_audit_status(broker_snapshot=snapshot)

    st.title("Audit Logs")
    st.warning(
        "This page is for auditability and operational evidence. Live submit remains blocked "
        "unless mode, arming, kill switch, reconciliation, and duplicate-order checks pass."
    )
    _render_status_metrics(status)

    st.subheader("Latest Audit Chain Rows")
    if not status.latest_audit_logs:
        st.info("No append-only audit log rows exist yet in the local operational database.")
    else:
        audit_frame = pd.DataFrame(
            [row.model_dump(mode="json") for row in status.latest_audit_logs]
        )
        st.dataframe(
            audit_frame,
            width="stretch",
            hide_index=True,
            column_config={
                "id": st.column_config.NumberColumn("ID"),
                "ts_utc": st.column_config.DatetimeColumn("Timestamp UTC"),
                "actor": st.column_config.TextColumn("Actor"),
                "action": st.column_config.TextColumn("Action"),
                "outcome": st.column_config.TextColumn("Outcome"),
                "payload_hash": st.column_config.TextColumn("Payload hash"),
                "previous_hash": st.column_config.TextColumn("Previous hash"),
            },
        )

    st.subheader("Smoke Test Artefacts")
    artifacts = pd.DataFrame([item.model_dump(mode="json") for item in status.smoke_artifacts])
    st.dataframe(
        artifacts,
        width="stretch",
        hide_index=True,
        column_config={
            "name": st.column_config.TextColumn("Artefact"),
            "path": st.column_config.TextColumn("Path"),
            "exists": st.column_config.CheckboxColumn("Exists"),
            "modified_at_utc": st.column_config.DatetimeColumn("Modified UTC"),
            "size_bytes": st.column_config.NumberColumn("Size bytes"),
        },
    )

    st.subheader("Current Guardrails")
    guardrails = pd.DataFrame(
        [
            {
                "control": "Mode",
                "state": status.mode,
                "result": "Preview only" if status.mode == "preview" else "Review required",
            },
            {
                "control": "Live armed",
                "state": str(status.live_armed),
                "result": "Blocked" if not status.live_armed else "Review required",
            },
            {
                "control": "Kill switch",
                "state": str(status.kill_switch_enabled),
                "result": "Pass" if not status.kill_switch_enabled else "Blocked",
            },
            {
                "control": "Broker",
                "state": f"{status.broker_status} / {status.broker_environment}",
                "result": "Read-only",
            },
        ]
    )
    st.dataframe(guardrails, width="stretch", hide_index=True)


def _render_status_metrics(status: AuditStatusSnapshot) -> None:
    """Render audit and runtime metrics."""

    cols = st.columns(5)
    cols[0].metric("Mode", status.mode)
    cols[1].metric("Live armed", str(status.live_armed))
    cols[2].metric("Kill switch", str(status.kill_switch_enabled))
    cols[3].metric("Broker positions", str(status.broker_position_count))
    cols[4].metric("Audit rows", str(status.audit_log_count))
    retrieved = to_london(status.retrieved_at_utc)
    st.caption(f"Status retrieved at {retrieved:%Y-%m-%d %H:%M:%S %Z}.")
    for warning in status.warnings:
        st.warning(warning)


if __name__ == "__main__":
    render()
