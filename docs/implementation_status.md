# Portfolio Intelligence Implementation Status

## Phase 0 - Project Bootstrap

Completed items:

- Kept one system by adapting the existing `isa_system` package instead of
  introducing a parallel package.
- Added implementation plan and acceptance checklist documents.
- Updated project metadata, Makefile targets, and local environment examples
  for the portfolio intelligence API on `127.0.0.1:8002`.
- Added OpenBB service defaults for API `6900` and MCP `8001`.
- Added example YAML configs for local settings, Finviz screeners, OpenBB,
  holdings, and watchlist.
- Added `scripts/check_openbb.py` for keyless `/openapi.json` and
  `/widgets.json` checks.
- Added `scripts/run_api.py` and placeholder phase CLI entry points.
- Extended `/health` to remain OpenBB-independent and expose conservative
  OpenBB/live-trading subsystem status.
- Added focused API regression coverage for the Phase 0 health contract.

Test results:

- `$env:PYTHONPATH='src'; python -m pytest -q` -> 116 passed.
- `python -m ruff check .` -> passed.
- `python -m ruff format --check .` -> passed.
- Direct network smoke on `127.0.0.1:8002` was not taken over because that port
  was already occupied by an existing listener. The updated app was verified
  through FastAPI `TestClient`.

Remaining risks:

- Existing code still contains guarded live execution scaffolding from the
  prior MVP. The new portfolio intelligence workflow must avoid expanding it
  and should keep future Trading 212 work read-only/order-preview only.
- Phase CLI scripts beyond API/OpenBB are placeholders until their respective
  phases are implemented.
- The `8002` port conflict should be cleared before manual browser/API smoke.

Next steps:

- Phase 1: implement curated Finviz discovery, local HTML caching, parser
  fixture tests, candidate deduplication, and discovery/candidate API routes.

## Phase 1 - Finviz Discovery Engine

Completed items:

- Added `isa_system.discovery` package for Finviz-specific discovery.
- Added curated screener YAML for Elite GARP Compounders, Hidden Compounders,
  and Post-Earnings Acceleration.
- Implemented `FinvizScreenerConfig`, `FinvizFetcher`, `FinvizParser`, and
  `CandidateIntakeService`.
- Added polite Finviz headers, retry/backoff, local HTML caching, blocked/empty
  page handling, and fixture-first offline execution.
- Implemented symbol-level dedupe, source screener preservation, appearance
  count, and multi-screener boost.
- Added `POST /discovery/run`, `GET /discovery/latest`, and
  `GET /candidates/latest`.
- Added local Finviz fixture HTML and parser/intake/API tests.
- Wired `scripts/run_discovery.py --fixtures` for offline discovery.

Test results:

- `$env:PYTHONPATH='src'; python -m pytest -q` -> 121 passed.
- `python -m ruff check .` -> passed.
- `python -m ruff format --check .` -> passed.
- `$env:PYTHONPATH='src'; python scripts/run_discovery.py --fixtures` -> 7
  deduplicated candidates and no warnings.

Remaining risks:

- Finviz layout changes are handled by returning no rows and warnings, but
  live parsing should be monitored before relying on a new page shape.
- Live Finviz fetching is deliberately conservative and not scheduled or
  aggressive; operator workflows should prefer cached/fixture paths during
  tests.

Next steps:

- Phase 2: implement OpenBB client wrapper, central endpoint definitions,
  enrichment packets, data quality scoring, graceful missing-route behaviour,
  and enrichment API routes.

## Phase 2 - OpenBB Enrichment Layer

Completed items:

- Added `isa_system.enrichment` with centralised OpenBB endpoint definitions.
- Implemented `OpenBBClient` with configurable base URL, health check,
  per-run cache, timeouts, and structured section results.
- Implemented `CandidateEnrichmentPacket` and enrichment service.
- Added fixture-mode enrichment that never requires live OpenBB or API keys.
- Added price-history summary, profile/fundamental/valuation extraction,
  missing-section tracking, section errors, and data quality scoring.
