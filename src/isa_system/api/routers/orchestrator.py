"""End-to-end orchestrator API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from isa_system.orchestrator import OrchestratorRun, PortfolioOrchestrator

router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])

_RUNS: dict[str, OrchestratorRun] = {}
_LATEST_RUN: OrchestratorRun | None = None


@router.post("/run", response_model=OrchestratorRun)
def run_orchestrator() -> OrchestratorRun:
    """Run the full offline-capable pipeline."""

    global _LATEST_RUN
    run = PortfolioOrchestrator().run(use_fixtures=True, write_artifacts=True)
    _RUNS[run.run_id] = run
    _LATEST_RUN = run
    return run


@router.get("/latest", response_model=OrchestratorRun | None)
def latest_run() -> OrchestratorRun | None:
    """Return latest orchestrator run."""

    return _LATEST_RUN


@router.get("/runs/{run_id}", response_model=OrchestratorRun)
def get_run(run_id: str) -> OrchestratorRun:
    """Return one orchestrator run by id."""

    run = _RUNS.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    return run
