"""Tests for operational DB creation and audit helpers."""

from __future__ import annotations

from isa_system.db.crud import append_audit_log
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