- Added `POST /enrichment/run`, `GET /enrichment/{symbol}`, and
  `GET /health/openbb`.
- Added OpenBB fixture data and tests for unavailable OpenBB, mocked section
  response/cache, fixture packet creation, missing data, and health status.

Test results:

- `$env:PYTHONPATH='src'; python -m pytest -q` -> 127 passed.
- `python -m ruff check .` -> passed.
- `python -m ruff format --check .` -> passed.

Remaining risks:

- OpenBB endpoint paths are best-effort placeholders isolated in
  `openbb_endpoints.py`; route availability must be confirmed against the
  operator's installed OpenBB version.
- Fixture mode intentionally marks absent sections missing instead of mixing
  fixtures with live calls.

Next steps:

- Phase 3: implement factor scores, composite opportunity scoring, ranking,
  top 10 selection, score explanations, and score/top10 API routes.

## Phase 3 - Scoring And Top 10 Selection

Completed items:

- Added `isa_system.scoring` with factor weights, factor score models,
  composite/opportunity score models, explanations, and ranking service.
- Implemented deterministic scoring for growth, quality, valuation, momentum,
  catalysts, balance sheet, sentiment, and sector/theme tailwinds.
- Added missing-data and stale-data penalties plus multi-screener boosts.
- Added top-N selection and score explanations.
- Added `POST /scores/run`, `GET /scores/latest`, and `GET /candidates/top10`.
- Added tests for weight sum, missing data penalty, stale data penalty,
  multi-screener boost, top 10 selection, explanations, and API scoring flow.

Test results:

- `$env:PYTHONPATH='src'; python -m pytest -q` -> 133 passed.
- `python -m ruff check .` -> passed.
- `python -m ruff format --check .` -> passed.

Remaining risks:

- Scores are deterministic and intentionally simple; later phases should refine
  formulas with validated OpenBB fields and official-source evidence.
- Score snapshots are still process-local until persistence is introduced for
  thesis/report records.

Next steps:

- Phase 4: implement thesis models, deterministic thesis generation, decision
  engine rules, thesis tracking/lifecycle services, persistence, and thesis API
  routes.

## Phase 4 - Thesis Engine

Completed items:

- Added thesis statuses, investment decisions, and full thesis Pydantic model.
- Added rule-based `DecisionEngine` covering BUY_NOW, WATCHLIST_WAIT_ENTRY,
  WATCHLIST_WAIT_CATALYST, and REJECT paths.
- Added deterministic `ThesisGenerator` that uses only provided score and
  enrichment data and does not fabricate price levels when price data is
  missing.
- Added SQLite-backed `ThesisTracker` and Alembic migration
  `0004_investment_theses`.
- Added lifecycle helper for watchlist and active thesis views.
- Added `POST /thesis/generate/{symbol}`, `GET /thesis/{symbol}`,
  `GET /thesis/watchlist`, `GET /thesis/active`, and
  `POST /thesis/review/{symbol}`.
- Added unit and integration tests for decision rules, no fabricated targets,
  thesis persistence, watchlist retention, and API generation.

Test results:

- `$env:PYTHONPATH='src'; python -m pytest -q` -> 141 passed.
- `python -m ruff check .` -> passed.
- `python -m ruff format --check .` -> passed.

Remaining risks:

- BUY_NOW remains a research decision, not order authority. Portfolio-improves
  checks are still a Phase 6 input and default conservatively within this
  standalone thesis layer.
- Thesis generation is deterministic and template-based until optional LLM memo
  generation is added in Phase 5.

Next steps:

- Phase 5: implement structured research memos, prompt builder, report store,
  deterministic no-key report generation, thesis updates from reports, and
  research API routes.

## Phase 5 - Deep Research Reports

Completed items:

- Added structured research memo models and the required memo section set.
- Added source-bounded prompt builder with data quality, missing-data notes,
  no-advice, no-certainty, and no-live-execution rules.
