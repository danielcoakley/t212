"""Operational database engine and session helpers."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

import isa_system.db.models  # noqa: F401
from isa_system.db.base import Base


def make_engine(dsn: str) -> Engine:
    """Create a SQLAlchemy engine."""

    _ensure_sqlite_parent(dsn)
    connect_args = {"check_same_thread": False} if dsn.startswith("sqlite") else {}
    return create_engine(dsn, future=True, connect_args=connect_args)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a typed session factory."""

    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db(engine: Engine) -> None:
    """Create operational tables for zero-config SQLite use."""

    Base.metadata.create_all(engine)


def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    """Yield a session and commit or roll back."""

    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _ensure_sqlite_parent(dsn: str) -> None:
    """Create the parent directory for file-backed SQLite DSNs."""

    url = make_url(dsn)
    if not url.drivername.startswith("sqlite"):
        return
    if not url.database or url.database == ":memory:":
        return
    Path(url.database).expanduser().parent.mkdir(parents=True, exist_ok=True)
