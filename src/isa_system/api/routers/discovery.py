"""Discovery API routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from isa_system.discovery.candidate_intake import CandidateIntakeService
from isa_system.discovery.finviz_custom import (
    FinvizPresetSaveRequest,
    FinvizScreenerPreset,
    FinvizScreenerRunRequest,
    FinvizScreenerRunResult,
    FinvizScreenerSettings,
    finviz_screener_settings,
    run_finviz_workbench_screener,
    save_finviz_preset,
)
from isa_system.discovery.finviz_screeners import load_finviz_screeners
from isa_system.discovery.models import CandidateDiscoveryResult

router = APIRouter(prefix="/discovery", tags=["discovery"])

_LATEST_DISCOVERY: CandidateDiscoveryResult | None = None


class DiscoveryRunRequest(BaseModel):
    """Request to run curated candidate discovery."""

    model_config = ConfigDict(extra="forbid")

    use_fixtures: bool = False
    force_refresh: bool = False


@router.post("/run", response_model=CandidateDiscoveryResult)
def run_discovery(request: DiscoveryRunRequest | None = None) -> CandidateDiscoveryResult:
    """Run Finviz discovery using live pages or local fixture HTML."""

    global _LATEST_DISCOVERY
    request = request or DiscoveryRunRequest()
    screeners = load_finviz_screeners()
    fixture_html = _load_fixture_html() if request.use_fixtures else None
    result = CandidateIntakeService(screeners=screeners).run(
        fixture_html_by_screener=fixture_html,
        force_refresh=request.force_refresh,
    )
    _LATEST_DISCOVERY = result
    return result


@router.get("/latest", response_model=CandidateDiscoveryResult | None)
def latest_discovery() -> CandidateDiscoveryResult | None:
    """Return the latest discovery result for this process."""

    return _LATEST_DISCOVERY


@router.get("/finviz/settings", response_model=FinvizScreenerSettings)
def finviz_settings() -> FinvizScreenerSettings:
    """Return Finviz presets, filter capabilities, and valuation fields."""

    return finviz_screener_settings()


@router.post("/finviz/screener", response_model=FinvizScreenerRunResult)
def run_finviz_screener(request: FinvizScreenerRunRequest) -> FinvizScreenerRunResult:
    """Run one configurable Finviz screener and expose full table rows."""

    global _LATEST_DISCOVERY
    result = run_finviz_workbench_screener(request)
    _LATEST_DISCOVERY = result.discovery
    return result.screener


@router.post("/finviz/presets", response_model=FinvizScreenerPreset)
def save_finviz_custom_preset(request: FinvizPresetSaveRequest) -> FinvizScreenerPreset:
    """Persist an operator-defined Finviz screener preset locally."""

    try:
        return save_finviz_preset(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def latest_discovery_result() -> CandidateDiscoveryResult | None:
    """Return latest discovery state for sibling routers."""

    return _LATEST_DISCOVERY


def _load_fixture_html() -> dict[str, str]:
    fixture_dir = Path("tests/fixtures")
    fixture_names = {
        "Elite GARP Compounders": "finviz_elite_garp.html",
        "Hidden Compounders": "finviz_hidden_compounders.html",
        "Post-Earnings Acceleration": "finviz_post_earnings.html",
    }
    return {
        screener_name: (fixture_dir / file_name).read_text(encoding="utf-8")
        for screener_name, file_name in fixture_names.items()
        if (fixture_dir / file_name).exists()
    }
