# Portfolio Intelligence Acceptance Checklist

## Safety

- [x] No live Trading 212 order submission endpoint exists.
- [x] Trading 212 integration is read-only plus order preview only.
- [x] Order previews always require manual approval.
- [x] Runtime defaults are preview-first and local-first.
- [x] Provider credentials are loaded from environment only and never printed.
- [x] OpenBB unavailable behaviour is graceful.
- [x] Finviz blocking, empty pages, or layout changes do not crash discovery.

## Phase Checks

- [x] Phase 0: pytest passes, ruff passes, FastAPI `/health` works in-process.
- [x] Phase 1: Finviz fixture discovery produces deduplicated candidates.
- [x] Phase 2: OpenBB enrichment packets tolerate missing sections.
- [x] Phase 3: Top 10 candidates include score breakdowns and explanations.
- [x] Phase 4: Thesis records persist and decisions include rationale.
- [x] Phase 5: Offline research reports are saved and update thesis fields.
- [x] Phase 6: Portfolio review avoids churn and explains proposals.
- [x] Phase 7: Broker read-only and order preview tests pass.
- [x] Phase 8: Workspace widget metadata returns valid JSON.
- [x] Phase 9: Offline smoke pipeline creates expected artifacts.
- [x] Phase 10: Docs describe architecture, runbook, safety, and roadmap.

## Final Checks

- [x] `$env:PYTHONPATH='src'; python -m pytest -q`
- [x] `python -m ruff check .`
- [x] `python -m ruff format --check .`
- [x] `python -m mypy` is clean or documented with limited warnings.
- [x] `python scripts/smoke_test.py` runs offline.
- [ ] `python scripts/run_api.py` starts the API on `127.0.0.1:8002`
      (blocked during this run by an existing local listener on port 8002).
- [x] `POST /orchestrator/run` works with fixture data.
- [x] All timestamps are timezone-aware UTC.
- [x] No secrets are committed.
