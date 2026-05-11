"""Tests for operational DB creation and audit helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from isa_system.db.crud import append_audit_log
from isa_system.db.models import ResearchReview
from isa_system.db.session import init_db, make_engine, make_session_factory


def test_sqlite_operational_db_can_be_created() -> None:
    """The default model metadata creates on SQLite."""

    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    factory = make_session_factory(engine)
    with factory() as session:
        row = append_audit_log(
            session, actor="test", action="preview", payload={"ok": True}, outcome="ok"
        )
        session.commit()
        assert row.id is not None


def test_file_backed_sqlite_parent_directory_is_created(tmp_path: Path) -> None:
    """Zero-config SQLite works even when the artifacts directory is absent."""

    db_path = tmp_path / "missing" / "nested" / "isa_system.sqlite3"
    engine = make_engine(f"sqlite:///{db_path}")
    init_db(engine)

    assert db_path.exists()


def test_sqlite_operational_db_can_persist_research_reviews() -> None:
    """Research review table exists in the default SQLite schema."""

    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    factory = make_session_factory(engine)
    generated = datetime(2026, 5, 10, tzinfo=UTC)
    with factory() as session:
        session.add(
            ResearchReview(
                id="research-test",
                symbol="GOOD.L",
                research_symbol="GOOD.L",
                broker_ticker="GOODl_EQ",
                status="AVAILABLE",
                decision="RESEARCH_PASSED",
                final_score=80,
                model="test-model",
                evidence_hash="hash",
                generated_at_utc=generated,
                expires_at_utc=generated + timedelta(days=7),
                request_json="{}",
                response_json="{}",
                warnings_json="[]",
            )
        )
        session.commit()
        assert session.get(ResearchReview, "research-test") is not None
