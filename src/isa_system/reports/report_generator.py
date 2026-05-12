"""Structured deterministic report generation."""

from __future__ import annotations

from datetime import timedelta

from isa_system.enrichment.enrichment_packet import CandidateEnrichmentPacket
from isa_system.reports.memo_models import MemoSection, ResearchReport
from isa_system.scoring.composite_score import CompositeScore
from isa_system.thesis.models import Thesis
from isa_system.utils.hashing import sha256_digest
from isa_system.utils.time import now_utc


class ReportGenerator:
    """Generate structured investment memos from existing thesis data."""

    def generate(
        self,
        thesis: Thesis,
        score: CompositeScore,
        packet: CandidateEnrichmentPacket | None,
    ) -> ResearchReport:
        """Create a deterministic memo from provided data."""

        generated_at = now_utc()
        sections = _sections(thesis, score, packet)
        markdown = _markdown(thesis.symbol, sections)
        report_id = sha256_digest(
            {"symbol": thesis.symbol, "thesis_id": thesis.id, "generated_at_utc": generated_at}
        )[:20]
        return ResearchReport(
            id=report_id,
            symbol=thesis.symbol,
            thesis_id=thesis.id,
            decision=thesis.decision,
            sections=sections,
            markdown=markdown,
            generated_at_utc=generated_at,
        )

    def apply_to_thesis(self, thesis: Thesis, report: ResearchReport) -> Thesis:
        """Return an updated thesis carrying report-derived review fields."""

        updated_at = now_utc()
        return thesis.model_copy(
            update={
                "latest_report_id": report.id,
                "updated_at_utc": updated_at,
                "next_review_date": updated_at + timedelta(days=30),
                "one_line_thesis": report.sections[MemoSection.EXECUTIVE_SUMMARY.value],
                "entry_conditions": [report.sections[MemoSection.ENTRY_PLAN.value]],
                "exit_conditions": [report.sections[MemoSection.EXIT_PLAN.value]],
                "invalidation_triggers": [report.sections[MemoSection.INVALIDATION.value]],
            }
        )


def _sections(
    thesis: Thesis,
    score: CompositeScore,
    packet: CandidateEnrichmentPacket | None,
) -> dict[str, str]:
    company = thesis.company_name or thesis.symbol
    screeners = "Finviz curated discovery and opportunity score ranking."
    data_quality = packet.data_quality if packet else {"score": 0, "missing_sections": ["packet"]}
    return {
        MemoSection.EXECUTIVE_SUMMARY.value: thesis.one_line_thesis,
        MemoSection.BUSINESS_OVERVIEW.value: thesis.business_summary,
        MemoSection.SCREEN_REASON.value: screeners,
        MemoSection.FUNDAMENTAL_GROWTH.value: thesis.growth_case,
        MemoSection.QUALITY_BALANCE_SHEET.value: thesis.quality_case,
        MemoSection.VALUATION.value: thesis.valuation_case,
        MemoSection.TECHNICAL_SETUP.value: thesis.technical_setup,
        MemoSection.SENTIMENT_OWNERSHIP.value: thesis.sentiment_context,
        MemoSection.CATALYST_PATH.value: thesis.catalyst_path,
        MemoSection.BULL_CASE.value: (
            f"{company} could work if growth, quality, valuation, and catalysts remain supportive."
        ),
        MemoSection.BEAR_CASE.value: (
            "The thesis can fail if data quality is poor, valuation compresses, "
            "or catalysts do not confirm."
        ),
        MemoSection.ENTRY_PLAN.value: "; ".join(thesis.entry_conditions),
        MemoSection.EXIT_PLAN.value: "; ".join(thesis.exit_conditions),
        MemoSection.INVALIDATION.value: "; ".join(thesis.invalidation_triggers),
        MemoSection.PORTFOLIO_FIT.value: (
            "Portfolio fit requires Phase 6 comparison against current holdings."
        ),
        MemoSection.DECISION.value: f"{thesis.decision.value}: {'; '.join(thesis.rationale)}",
        MemoSection.MISSING_DATA.value: (
            f"Confidence {thesis.confidence_score:.1f}/100. Data quality: {data_quality}. "
            f"Missing notes: {', '.join(thesis.missing_data_notes) or 'none'}."
        ),
    }


def _markdown(symbol: str, sections: dict[str, str]) -> str:
    lines = [f"# Research memo: {symbol}", ""]
    for title, body in sections.items():
        lines.extend([f"## {title}", "", body, ""])
    return "\n".join(lines).strip() + "\n"