- Added deterministic no-key report generation from thesis, score, and
  enrichment data.
- Added report application back to thesis fields including latest report id,
  entry/exit/invalidation fields, and next review date.
- Added Markdown plus SQLite report persistence and Alembic migration
  `0005_research_reports`.
- Added `POST /research/run-top10`, `POST /research/report/{symbol}`,
  `GET /research/report/{symbol}`, and `GET /research/reports/latest`.
- Added tests for no-key reports, prompt safety/data-quality notes, report
  persistence, thesis updates, top 10 report generation, and watchlist retention.

Test results:

- `$env:PYTHONPATH='src'; python -m pytest -q` -> 145 passed.
- `python -m ruff check .` -> passed.
- `python -m ruff format --check .` -> passed.

Remaining risks:

- Optional LLM memo generation is represented by safe prompt construction but
  not by a live OpenAI call in this phase.
- Report quality is deterministic and conservative until richer enrichment and
  portfolio comparison data arrive.

Next steps:

- Phase 6: implement holdings models, portfolio comparison, risk constraints,
  watchlist review, rationale-based rebalance proposals, and portfolio/rebalance
  API routes.

## Phase 6 - Portfolio Manager And Holdings Comparison

Completed items:

- Added portfolio holding, risk config, sleeve default, and rebalance proposal
  models.
- Added rationale-based portfolio comparison service.
- Implemented no-churn behaviour when existing holdings remain superior.
- Implemented watchlist actions for poor entry and unresolved catalysts.
- Implemented material-superiority replacement rule, cooldown blocking,
  broken-thesis sell review, target-reached trim/sell review, and strategy
  sleeve limit handling.
- Added `POST /portfolio/review`, `GET /portfolio/holdings`,
  `POST /portfolio/holdings/load-example`, `POST /watchlist/review`,
  `POST /rebalance/propose`, `GET /rebalance/latest`, and
  `GET /portfolio/actions/latest`.
- Added unit and integration tests for the required proposal behaviours.

Test results:

- `$env:PYTHONPATH='src'; python -m pytest -q` -> 153 passed.
- `python -m ruff check .` -> passed.
- `python -m ruff format --check .` -> passed.

Remaining risks:

- Holdings/proposal state is still in-process for this phase; later
  orchestration can make run snapshots durable.
- At the end of Phase 6, the legacy `/rebalances/submit` route still existed
  from the prior MVP. This was resolved in Phase 7; the route now returns 404.

Next steps:

- Phase 7: implement Trading 212 read-only models/client helpers, broker
  account/positions routes, order preview only, duplicate hash preparation, and
  remove live submission authority from the unified API surface.

## Phase 7 - Trading 212 Read-Only And Order Preview

Completed items:

- Added `isa_system.trading212` package with config, read-only account and
  position models, instrument mapping helpers, safety helper, and local order
  preview generation.
- Added read-only Trading 212 client where API key is optional and no POST
  order calls exist in the new workflow.
- Added deterministic duplicate order hash preparation for future safety.
- Added local order preview fields for direction, quantity, trade value, FX
  impact, SDRT placeholder, cash buffer effect, target weight, warnings, and
  manual approval requirement.
- Added `GET /broker/account`, `GET /broker/positions`, and
  `POST /orders/preview`.
- Removed the legacy `/rebalances/submit` route from the unified API surface;
  it now returns 404.
- Disabled legacy Trading 212 provider submit methods by making them raise
  `NotImplementedError`.
- Added tests for optional API key, mocked account/positions, order preview,
  deterministic duplicate hash, manual approval, and no live submit endpoint.

Test results:

- `$env:PYTHONPATH='src'; python -m pytest -q` -> 159 passed.
- `python -m ruff check .` -> passed.
- `python -m ruff format --check .` -> passed.

Remaining risks:

- Broker read-only endpoint paths should be validated against the operator's
  Trading 212 environment before use with real credentials.
- Future live execution must be treated as a separate phase with explicit safety
  review; it is not present in this build.

