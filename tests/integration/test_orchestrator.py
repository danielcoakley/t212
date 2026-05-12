"""End-to-end orchestrator tests."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from isa_system.api.main import app
from isa_system.orchestrator import PortfolioOrchestrator


def test_full_pipeline_runs_with_fixtures_and_writes_outputs(monkeypatch, tmp_path: Path) -> None:
    """Full fixture pipeline creates expected smoke artifacts."""

    monkeypatch.setenv("ISA_OPERATIONAL_DB_DSN", f"sqlite:///{tmp_path / 'orch.sqlite3'}")
    monkeypatch.setenv("ISA_ARTIFACTS_PATH", str(tmp_path / "artifacts"))
    from isa_system.settings import clear_settings_cache

    clear_settings_cache()
    artifact_dir = tmp_path / "smoke"

    run = PortfolioOrchestrator().run(
        use_fixtures=True,
        write_artifacts=True,
        artifact_dir=artifact_dir,
    )

    assert run.status == "completed"
    assert run.candidate_count == 7
    assert run.top10_symbols
    assert run.watchlist_symbols
    assert run.rebalance_proposals
    assert run.order_previews
    assert (artifact_dir / "latest_candidates.csv").exists()
    assert (artifact_dir / "top10.csv").exists()
    assert (artifact_dir / "research_reports").exists()
    assert (artifact_dir / "watchlist.csv").exists()
    assert (artifact_dir / "rebalance_proposals.json").exists()
    assert (artifact_dir / "order_previews.json").exists()
    assert (artifact_dir / "run_summary.json").exists()

    clear_settings_cache()


def test_orchestrator_api_run_and_latest(monkeypatch, tmp_path: Path) -> None:
    """Orchestrator API runs with fixtures and exposes latest run."""

    monkeypatch.setenv("ISA_OPERATIONAL_DB_DSN", f"sqlite:///{tmp_path / 'api-orch.sqlite3'}")
    monkeypatch.setenv("ISA_ARTIFACTS_PATH", str(tmp_path / "artifacts"))
    from isa_system.settings import clear_settings_cache

    clear_settings_cache()
    client = TestClient(app)

    response = client.post("/orchestrator/run")
    latest = client.get("/orchestrator/latest")

    assert response.status_code == 200
    assert latest.status_code == 200
    assert response.json()["run_id"] == latest.json()["run_id"]
    assert response.json()["order_previews"]

    clear_settings_cache()
