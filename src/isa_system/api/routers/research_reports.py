"""Structured research report API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from isa_system.api.routers.enrichment import latest_enrichment_packets
from isa_system.api.routers.scores import latest_score_snapshot
from isa_system.reports.memo_models import ResearchReport
from isa_system.reports.report_generator import ReportGenerator
from isa_system.reports.report_store import ReportStore
from isa_system.thesis.thesis_generator import ThesisGenerator
from isa_system.thesis.thesis_tracker import ThesisTracker

router = APIRouter(prefix="/research", tags=["research"])


@router.post("/run-top10", response_model=list[ResearchReport])
def run_top10_research() -> list[ResearchReport]:
    """Generate deterministic research reports for latest top 10 candidates."""

    reports: list[ResearchReport] = []
    for score in latest_score_snapshot()[:10]:
        reports.append(generate_report(score.symbol))
    return reports


@router.post("/report/{symbol}", response_model=ResearchReport)
def generate_report(symbol: str) -> ResearchReport:
    """Generate, persist, and return a structured report for one symbol."""

    score = _score_for_symbol(symbol)
    packet = latest_enrichment_packets().get(symbol.upper())
    tracker = ThesisTracker()
    thesis = tracker.latest_for_symbol(symbol)
    if thesis is None:
        thesis = ThesisGenerator().generate(score, packet)
        tracker.save(thesis)
    generator = ReportGenerator()
    report = ReportStore().save(generator.generate(thesis, score, packet))
    tracker.save(generator.apply_to_thesis(thesis, report))
    return report


@router.get("/report/{symbol}", response_model=ResearchReport | None)
def get_report(symbol: str) -> ResearchReport | None:
    """Return latest report for a symbol."""

    return ReportStore().latest_for_symbol(symbol)


@router.get("/reports/latest", response_model=list[ResearchReport])
def latest_reports() -> list[ResearchReport]:
    """Return latest generated reports."""

    return ReportStore().latest()


def _score_for_symbol(symbol: str):
    for score in latest_score_snapshot():
        if score.symbol == symbol.upper():
            return score
    raise HTTPException(status_code=404, detail=f"No score found for {symbol.upper()}.")