Next steps:

- Phase 8: add OpenBB Workspace widget metadata and simple table-friendly JSON
  endpoints for ranked candidates, thesis/watchlist, holdings, proposals, risk
  warnings, and reports.

## Phase 8 - OpenBB Workspace Outputs

Completed items:

- Added workspace widget metadata models and app metadata payload.
- Added `GET /workspace/widgets.json` for OpenBB Workspace-style backend
  consumption.
- Added `GET /workspace/risk-warnings` for simple risk warning table output.
- Registered widgets for ranked candidates, top 10 research queue, thesis
  watchlist, portfolio holdings, rebalance proposals, risk warnings, and
  research reports.
- Added tests that widget metadata is local/OpenBB-independent and target
  endpoints exist.

Test results:

- `$env:PYTHONPATH='src'; python -m pytest -q` -> 161 passed.
- `python -m ruff check .` -> passed.
- `python -m ruff format --check .` -> passed.

Remaining risks:

- Widget metadata is intentionally simple and may need adjustment for the exact
  OpenBB Workspace custom backend contract in use locally.

Next steps:

- Phase 9: implement end-to-end orchestrator, run records, orchestrator API
  routes, full-pipeline script, and offline smoke artifacts.

## Phase 9 - End-To-End Orchestration

Completed items:

- Added `PortfolioOrchestrator` and `OrchestratorRun` summary model.
- Implemented fixture-backed end-to-end flow: Finviz discovery, dedupe,
  enrichment, scoring, top 10 selection, thesis generation, report generation,
  watchlist update, portfolio review, rebalance proposals, order previews, and
  final run summary.
- Added smoke artifact output:
  `artifacts/smoke/latest_candidates.csv`, `top10.csv`,
  `research_reports/`, `watchlist.csv`, `rebalance_proposals.json`,
  `order_previews.json`, and `run_summary.json`.
- Added `POST /orchestrator/run`, `GET /orchestrator/latest`, and
  `GET /orchestrator/runs/{run_id}`.
- Added `scripts/run_full_pipeline.py` and updated `scripts/smoke_test.py`.
- Added end-to-end tests for service and API orchestration.

Test results:

- `$env:PYTHONPATH='src'; python scripts/smoke_test.py` -> completed and wrote
  smoke artifacts.
- `$env:PYTHONPATH='src'; python -m pytest -q` -> 163 passed.
- `python -m ruff check .` -> passed.
- `python -m ruff format --check .` -> passed.

Remaining risks:

- Orchestrator run registry is process-local; smoke artifacts and report/thesis
  DB records are durable.
- Fixture enrichment reuses compact sample data and is for offline workflow
  validation, not investment decision quality.

Next steps:

- Phase 10: complete final documentation and hardening notes, including
  architecture, workflow, OpenBB setup, Finviz usage, scoring model, thesis
  lifecycle, decision rules, portfolio manager, Trading 212 safety, Workspace
  integration, runbook, and roadmap.

## Phase 10 - Documentation And Final Hardening

Completed items:

- Added required docs for architecture, autonomous workflow, OpenBB setup,
  Finviz discovery, scoring model, thesis lifecycle, decision rules, portfolio
  manager, Trading 212 safety, Workspace integration, runbook, and roadmap.
- Updated docs to reflect the unified `isa_system` implementation and no-live
  Trading 212 boundary.
- Re-ran final tests, lint, formatting, mypy, and smoke script.

Test results:

- `$env:PYTHONPATH='src'; python -m pytest -q` -> 163 passed.
- `python -m ruff check .` -> passed.
- `python -m ruff format --check .` -> passed.
- `$env:PYTHONPATH='src'; python scripts/smoke_test.py` -> completed and wrote
  smoke artifacts.
- `$env:PYTHONPATH='src'; python -m mypy` -> 25 legacy warnings remain in
  pre-existing modules: `services/recommendation_handoff.py`,
  `services/pilot_workflow.py`, `services/paper_persistence.py`, and
  `api/routers/operator_report.py`. New Phase 0-10 modules are clean after
  targeted fixes.

