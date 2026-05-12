"""Enrichment API routes."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from isa_system.api.routers.discovery import latest_discovery_result
from isa_system.enrichment.enrichment_packet import (
    CandidateEnrichmentPacket,
    EnrichmentService,
    load_fixture_enrichment,
)
from isa_system.enrichment.openbb_client import OpenBBClient, OpenBBHealth

router = APIRouter(tags=["enrichment"])

_LATEST_ENRICHMENT: dict[str, CandidateEnrichmentPacket] = {}


class EnrichmentRunRequest(BaseModel):
    """Request to enrich symbols or latest candidates."""

    model_config = ConfigDict(extra="forbid")

    symbols: list[str] = Field(default_factory=list)
    use_fixtures: bool = False


@router.post("/enrichment/run", response_model=list[CandidateEnrichmentPacket])
def run_enrichment(request: EnrichmentRunRequest | None = None) -> list[CandidateEnrichmentPacket]:
    """Run candidate enrichment for supplied symbols or latest candidates."""

    global _LATEST_ENRICHMENT
    request = request or EnrichmentRunRequest()
    symbols = request.symbols or _latest_candidate_symbols()
    fixture_data = (
        {symbol.upper(): load_fixture_enrichment(symbol) for symbol in symbols}
        if request.use_fixtures
        else None
    )
    packets = EnrichmentService().enrich_symbols(symbols, fixture_data_by_symbol=fixture_data)
    _LATEST_ENRICHMENT.update({packet.symbol: packet for packet in packets})
    return packets


@router.get("/enrichment/{symbol}", response_model=CandidateEnrichmentPacket | None)
def get_enrichment(symbol: str) -> CandidateEnrichmentPacket | None:
    """Return the latest enrichment packet for a symbol."""

    return _LATEST_ENRICHMENT.get(symbol.upper())


@router.get("/health/openbb", response_model=OpenBBHealth)
def openbb_health() -> OpenBBHealth:
    """Return OpenBB API health without failing the main app health."""

    return OpenBBClient().health_check()


def latest_enrichment_packets() -> dict[str, CandidateEnrichmentPacket]:
    """Return latest enrichment state for later scoring routes."""

    return _LATEST_ENRICHMENT


def _latest_candidate_symbols() -> list[str]:
    latest = latest_discovery_result()
    if latest is None:
        return []
    return [candidate.symbol for candidate in latest.candidates]
