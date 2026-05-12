"""Research report persistence."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from isa_system.db.models import ResearchReportRecord
from isa_system.db.session import init_db, make_engine, make_session_factory
from isa_system.reports.memo_models import ResearchReport
from isa_system.settings import Settings, get_settings


class ReportStore:
    """Persist research reports as Markdown and SQLite records."""

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
        self.report_dir = Path(self.settings.artifacts_path) / "research_reports"
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def save(self, report: ResearchReport) -> ResearchReport:
        """Save report Markdown and SQLite metadata."""

        markdown_path = self.report_dir / f"{report.id}.md"
        markdown_path.write_text(report.markdown, encoding="utf-8")
        saved = report.model_copy(update={"markdown_path": str(markdown_path)})
        with self.session_factory() as session:
            session.merge(
                ResearchReportRecord(
                    id=saved.id,
                    symbol=saved.symbol,
                    thesis_id=saved.thesis_id,
                    decision=saved.decision.value,
                    markdown_path=saved.markdown_path or "",
                    generated_at_utc=saved.generated_at_utc,
                    payload_json=saved.model_dump_json(),
                )
            )
            session.commit()
        return saved

    def latest_for_symbol(self, symbol: str) -> ResearchReport | None:
        """Load latest report for a symbol."""

        with self.session_factory() as session:
            row = session.scalar(
                select(ResearchReportRecord)
                .where(ResearchReportRecord.symbol == symbol.upper())
                .order_by(ResearchReportRecord.generated_at_utc.desc())
                .limit(1)
            )
            if row is None:
                return None
            return ResearchReport.model_validate(json.loads(row.payload_json))

    def latest(self, limit: int = 20) -> list[ResearchReport]:
        """Load latest reports."""

        with self.session_factory() as session:
            rows = session.scalars(
                select(ResearchReportRecord)
                .order_by(ResearchReportRecord.generated_at_utc.desc())
                .limit(limit)
            ).all()
            return [ResearchReport.model_validate(json.loads(row.payload_json)) for row in rows]