Remaining risks:

- Mypy baseline still has legacy type issues unrelated to the new portfolio
  intelligence modules.
- API network smoke on port 8002 still depends on clearing any existing local
  listener before startup.

Next steps:

- Validate OpenBB endpoint paths against the operator's installed OpenBB
  version.
- Validate Trading 212 read-only endpoint paths in demo mode with local
  credentials.
- Decide whether to make orchestrator run records durable beyond smoke
  artifacts.

## Holdings Health Check Workstream

Completed items:

- Added on-demand holdings health report generation inside the unified
  `isa_system` app.
- Added `OPENAI_HEALTH_MODEL`, defaulting to `o3-deep-research`, while keeping
  no-key local fallback behaviour for offline tests and safe first runs.
- Added append-only SQLite history for health report runs and separate
  operator accepted/adjusted target/action updates.
- Added `POST /health-check/run`, `GET /health-check/latest`,
  `GET /health-check/reports`, `GET /health-check/reports/{report_id}`, and
  `POST /health-check/reports/{report_id}/holdings/{symbol}/accept`.
- Added a Streamlit Health Check page with report history, bear/base/bull
  targets, recommended action, and accept/adjust carry-forward controls.
- Added focused unit and integration tests for fallback reports, mocked OpenAI
  responses, API persistence, dashboard helper transforms, and migration
  discoverability.

Test results:

- `$env:PYTHONPATH='src'; python -m pytest -q tests/unit/test_holding_health.py tests/unit/test_dashboard_health_check.py tests/integration/test_holding_health_api.py tests/unit/test_migration_readiness.py` -> 9 passed.
- `python -m ruff check src/isa_system/services/holding_health.py src/isa_system/dashboard/pages/health_check.py src/isa_system/api/routers/holding_health.py src/isa_system/settings.py src/isa_system/db/models.py src/isa_system/api/main.py tests/unit/test_holding_health.py tests/unit/test_dashboard_health_check.py tests/integration/test_holding_health_api.py tests/unit/test_migration_readiness.py` -> passed.
- `$env:PYTHONPATH='src'; python -m pytest -q` -> 170 passed.
- `python -m ruff check .` -> passed.
- `python -m ruff format --check .` -> passed.
- `$env:PYTHONPATH='src'; python -m mypy` -> unchanged 25 legacy warnings in
  `services/recommendation_handoff.py`, `services/pilot_workflow.py`,
  `services/paper_persistence.py`, and `api/routers/operator_report.py`.

Remaining risks:

- Real OpenAI deep research report latency and model access need to be validated
  with the operator's API account. The no-key fallback is conservative and not
  a substitute for current external research.
- Accepted targets/actions are stored as local operator carry-forward state;
  they do not yet feed every downstream thesis or portfolio comparison surface.

Next steps:

- Decide whether accepted health-check targets should automatically update
  thesis records or stay as a separate operator overlay.
- Validate the deep research prompt against real current holdings and tune the
  evidence packet after the first live-key run.

## Command Centre Finviz Screener Page

Completed items:

- Reduced the FastAPI command centre left nav to Overview and Finviz Screener,
  so nav entries now represent real pages rather than anchors inside Overview.
- Added `GET /discovery/finviz/settings` for curated presets, supported Finviz
  filter capabilities, and principal valuation field metadata.
- Added `POST /discovery/finviz/screener` for configurable, cached Finviz runs
  that also refresh the latest candidate discovery result for downstream
  scoring.
- Expanded the Finviz parser to preserve best-effort table fields, ranks,
  normalized symbols, and deterministic Finviz profile links.
- Added a screener page with preset application, filter toggles, raw filter-code
  entry, dynamic Finviz URL link, principal valuation column toggles, and a full
  filtered-results table.
