"""Research report tests."""

from __future__ import annotations

from pathlib import Path

from isa_system.db.session import init_db, make_engine, make_session_factory
from isa_system.discovery.models import Candidate
from isa_system.enrichment.enrichment_packet import EnrichmentService, load_fixture_enrichment
from isa_system.reports.memo_models import MemoSection
from isa_system.reports.prompt_builder import build_research_prompt
from isa_system.reports.report_generator import ReportGenerator
from isa_system.reports.report_store import ReportStore
from isa_system.scoring.ranking import RankingService
from isa_system.settings import Settings
from isa_system.thesis.thesis_generator import ThesisGenerator
from isa_system.thesis.thesis_tracker import ThesisTracker
from isa_system.utils.time import now_utc


def test_report_generation_without_llm_key() -> None:
    """No-key report generation is deterministic and complete."""

    thesis, score, packet = _inputs()

    report = ReportGenerator().generate(thesis, score, packet)

    assert report.symbol == "MSFT"
    assert MemoSection.EXECUTIVE_SUMMARY.value in report.sections
    assert "Research memo: MSFT" in report.markdown


def test_prompt_includes_data_quality_notes() -> None:
    """Prompt builder includes data quality and missing-data notes."""

    thesis, score, packet = _inputs()

    prompt = build_research_prompt(thesis, score, packet)

    assert "Data quality" in prompt
    assert "Missing data notes" in prompt
    assert "Do not recommend live execution" in prompt


def test_report_updates_thesis_and_persists(tmp_path: Path) -> None:
    """Report storage writes Markdown and updated thesis can be persisted."""

    thesis, score, packet = _inputs()
    engine = make_engine(f"sqlite:///{tmp_path / 'reports.sqlite3'}")
    init_db(engine)
    factory = make_session_factory(engine)
    settings = Settings(_env_file=None, artifacts_path=tmp_path)
    tracker = ThesisTracker(session_factory=factory)
    store = ReportStore(settings=settings, session_factory=factory)
    generator = ReportGenerator()

    report = store.save(generator.generate(thesis, score, packet))
    updated = tracker.save(generator.apply_to_thesis(thesis, report))

    assert report.markdown_path is not None
    assert Path(report.markdown_path).exists()
    assert updated.latest_report_id == report.id


def _inputs():
    packet = EnrichmentService().enrich_symbol("MSFT", fixture_data=load_fixture_enrichment("MSFT"))
    candidate = Candidate(
        symbol="MSFT",
        source_screener="test",
        source_screeners=["test"],
        discovered_at_utc=now_utc(),
        screener_rank=1,
        raw_fields={},
        cache_key="cache",
    )
    score = RankingService().score_candidate(candidate, packet)
    thesis = ThesisGenerator().generate(score, packet)
    return thesis, score, packet
