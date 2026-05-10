"""Operator audit and runtime status service."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel
from sqlalchemy import func, select

from isa_system.db.models import AuditLog
from isa_system.db.session import init_db, make_engine, make_session_factory
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot, load_trading212_portfolio
from isa_system.settings import Settings, get_settings
from isa_system.utils.time import now_utc


class AuditLogRow(BaseModel):
    """Compact audit log row for API and dashboard display."""

    id: int
    ts_utc: datetime
    actor: str
    action: str
    outcome: str
    payload_hash: str
    previous_hash: str | None = None


class ArtifactStatus(BaseModel):
    """Local run artefact freshness row."""

    name: str
    path: str
    exists: bool
    modified_at_utc: datetime | None = None
    size_bytes: int | None = None


class AuditStatusSnapshot(BaseModel):
    """Runtime and audit status for local operator review."""

    retrieved_at_utc: datetime
    mode: str
    live_armed: bool
    kill_switch_enabled: bool
    broker_status: str
    broker_environment: str
    broker_position_count: int
    broker_warning_count: int
    audit_log_count: int
    latest_audit_logs: list[AuditLogRow]
    smoke_artifacts: list[ArtifactStatus]
    warnings: list[str]


def load_audit_status(
    settings: Settings | None = None,
    broker_snapshot: BrokerPortfolioSnapshot | None = None,
) -> AuditStatusSnapshot:
    """Load local audit, runtime, and artefact status."""

    app_settings = settings or get_settings()
    broker = broker_snapshot or load_trading212_portfolio()
    warnings = list(broker.warnings)
    audit_count = 0
    latest_logs: list[AuditLogRow] = []
    try:
        engine = make_engine(app_settings.operational_db_dsn)
        init_db(engine)
        session_factory = make_session_factory(engine)
        with session_factory() as session:
            audit_count = session.scalar(select(func.count()).select_from(AuditLog)) or 0
            rows = session.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(25)).all()
            latest_logs = [
                AuditLogRow(
                    id=row.id,
                    ts_utc=_utc(row.ts_utc),
                    actor=row.actor,
                    action=row.action,
                    outcome=row.outcome,
                    payload_hash=row.payload_hash,
                    previous_hash=row.previous_hash,
                )
                for row in rows
            ]
    except Exception as exc:  # pragma: no cover - defensive local DB status path
        warnings.append(f"Audit database status unavailable: {exc.__class__.__name__}.")

    return AuditStatusSnapshot(
        retrieved_at_utc=now_utc(),
        mode=str(app_settings.runtime_mode.value),
        live_armed=app_settings.live_armed,
        kill_switch_enabled=app_settings.kill_switch_enabled,
        broker_status=broker.status,
        broker_environment=broker.environment,
        broker_position_count=len(broker.positions),
        broker_warning_count=len(broker.warnings),
        audit_log_count=audit_count,
        latest_audit_logs=latest_logs,
        smoke_artifacts=_smoke_artifact_status(app_settings.artifacts_path),
        warnings=warnings,
    )


def _smoke_artifact_status(artifacts_path: Path) -> list[ArtifactStatus]:
    """Return known smoke artefact file statuses."""

    smoke_dir = artifacts_path / "smoke_test"
    return [
        _artifact(smoke_dir / "metrics.csv"),
        _artifact(smoke_dir / "trades.csv"),
        _artifact(smoke_dir / "holdings.csv"),
        _artifact(smoke_dir / "rebalance_preview.json"),
    ]


def _artifact(path: Path) -> ArtifactStatus:
    """Return file existence and freshness for one artefact."""

    if not path.exists():
        return ArtifactStatus(name=path.name, path=str(path), exists=False)
    stat = path.stat()
    return ArtifactStatus(
        name=path.name,
        path=str(path),
        exists=True,
        modified_at_utc=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
        size_bytes=stat.st_size,
    )


def _utc(value: datetime) -> datetime:
    """Return UTC for database datetimes that may round-trip through SQLite."""

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