- Reworked the screener to use a Finviz-like compact toolbar with preset,
  order-by, direction, signal, ticker input, run, collapsible filter drawer, and
  icon-only external Finviz links.
- Replaced large explicit filter cards with dropdown controls grouped under
  Descriptive, Fundamental, and Technical tabs.
- Added category-grouped table-column selection, custom column labels, and
  client-side sorting by any visible column. Selected columns now render even
  when the current response has blank values for that field.

Test results:

- `$env:PYTHONPATH='src'; python -m pytest -q tests/unit/test_finviz_parser.py tests/integration/test_discovery_api.py tests/integration/test_command_center_ui.py` -> 8 passed.
- `$env:PYTHONPATH='src'; python -m pytest -q` -> 175 passed.
- `python -m ruff check .` -> passed.
- `python -m ruff format --check .` -> passed.
- Browser/IAB rendered QA on `http://localhost:8501/?ui=screener-final#screener`
  verified page identity, hydrated filter controls, fixture-run results,
  profile links, Overview navigation, and no console errors.
- Browser/IAB rendered QA on `http://localhost:8501/?ui=finvizlike2#screener`
  verified collapsed filters, Finviz-style dropdown controls, category-sorted
  column selection, custom column UI, visible-column sorting, icon-only profile
  links, and no localhost console errors.

Remaining risks:

- Live Finviz layout can change or block automated access; the page remains
  operator-triggered and fixture-tested, but live table-shape validation should
  continue.
- The current workbench handles the first returned screener page. Pagination is
  a future enhancement if the operator needs broader table capture.

Next steps:

- Add richer table fixtures with valuation fields once a representative live
  Finviz response is cached locally.
- Decide whether configurable screener definitions should be persisted as named
  local presets beyond the three bundled YAML presets.

## Command Centre Screener Refinement

Completed items:

- Pulled the screener page back into the command-centre aesthetic instead of a
  literal Finviz skin.
- Kept presets prominent, with filters in a collapsed operator drawer grouped
  by Descriptive, Fundamental, and Technical categories.
- Expanded dropdown choices across the exposed Finviz indicators, including
  broader under/over ranges for valuation, growth, margin, leverage, ownership,
  moving-average, performance, change, RSI, and descriptive controls.
- Added local custom-preset persistence via `POST /discovery/finviz/presets`;
  built-in YAML presets remain read-only, while operator-saved presets reload
  from local artifacts.
- Restored the lighter app-style results table while preserving dynamic column
  selection, custom column labels, icon-only Finviz profile links, and sorting
  by any visible column.
- Bumped dashboard asset versions so the browser loads the updated CSS and JS.

Test results:

- `$env:PYTHONPATH='src'; python -m pytest tests/integration/test_discovery_api.py tests/integration/test_command_center_ui.py -q` -> 6 passed.
- `$env:PYTHONPATH='src'; python -m pytest -q` -> 176 passed.
- `python -m ruff check .` -> passed.
- `node --check src/isa_system/web/app.js` -> passed.
- `$env:PYTHONPATH='src'; python -m mypy` -> unchanged 25 legacy errors in
  `services/recommendation_handoff.py`, `services/pilot_workflow.py`,
  `services/paper_persistence.py`, and `api/routers/operator_report.py`.
- Browser/IAB rendered QA on `http://localhost:8501/#screener` verified page
  identity, non-blank render, expanded filter drawer, full P/E dropdown range,
  saved custom preset persistence after reload, fixture-run results, RSI column
  toggle, ticker sorting, and no console errors for the updated dashboard asset
  version.

Remaining risks:

- The dropdown map now covers the main Finviz-style descriptive, fundamental,
  and technical indicators used by the cockpit, but rarely used or uncertain
  Finviz filter codes may still need to be added after live validation. The raw
  custom filter-code input remains available for those cases.
- Live Finviz table columns and blocking behaviour still need periodic
  validation; fixture tests cover offline behaviour.

Next steps:

- Add pagination support if live screens regularly return more than the first
  Finviz page of results.
