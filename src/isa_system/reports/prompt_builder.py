"""Prompt construction for optional LLM research memo generation."""

from __future__ import annotations

from isa_system.enrichment.enrichment_packet import CandidateEnrichmentPacket
from isa_system.scoring.composite_score import CompositeScore
from isa_system.thesis.models import Thesis


def build_research_prompt(
    thesis: Thesis,
    score: CompositeScore,
    packet: CandidateEnrichmentPacket | None,
) -> str:
    """Build a source-bounded memo prompt for optional LLM use."""

    missing = ", ".join(thesis.missing_data_notes) or "none recorded"
    data_quality = packet.data_quality if packet else {"score": 0, "missing_sections": ["packet"]}
    return "\n".join(
        [
            "Produce a structured investment memo using provided data only.",
            "Do not make personal financial advice statements.",
            "Do not claim certainty. Do not recommend live execution.",
            "Label assumptions and include what would change the decision.",
            f"Symbol: {thesis.symbol}",
            f"Decision: {thesis.decision.value}",
            f"Composite score: {score.total_score}",
            f"Data quality: {data_quality}",
            f"Missing data notes: {missing}",
            f"Thesis: {thesis.one_line_thesis}",
            f"Score explanation: {score.explanation}",
        ]
    )
