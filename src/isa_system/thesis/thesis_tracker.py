"""Thesis persistence helpers."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from isa_system.db.models import InvestmentThesisRecord
from isa_system.db.session import init_db, make_engine, make_session_factory
from isa_system.settings import Settings, get_settings
from isa_system.thesis.models import Thesis, ThesisStatus


class ThesisTracker:
    """Persist and retrieve thesis records."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        session_factory: sessionmaker[Session] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        if session_factory is not None:
            self.session_factory = session_factory
        else:
            engine = make_engine(self.settings.operational_db_dsn)
            init_db(engine)
            self.session_factory = make_session_factory(engine)

    def save(self, thesis: Thesis) -> Thesis:
        """Persist a thesis snapshot."""

        payload = thesis.model_dump_json()
        with self.session_factory() as session:
            session.merge(
                InvestmentThesisRecord(
                    id=thesis.id,
                    symbol=thesis.symbol,
                    status=thesis.status.value,
                    decision=thesis.decision.value,
                    created_at_utc=thesis.created_at_utc,
                    updated_at_utc=thesis.updated_at_utc,
                    payload_json=payload,
                )
            )
            session.commit()
        return thesis

    def latest_for_symbol(self, symbol: str) -> Thesis | None:
        """Return the latest persisted thesis for a symbol."""

        with self.session_factory() as session:
            row = session.scalar(
                select(InvestmentThesisRecord)
                .where(InvestmentThesisRecord.symbol == symbol.upper())
                .order_by(InvestmentThesisRecord.updated_at_utc.desc())
                .limit(1)
            )
            if row is None:
                return None
            return Thesis.model_validate(json.loads(row.payload_json))

    def list_by_status(self, statuses: set[ThesisStatus]) -> list[Thesis]:
        """List persisted theses matching one of the supplied statuses."""

        with self.session_factory() as session:
            rows = session.scalars(
                select(InvestmentThesisRecord)
                .where(InvestmentThesisRecord.status.in_([status.value for status in statuses]))
                .order_by(InvestmentThesisRecord.updated_at_utc.desc())
            ).all()
            return [Thesis.model_validate(json.loads(row.payload_json)) for row in rows]
