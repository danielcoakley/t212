"""Tests for audit status service."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from isa_system.db.crud import append_audit_log
from isa_system.db.session import init_db, make_engine, make_session_factory
from isa_system.services.audit_status import load_audit_status
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot
from isa_system.settings import Settings


def test_load_audit_status_reads_db_and_artifacts(tmp_path: Path) -> None:
    """Audit status combines DB rows, guardrails, broker state, and artefacts."""

    db_path = tmp_path / "ops.sqlite3"
    artifacts = tmp_path / "artifacts"
    smoke = artifacts / "smoke_test"
    smoke.mkdir(parents=True)
    (smoke / "metrics.csv").write_text("metric,value\ncagr,0.1\n", encoding="utf-8")

    engine = make_engine(f"sqlite:///{db_path}")
    init_db(engine)
    session_factory = make_session_factory(engine)
    with session_factory() as session:
        append_audit_log(session, actor="system", action="test", payload={"ok": True}, outcome="ok")
        session.commit()

    status = load_audit_status(
        Settings(
            operational_db_dsn=f"sqlite:///{db_path}",
            artifacts_path=artifacts,
        ),
        broker_snapshot=BrokerPortfolioSnapshot(
            status="live",
            environment="live",
            retrieved_at_utc=datetime(2026, 5, 10, tzinfo=UTC),
            positions=[],
            warnings=[],
        ),
    )

    assert status.audit_log_count == 1
    assert status.latest_audit_logs[0].action == "test"
    assert status.smoke_artifacts[0].name == "metrics.csv"
    assert status.smoke_artifacts[0].exists
    assert status.broker_status == "live"
    assert not status.live_armed