- Add more representative cached Finviz valuation-table fixtures once live
  operator runs confirm current column names.

## Screener Table Data Alignment And Metric Colouring

Completed items:

- Fixed Finviz parser header detection so filter-form rows are no longer
  mistaken for results-table headers.
- Scoped row extraction to Finviz's actual `screener_table`, including support
  for Finviz pages that omit an explicit `</tr>` in the header row.
- Correctly maps valuation-table columns such as `Market Cap`, `P/E`,
  `Forward P/E`, `PEG`, `EPS this Y`, `Price`, `Change`, and `Volume`.
- Extracts embedded Finviz row metadata for `Company`, `Industry`, and
  `Country`, and displays `Company` and `Industry` by default.
- Added a richer Finviz fixture with valuation fields so offline tests cover
  the exact column-alignment issue.
- Tightened table column widths, especially `Market Cap`, and aligned numeric
  values consistently under their headers.
- Added first-pass sector-aware metric colouring using broad investing
  heuristics for valuation, growth, margins, returns, leverage, performance,
  and price change.

Test results:

- `$env:PYTHONPATH='src'; python -m pytest tests/unit/test_finviz_parser.py tests/integration/test_discovery_api.py tests/integration/test_command_center_ui.py -q` -> 10 passed.
- `$env:PYTHONPATH='src'; python -m pytest -q` -> 177 passed.
- `python -m ruff check .` -> passed.
- `node --check src/isa_system/web/app.js` -> passed.
- `$env:PYTHONPATH='src'; python -m mypy` -> unchanged 25 legacy errors in
  `services/recommendation_handoff.py`, `services/pilot_workflow.py`,
  `services/paper_persistence.py`, and `api/routers/operator_report.py`.
- Browser/IAB rendered QA on `http://localhost:8501/#screener` verified fixture
  run table output with company, industry, valuation fields, EPS fields,
  volume, sortable columns, and coloured metric pills.

Remaining risks:

- Metric colours are intentionally broad heuristics. Sector calibration should
  be refined after collecting more live examples and deciding the operator's
  preferred valuation/growth bands.
- Finviz may change class names or embedded metadata attributes; parser tests
  now cover the current live table shape and fixture fallback.

Next steps:

- Add optional sector-specific colour-band configuration if the default
  heuristic proves too blunt.
- Add live-cache regression fixtures for additional Finviz table views.

## Screener Review Cleanup

Completed items:

- Renamed the left navigation item from `Finviz Screener` to `Screener`.
- Removed the screener page eyebrow, title, and explanatory paragraph so the
  page opens directly into the operator controls.
- Removed the fixture-only run button from the visible dashboard while leaving
  fixture-backed tests and endpoints intact.
- Moved the external Finviz profile/screen icon beside the preset selector for
  clearer context.
- Bumped dashboard asset versions for the updated markup and CSS.

Test results:

- `$env:PYTHONPATH='src'; python -m pytest tests/integration/test_command_center_ui.py -q` -> 3 passed.
- `$env:PYTHONPATH='src'; python -m pytest -q` -> 177 passed.
- `python -m ruff check .` -> passed.
- `python -m ruff format --check src/isa_system/web tests/integration/test_command_center_ui.py` -> passed.
- `node --check src/isa_system/web/app.js` -> passed.
- `$env:PYTHONPATH='src'; python -m mypy` -> unchanged 25 legacy errors in
  `services/recommendation_handoff.py`, `services/pilot_workflow.py`,
  `services/paper_persistence.py`, and `api/routers/operator_report.py`.
- Browser/IAB rendered QA on `http://localhost:8501/#screener` verified the
  cleaned navigation label, removed intro copy, removed fixture button, and
  Finviz link placement beside the preset dropdown.

Remaining risks:

- The visible dashboard no longer exposes fixture execution, so fixture runs
  remain a test/offline path rather than an operator control.

Next steps:

- Continue refining live screener pagination and table-state persistence as
  the next discovery milestone.
