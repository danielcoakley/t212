# Agent Coordination

## Current Goal

Ship a practical MVP operator cockpit for a local-first UK Stocks and Shares ISA
trading system. The immediate objective is not autonomous trading; it is a safe,
auditable workflow from account state to broker-seeded screener, consolidated
recommendations, deep research gate, preview-only sizing, persisted paper
evidence, and operator reporting. Paper reconciliation and management
visibility come before any deeper live execution work.

## Active Workstreams

| Workstream | Owner | Branch/worktree name | Status |
| --- | --- | --- | --- |
| Documentation and coordination | Current orchestrator | `codex/mvp-roadmap-orchestration` | Completed baseline |
| Management console / admin area | Current orchestrator / Tesla | `codex/parallel-partial-integration` | Completed first two slices |
| UI/UX consistency and simplification | Unassigned | `codex/ui-cockpit-simplification` | Pending |
| Local onboarding and pilot setup | Hypatia / orchestrator | `codex/parallel-partial-integration` | Completed first slice |
| Pilot customer workflow | Meitner | `codex/parallel-partial-integration` | Completed workflow shell |
| Paper persistence thin slice | Feynman | `codex/parallel-partial-integration` | Integrated |
| Portfolio and instrument data model | Unassigned | `codex/identity-mapping` | Pending |
| Source freshness diagnostics | Pascal | `codex/parallel-partial-integration` | Integrated |
| Recommendation engine / agent output | Russell / orchestrator | `codex/parallel-partial-integration` | Completed display slice |
| Report generation | Kant | `codex/parallel-partial-integration` | Integrated report shell |
| Paper/report integration | Turing | `codex/parallel-partial-integration` | Integrated |
| Paper cycle review surface | Cicero | `codex/parallel-partial-integration` | Integrated |
| Identity diagnostics | Heisenberg | `codex/parallel-partial-integration` | Integrated |
| API/release readiness QA | Franklin | `codex/parallel-partial-integration` | Integrated |
| Auth, roles, permissions | Unassigned | `codex/auth-permission-design` | Pending |
| Testing, QA, deployment readiness | Zeno | `codex/parallel-partial-integration` | Completed guardrail slice |
| Management diagnostics phase 2 | Tesla | `codex/parallel-partial-integration` | Integrated |

## Parallel Execution Plan

This plan selects the next five practical MVP workstreams for separate Codex
execution agents. The selection favours operator readiness, workflow clarity,
pilot evidence, and regression protection over deeper enterprise architecture.

Status update: the first three isolated worker batches have been integrated into
`codex/parallel-partial-integration`. The latest integrated batch landed paper
cycle review, report-to-paper linkage, identity diagnostics, and API release
readiness checks. Full tests and lint are green after integration.

### Selected Workstreams

| Priority | Workstream | Summary | Branch/worktree | Likely files/directories | Dependencies | Acceptance criteria | Conflict risk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Management diagnostics phase 2 | Extend the first Management page into a clearer operational status surface: cache freshness, provider readiness, broker read-only state, live guardrail state, and next required operator action. Keep controls read-only unless existing APIs already support safe state reads. | `codex/management-diagnostics` | `src/isa_system/dashboard/pages/management.py`, `src/isa_system/dashboard/data.py`, `src/isa_system/dashboard/cache_policy.py`, `src/isa_system/settings.py`, `tests/unit/test_dashboard_management.py`, possibly `docs/dashboard_layout.md` | Existing Management page, settings, broker snapshot, cache policy | Operator can see provider/config gaps, stale cache context, broker readiness, deep research availability, and live guardrails from one page. No order submission or live arming is added. Focused tests cover pure helper/status logic. | Moderate. Avoid editing `src/isa_system/dashboard/app.py` unless navigation must change. |
| 2 | Local onboarding and pilot setup | Make first-run and pilot setup obvious: local install, env setup, read-only broker connection, preview-only default, OpenAI/deep-research behaviour, and pilot acceptance checklist. Treat signup/pricing as out of scope for this local app. | `codex/local-onboarding` | `README.md`, `.env.example`, `docs/runbook.md`, `docs/assumptions.md`, `docs/README.md`, optionally `docs/pilot-checklist.md` | Management page exists and documents provider/safety concepts | A new operator can run tests, start API/dashboard, configure optional providers, understand why buy/add approvals may be blocked, and follow a pilot checklist without live trading. | Low. Stay docs-first; do not touch dashboard pages in this workstream. |
| 3 | Recommendation display UX and evidence clarity | Improve the MVP recommendation review surface so blockers, broker validation, research state, source freshness, and next action are easier to scan. Keep recommendation logic deterministic and review-only. | `codex/recommendation-display-ux` | `src/isa_system/dashboard/pages/recommendations.py`, `src/isa_system/dashboard/recommendation_charts.py`, `src/isa_system/services/recommendations.py`, `src/isa_system/services/recommendation_handoff.py`, `tests/unit/test_dashboard_recommendation_queue.py`, focused recommendation tests | Existing recommendation response, handoff rows, instrument validation, deep research status | Recommendation table clearly shows action, blockers, research gate state, preview eligibility, and source caveats. No row implies order authority. Tests cover the displayed columns or helper transforms. | Moderate. Avoid Management page and Preview page edits. |
| 4 | Pilot paper workflow shell | Add the smallest pilot-cycle shell after preview: selected recommendations, preview sizing, paper simulation snapshot, expected-vs-simulated status, and handoff notes for later persistence. Prefer a service/API/dashboard shell before schema-heavy persistence. | `codex/pilot-paper-workflow` | `src/isa_system/services/paper_simulation.py`, new `src/isa_system/services/pilot_workflow.py` or similar, `src/isa_system/dashboard/pages/preview.py`, `src/isa_system/api/routers/rebalances.py`, `tests/unit/test_paper_simulation.py`, focused integration tests | Recommendation preview and paper simulation already exist | Operator can create or inspect a paper workflow summary from preview data. Missing persistence is explicit. No live broker submit path changes. Tests verify shell output and preview/paper linkage. | Moderate. Avoid DB migrations unless absolutely necessary for this slice. |
| 5 | MVP QA and route guardrails | Add regression tests around routes and helpers most likely to break during parallel work: health, recommendations, handoff, deep research fallback, preview-only sizing, management helpers, and no-live-submit guardrails. | `codex/mvp-qa-guardrails` | `tests/unit`, `tests/integration`, `src/isa_system/smoke_test.py`, `Makefile`, possibly `.github/*` | Current passing test suite and active workstream contracts | Tests remain fast and offline-safe. New tests protect preview-only semantics, blocked live submit, missing provider behaviour, and dashboard helper transforms. No broad fixture rewrites. | Low to moderate. Avoid changing production code except tiny testability fixes. |

### Execution Order

Agents can start these in parallel, with two practical sequencing notes:

1. Start `management-diagnostics`, `local-onboarding`, and
   `mvp-qa-guardrails` immediately. They are mostly disjoint and clarify the
   operator surface.
2. Start `recommendation-display-ux` in parallel once the agent confirms it
   will not edit Management files.
3. Start `pilot-paper-workflow` in parallel if it stays schema-light. If it
   needs migrations, pause and coordinate before continuing.
4. Defer identity mapping, official-source ingestion depth, auth, hosted
   deployment, and full-auto live work until these MVP usability and safety
   slices are merged.

### Recommended Merge Order

1. `codex/mvp-qa-guardrails`
2. `codex/management-diagnostics`
3. `codex/local-onboarding`
4. `codex/recommendation-display-ux`
5. `codex/pilot-paper-workflow`

This order puts test coverage first, lands the operational status surface
before docs point to it, then merges user-facing recommendation and pilot flow
changes. If QA tests depend on a later feature branch, split them so baseline
guardrails merge first and feature-specific tests travel with the feature.

### Integrated Parallel Batch 2

These streams started from `codex/parallel-partial-integration` after the first
worker batch merged and are now integrated:

| Priority | Workstream | Branch/worktree | Likely files/directories | Acceptance criteria | Conflict risk |
| --- | --- | --- | --- | --- | --- |
| 1 | Paper persistence thin slice | `codex/paper-intent-persistence` | `src/isa_system/db/models.py`, `alembic/versions`, `src/isa_system/services/pilot_workflow.py`, `src/isa_system/api/routers/rebalances.py`, `tests/unit`, `tests/integration` | Preview/pilot rows can be saved as paper intents and simulated fills with replayable IDs. No live broker submit semantics change. Migration impact is documented. | Moderate to high; owns persistence and pilot workflow files. |
| 2 | Operator report export shell | `codex/operator-report-shell` | `src/isa_system/services`, `src/isa_system/api/routers`, `src/isa_system/dashboard/pages`, `tests/unit`, `docs` | A side-effect-free report summary can aggregate account/recommendation/research/preview/paper status into JSON or Markdown-ready sections. Missing data is explicit. | Moderate; avoid persistence files owned by paper slice. |
| 3 | Source freshness diagnostics | `codex/source-freshness-diagnostics` | `src/isa_system/dashboard/pages/recommendations.py`, `src/isa_system/dashboard/pages/management.py`, `src/isa_system/dashboard/cache_policy.py`, `tests/unit` | Recommendation and Management surfaces expose cache/source age, provider gaps, and stale warnings without changing scoring. | Moderate; coordinate with report shell before editing dashboard pages. |
| 4 | Identity mapping diagnostics | `codex/identity-diagnostics` | `src/isa_system/services/instrument_validation.py`, `src/isa_system/dashboard/pages/recommendations.py`, `tests/unit`, `docs` | Broker ticker, research symbol, ISIN, and validation confidence are easier to inspect before schema-heavy identity mapping. | Moderate; avoid migrations unless separately approved. |

Actual merge order: source freshness diagnostics, paper persistence, then
operator report shell. This landed durable paper evidence before the report
shell became the next aggregation surface.

### Integrated Parallel Batch 3

These streams started from `codex/parallel-partial-integration` after the
second worker batch merged and are now integrated:

| Priority | Workstream | Branch/worktree | Likely files/directories | Acceptance criteria | Conflict risk |
| --- | --- | --- | --- | --- | --- |
| 1 | Paper/report integration | `codex/paper-report-integration` | `src/isa_system/services/operator_report.py`, `src/isa_system/services/paper_persistence.py`, `src/isa_system/api/routers/operator_report.py`, focused tests | Operator reports can include a supplied persisted paper cycle ID or clearly show no persisted cycle. Missing reconciliation remains explicit. | Moderate; owns report and paper service boundary. |
| 2 | Paper cycle review surface | `codex/paper-cycle-review` | `src/isa_system/dashboard/pages/preview.py`, `src/isa_system/api/routers/rebalances.py`, `tests/unit`, `tests/integration` | Operators can see how to save/reload paper cycles from Preview/API output without changing live execution. | Moderate; avoid report service files. |
| 3 | Identity diagnostics | `codex/identity-diagnostics` | `src/isa_system/services/instrument_validation.py`, `src/isa_system/dashboard/recommendation_charts.py`, `tests/unit`, docs | Broker ticker, research symbol, ISIN, and validation confidence are easier to inspect before schema-heavy mapping. | Moderate; avoid migrations unless separately approved. |
| 4 | API/release readiness QA | `codex/api-release-readiness` | `tests/integration`, `src/isa_system/smoke_test.py`, `docs/runbook.md`, `TODO.md` | Fast offline checks cover new report and paper-cycle endpoints, migration shape, and no-live-submit guardrails. | Low; tests/docs first. |

Recommended merge order for the next batch: API/release readiness QA, identity
diagnostics, paper/report integration, then paper cycle review surface. Merge
dashboard work last if it touches Preview rendering.

Actual merge order: paper cycle review surface, paper/report integration,
API/release readiness QA, then identity diagnostics. Full tests passed after the
batch merged.

### Next Parallel Batch

The next batch should use `codex/parallel-partial-integration` as its base
after commit `6df047d` or later. Keep these streams paper-first and avoid live
execution work:

| Priority | Workstream | Branch/worktree | Likely files/directories | Acceptance criteria | Conflict risk |
| --- | --- | --- | --- | --- | --- |
| 1 | Paper reconciliation summary | `codex/paper-reconciliation-summary` | `src/isa_system/services/paper_persistence.py`, `src/isa_system/services/operator_report.py`, `src/isa_system/dashboard/pages/preview.py`, tests | Persisted paper cycles expose a clear reconciliation placeholder/summary and operator next action without broker live writes. | Moderate; coordinates report and Preview surfaces. |
| 2 | Official evidence packet diagnostics | `codex/evidence-packet-diagnostics` | `src/isa_system/services/deep_research.py`, `src/isa_system/services/recommendation_handoff.py`, `tests/unit`, docs | Buy/add review context exposes evidence packet freshness/caveats without changing OpenAI or provider fetch semantics. | Moderate; avoid recommendation scoring changes. |
| 3 | Dashboard smoke automation | `codex/dashboard-smoke-readiness` | `src/isa_system/smoke_test.py`, `tests/integration`, `docs/runbook.md` | A repeatable local smoke path verifies Management, Recommendations, Preview, and report/paper endpoints with no live submit authority. | Low; tests/docs first. |
| 4 | Release cut notes | `codex/mvp-release-notes` | `CHANGELOG.md`, `TODO.md`, `docs/README.md`, `docs/agent-coordination.md` | Docs summarize the current MVP surface, known blockers, and exact safe demo flow. | Low; docs-only. |

Recommended merge order for the next batch: dashboard smoke automation, release
cut notes, official evidence packet diagnostics, then paper reconciliation
summary. Merge paper reconciliation last if it touches both report and Preview.

### Exact Execution Prompts

#### Management Diagnostics

```text
You are the Codex execution agent for the Management diagnostics phase 2 workstream.

Read:
- docs/agent-coordination.md
- docs/implementation-roadmap.md
- docs/mvp-gap-analysis.md
- docs/dashboard_layout.md
- src/isa_system/dashboard/pages/management.py
- src/isa_system/dashboard/data.py
- src/isa_system/dashboard/cache_policy.py
- src/isa_system/settings.py

Goal:
Improve the existing read-only Management page so it gives the operator a clearer operational status view: provider readiness, cache freshness, broker read-only status, deep research availability, live guardrails, and the next required safe action.

Constraints:
- Do not add order submission.
- Do not add live arming controls unless they only reflect existing state safely.
- Avoid editing src/isa_system/dashboard/app.py unless navigation is genuinely broken.
- Keep helpers testable and add focused tests.

Acceptance:
- The Management page answers: what is configured, what is stale or missing, what is blocked, and what should the operator do next?
- Preview/live guardrails remain visible.
- Tests pass for any new helper/status logic.
- Add a handoff note to docs/agent-coordination.md.
```

#### Local Onboarding And Pilot Setup

```text
You are the Codex execution agent for the local onboarding and pilot setup workstream.

Read:
- docs/agent-coordination.md
- docs/implementation-roadmap.md
- docs/mvp-gap-analysis.md
- README.md
- .env.example
- docs/runbook.md
- docs/assumptions.md
- docs/README.md

Goal:
Make first-run and pilot setup clear for a local-first operator: install, test, run API/dashboard, configure optional provider keys, connect Trading 212 read-only credentials, understand preview-only defaults, understand why OpenAI/deep research may block buy/add preview approval, and follow a pilot acceptance checklist.

Constraints:
- This is not a SaaS signup/pricing flow.
- Prefer docs-first changes.
- Do not introduce hosted auth, deployment changes, or live trading changes.
- Do not edit dashboard code in this branch unless the docs reveal a broken reference.

Acceptance:
- A new operator can get to a safe preview-only dashboard from the docs.
- The pilot checklist is concrete and auditable.
- Provider setup is clear without exposing or inventing secrets.
- Add a handoff note to docs/agent-coordination.md.
```

#### Recommendation Display UX And Evidence Clarity

```text
You are the Codex execution agent for the recommendation display UX and evidence clarity workstream.

Read:
- docs/agent-coordination.md
- docs/implementation-roadmap.md
- docs/mvp-gap-analysis.md
- src/isa_system/dashboard/pages/recommendations.py
- src/isa_system/dashboard/recommendation_charts.py
- src/isa_system/services/recommendations.py
- src/isa_system/services/recommendation_handoff.py
- tests/unit/test_dashboard_recommendation_queue.py

Goal:
Improve the recommendation review surface so an operator can quickly scan action, blockers, broker validation, research review state, preview eligibility, source caveats, and next step.

Constraints:
- Keep recommendations review-only.
- Do not add order authority.
- Do not change live execution or Management page files.
- Preserve existing service contracts unless a tiny additive field is clearly needed.

Acceptance:
- The dashboard recommendation table/helper output is easier to scan and still exposes blockers.
- Missing evidence and provider caveats remain conservative and visible.
- Focused tests cover any new displayed columns or transforms.
- Add a handoff note to docs/agent-coordination.md.
```

#### Pilot Paper Workflow Shell

```text
You are the Codex execution agent for the pilot paper workflow shell workstream.

Read:
- docs/agent-coordination.md
- docs/implementation-roadmap.md
- docs/mvp-gap-analysis.md
- src/isa_system/services/recommendation_preview.py
- src/isa_system/services/paper_simulation.py
- src/isa_system/dashboard/pages/preview.py
- src/isa_system/api/routers/rebalances.py
- tests/unit/test_paper_simulation.py
- tests/integration/test_mvp_realignment_api.py

Goal:
Add the smallest useful pilot workflow shell after preview: selected recommendation preview rows, paper simulation snapshot, expected-vs-simulated status, warnings, and clear next action. Prefer a schema-light service/API/dashboard shell before persistent paper-cycle migrations.

Constraints:
- Do not add live broker submission.
- Do not change Trading 212 live submit semantics.
- Avoid DB migrations unless absolutely required; if a migration becomes necessary, stop and document the proposed schema first.
- Keep output tolerant of missing broker/provider data.

Acceptance:
- An operator can inspect a pilot paper workflow summary from existing preview/paper data.
- The output makes missing persistence/reconciliation explicit.
- Tests verify preview-to-paper linkage and safe no-live behaviour.
- Add a handoff note to docs/agent-coordination.md.
```

#### MVP QA And Route Guardrails

```text
You are the Codex execution agent for the MVP QA and route guardrails workstream.

Read:
- docs/agent-coordination.md
- docs/implementation-roadmap.md
- docs/mvp-gap-analysis.md
- pyproject.toml
- Makefile
- tests/unit
- tests/integration
- src/isa_system/api
- src/isa_system/dashboard

Goal:
Add focused offline-safe regression tests for MVP guardrails: health, recommendations, handoff, deep research fallback, preview-only sizing, management helpers, SQLite first-run behaviour, and blocked live submit.

Constraints:
- Keep tests fast and deterministic.
- Avoid broad fixture rewrites.
- Do not add new external network dependencies.
- Change production code only for small testability or first-run reliability fixes.

Acceptance:
- New tests protect preview-only semantics and live guardrails.
- Existing tests still pass with `$env:PYTHONPATH='src'; python -m pytest -q`.
- Ruff check and format check pass.
- Add a handoff note to docs/agent-coordination.md.
```

## File Ownership Map

| Area | Primary owner | Avoid touching unless necessary |
| --- | --- | --- |
| Streamlit app shell and primary navigation | UI/UX or Management workstream | Backend service semantics, DB schema |
| `src/isa_system/dashboard/pages/management.py` | Management console | Recommendation scoring, provider clients |
| Recommendation services | Recommendation engine workstream | Dashboard layout beyond needed fields |
| Deep research service and research review routes | Recommendation engine workstream | Provider clients and unrelated dashboard pages |
| Paper simulation and future paper persistence | Pilot workflow | Live broker submit code unless explicitly needed |
| DB models and Alembic migrations | Portfolio/instrument data model | UI pages, unless adding read-only fields |
| Provider adapters | Data/model workstream | Live order execution paths |
| API mode, health, and management status routes | Management console | Scoring algorithms |
| Tests under `tests/unit` and `tests/integration` | Workstream touching the behavior | Broad rewrites of unrelated fixtures |
| Documentation under `docs/` | Documentation workstream; all agents may append handoff notes | Rewriting another active agent's handoff without coordination |

## Shared Decisions

- The app remains local-first and binds to `127.0.0.1` by default.
- MVP execution state is preview-first. Paper is allowed for simulation and
  persistence work. Live remains guarded and disarmed by default.
- Trading 212 is the source of truth for account state, positions, accessible
  instruments, orders, fills, and reconciliation.
- Trading 212 is not treated as a historical OHLC data source.
- Research data comes from external/free providers and official sources, with
  official timestamps winning for point-in-time availability.
- Buy/add preview eligibility requires broker validation and a non-expired
  `RESEARCH_PASSED` review. Sell/trim review can proceed without fresh deep
  research but still needs risk review.
- The 20% algorithmic sleeve is the default planning boundary; no fixed account
  size is assumed.
- UK frictions such as SDRT, PTM levy, FX, spreads, and slippage must remain
  visible in preview/backtest/report paths.
- Streamlit is the existing dashboard framework. Do not introduce React/Vite
  unless a future user explicitly asks for a separate frontend.
- Do not add hosted auth, SaaS signup, or pricing pages for this MVP. Treat
  "onboarding" as local operator setup and pilot readiness.

## Integration Order

1. Documentation and coordination baseline.
2. Management console skeleton, because it clarifies operator controls without
   touching scoring or storage.
3. UI/UX simplification polish that incorporates the Management page.
4. Recommendation evidence improvements that add source freshness and rank
   context.
5. Paper cycle persistence and pilot workflow.
6. Identity mapping schema and official-source enrichment.
7. Report generation and release-note workflow.
8. Auth/permission design, then implementation only with explicit approval.
9. Guarded live-readiness improvements after paper acceptance evidence.

## Blockers / Risks

- No exact ISA account size, benchmark, maximum drawdown, or non-GBP trading
  preference has been specified. Keep controls percentage-based.
- `OPENAI_API_KEY` may be absent; deep research should remain unavailable
  rather than accidentally approving buy/add rows.
- FCA short-disclosure semantics change on 2026-07-13. Parser work must be
  date/version aware.
- Official-source adapters are still starter depth; do not let convenience
  feeds silently become point-in-time truth.
- The current worktree started detached from HEAD; the orchestrator created
  branch `codex/mvp-roadmap-orchestration`.
- `AGENTS.md`, root `TODO.md`, root `CHANGELOG.md`, root `ROADMAP.md`, and
  `package.json` were not present at the start of orchestration.

## Agent Handoff Notes

Each agent should add a dated note here before handoff:

- What it changed
- What remains
- Files touched
- Tests run
- Integration concerns

### 2026-05-11 - Orchestrator

What changed: Created the coordination baseline and converted the deep research
direction into repo-specific roadmap and gap-analysis docs.

What remains: Commit docs, add the first Management console skeleton, run
focused tests, and update this note with implementation details.

Files touched:

- `docs/implementation-roadmap.md`
- `docs/mvp-gap-analysis.md`
- `docs/agent-coordination.md`

Tests run: Pending.

Integration concerns: Management page work should avoid changing live execution
semantics. Keep it read-only in the first slice.

### 2026-05-11 - Orchestrator Management Slice

What changed: Added a read-only Streamlit Management page to surface runtime
mode, live arming, kill switch, broker status, cache window, provider
configuration, and safety checklist. Updated dashboard layout docs to include
Management as a front-stage MVP page. Also fixed zero-config SQLite setup so
file-backed SQLite tests and first-run operation create the missing parent
directory automatically.

What remains: Persist paper cycles, add richer provider freshness diagnostics,
and decide whether a future API management status endpoint is needed.

Files touched:

- `src/isa_system/dashboard/app.py`
- `src/isa_system/dashboard/pages/management.py`
- `src/isa_system/db/session.py`
- `tests/unit/test_dashboard_management.py`
- `tests/unit/test_db.py`
- `docs/dashboard_layout.md`
- `docs/agent-coordination.md`

Tests run:

- `$env:PYTHONPATH='src'; python -m pytest -q`
- `python -m ruff check .`
- `python -m ruff format --check .`
- Browser rendered smoke: `http://127.0.0.1:8501` loaded, Management selected, provider configuration and safety checklist visible.

Integration concerns: The Management page reads local settings and broker
snapshot state only. It does not call mode mutation endpoints or submit orders.

### 2026-05-11 - Orchestrator Parallel Dispatch

What changed: Dispatched five parallel worker agents for Management diagnostics,
local onboarding, recommendation display UX, pilot paper workflow shell, and MVP
QA guardrails. Added root coordination files for future agents.

What remains: Monitor worker outputs, integrate in recommended merge order, and
resolve any handoff-note conflicts in this file.

Files touched:

- `AGENTS.md`
- `TODO.md`
- `CHANGELOG.md`
- `docs/agent-coordination.md`

Tests run: Documentation-only update; `git diff --check` pending before commit.

Integration concerns: Multiple workers may append handoff notes to
`docs/agent-coordination.md`. The orchestrator should reconcile notes during
merge and preserve the latest status table.

### 2026-05-11 - Orchestrator Shared Worktree Recovery

What changed: Paused the first parallel worker batch after detecting that
agents shared the same checkout. Preserved useful partial work in split commits
on `codex/parallel-partial-integration`, then created explicit isolated
worktrees under `C:\Users\DanielCoakley\.codex\worktrees\parallel-t212`.

Commits preserved:

- `6248cca docs: improve local onboarding and pilot checklist`
- `2c3f050 feat: clarify recommendation review display`
- `eb33f30 feat: add notional paper preview simulation`

New isolated workers:

- Tesla: `codex/management-diagnostics`
- Zeno: `codex/mvp-qa-guardrails-2`
- Meitner: `codex/pilot-paper-workflow`

What remains: Monitor the isolated workers, then integrate in this order:
QA guardrails, Management diagnostics, Pilot workflow shell. Reconcile any
handoff notes from isolated branches.

Files touched:

- `.env.example`
- `README.md`
- `docs/README.md`
- `docs/pilot-checklist.md`
- `src/isa_system/dashboard/pages/recommendations.py`
- `src/isa_system/dashboard/recommendation_charts.py`
- `src/isa_system/services/paper_simulation.py`
- `tests/unit/test_dashboard_recommendation_queue.py`
- `tests/unit/test_paper_simulation.py`
- `docs/agent-coordination.md`

Tests run:

- `$env:PYTHONPATH='src'; python -m pytest -q` -> 79 passed
- `python -m ruff check .`
- `python -m ruff format --check .`

Integration concerns: The first worker batch did not complete normal handoff
notes because it was paused. The orchestrator added tests and commits for the
salvaged slices. Continue future parallel work only in explicit worktree
directories.

### 2026-05-11 - Dirac Pilot Paper Workflow

What changed: Added a schema-light pilot paper workflow shell that links
selected recommendation preview rows to the notional paper simulation snapshot,
reports expected-vs-simulated status per row, keeps blocked rows visible, and
states that paper output is not persisted or reconciled. Exposed the shell via a
side-effect-free recommendation workflow API route and rendered it after
preview-only sizing in the Streamlit Preview page.

What remains: Persist paper intents/fills and reconciliation records in a later
schema-scoped slice; add broker quote, lot-size, and actual fill comparison when
paper persistence exists.

Files touched:

- `src/isa_system/services/pilot_workflow.py`
- `src/isa_system/api/routers/rebalances.py`
- `src/isa_system/dashboard/pages/preview.py`
- `tests/unit/test_pilot_workflow.py`
- `tests/integration/test_mvp_realignment_api.py`
- `docs/agent-coordination.md`

Tests run:

- `$env:PYTHONPATH='src'; python -m pytest -q tests/unit/test_paper_simulation.py tests/unit/test_pilot_workflow.py tests/integration/test_mvp_realignment_api.py`
- `$env:PYTHONPATH='src'; python -m pytest -q`
- `python -m ruff check .`
- `python -m ruff format --check .`

Integration concerns: The new route reuses the existing recommendation preview
pipeline and does not submit orders, arm live trading, or add persistence. Merge
with recommendation-display work may need a small Preview page conflict
resolution if both branches edited the post-preview rendering area.

### 2026-05-11 - Tesla Management Diagnostics

What changed: Expanded the read-only Management page into a clearer operational
status surface with provider readiness, cache freshness, broker read-only state,
deep research availability, live guardrail state, and a prioritized next safe
action. Added stale/missing state language without adding controls or order
submission paths.

What remains: Future branches can wire in richer paper-cycle persistence and
official-source freshness once those services exist.

Files touched:

- `src/isa_system/dashboard/pages/management.py`
- `tests/unit/test_dashboard_management.py`
- `docs/dashboard_layout.md`
- `docs/agent-coordination.md`

Tests run:

- `$env:PYTHONPATH='src'; python -m pytest tests/unit/test_dashboard_management.py -q`
- `$env:PYTHONPATH='src'; python -m pytest -q`
- `python -m ruff check .`
- `python -m ruff format --check .`

Integration concerns: This branch only reads local settings and broker snapshot
state. It does not mutate runtime mode, live arming, kill switch state, or
recommendation/pilot workflows.

### 2026-05-11 - MVP QA Guardrails

What changed: Added focused offline regression coverage for preview-first MVP
guardrails across health status, recommendation handoff gating, deep research
fallback, preview-only recommendation sizing, management helper safety rows,
SQLite first-run setup, blocked live submit, and dashboard review tables that
must not imply order authority.

What remains: Broaden route coverage after the management diagnostics,
recommendation display, and pilot paper workflow branches land; feature-specific
assertions should travel with those branches if their contracts change.

Files touched:

- `tests/integration/test_mvp_guardrails.py`
- `tests/unit/test_mvp_guardrail_helpers.py`
- `docs/agent-coordination.md`

Tests run:

- `$env:PYTHONPATH='src'; python -m pytest -q tests/integration/test_mvp_guardrails.py tests/unit/test_mvp_guardrail_helpers.py`
- `$env:PYTHONPATH='src'; python -m pytest -q`
- `python -m ruff check .`
- `python -m ruff format --check .`

Integration concerns: The tests monkeypatch broker, market-data, and OpenAI
seams to remain deterministic and offline. They assert existing preview-only
semantics and do not add live order submission paths.

### 2026-05-11 - Orchestrator Browser Smoke

What changed: Started a fresh Streamlit server from
`codex/parallel-partial-integration` on `http://127.0.0.1:8502/` and checked
the integrated cockpit in the in-app browser.

What remains: Repeat browser smoke after the second worker batch merges,
especially if dashboard page files conflict during integration.

Files touched:

- `docs/agent-coordination.md`

Checks run:

- Browser smoke: Overview, Management, Preview, and Recommendations rendered
  without visible Streamlit exceptions.
- Verified Management shows read-only operational status sections.
- Verified Preview keeps review-only/no-eligible-row messaging visible.
- Verified Recommendations keeps review-only/source/status messaging visible.

Integration concerns: The browser smoke used a separate local server on port
8502 to avoid disturbing the user's existing `8501` app session.

### 2026-05-11 - Source Freshness Diagnostics

What changed: Added shared dashboard cache/source age helpers, explicit age
labels on Management cache freshness rows, provider source caveats, and a
Recommendation Source Freshness diagnostic table. The consolidated
recommendation queue can now show source freshness, source age, cache context,
and stale/provider-gap caveats while preserving review-only language.

What remains: Future official-source ingestion should add real per-evidence
`available_at_utc` coverage once those services exist; this slice only displays
freshness from existing cache, broker snapshot, recommendation, validation, and
handoff timestamps.

Files touched:

- `src/isa_system/dashboard/cache_policy.py`
- `src/isa_system/dashboard/pages/management.py`
- `src/isa_system/dashboard/pages/recommendations.py`
- `src/isa_system/dashboard/recommendation_charts.py`
- `tests/unit/test_dashboard_cache_policy.py`
- `tests/unit/test_dashboard_management.py`
- `tests/unit/test_dashboard_recommendation_queue.py`
- `docs/agent-coordination.md`

Tests run:

- `$env:PYTHONPATH='src'; python -m pytest -q tests/unit/test_dashboard_cache_policy.py tests/unit/test_dashboard_management.py tests/unit/test_dashboard_recommendation_queue.py`
- `$env:PYTHONPATH='src'; python -m pytest -q`
- `python -m ruff check .`
- `python -m ruff format --check .`

Integration concerns: Dashboard-only display changes; no recommendation scoring,
provider fetch semantics, broker submission, live arming, mode mutation, or DB
schema changes were made. Recommendation rows remain review/preview context, not
order authority.

### 2026-05-11 - Operator Report Shell

What changed: Added a side-effect-free operator report shell service that
aggregates available account, recommendation, research, preview, pilot-paper,
and management evidence into JSON plus a Markdown-ready summary. Missing,
stale, blocked, unavailable, and not-persisted sections are labelled explicitly.
Added a read-only `/operator-report` route that builds the report from existing
MVP services and only creates preview/paper sections when symbols are supplied.

What remains: Persist paper cycles and reconciliation before treating paper
evidence as durable. A future dashboard/export surface can consume the service
without changing broker execution semantics.

Files touched:

- `src/isa_system/services/operator_report.py`
- `src/isa_system/api/routers/operator_report.py`
- `src/isa_system/api/main.py`
- `tests/unit/test_operator_report.py`
- `tests/integration/test_operator_report_api.py`
- `docs/agent-coordination.md`

Tests run:

- `$env:PYTHONPATH='src'; python -m pytest -q tests/unit/test_operator_report.py tests/integration/test_operator_report_api.py`
- `$env:PYTHONPATH='src'; python -m pytest -q tests/integration/test_mvp_realignment_api.py`
- `$env:PYTHONPATH='src'; python -m pytest -q`
- `python -m ruff check .`
- `python -m ruff format --check .`

Integration concerns: The route reuses read-only broker, recommendation,
validation, research-review, preview, and pilot workflow services. It does not
submit broker orders, arm live trading, persist paper output, or add migrations.
The report's paper section intentionally reports persistence and reconciliation
as missing until the paper persistence workstream lands.

### 2026-05-11 - Paper Intent Persistence

What changed: Added a durable paper-cycle persistence slice for selected
recommendation preview rows. The existing side-effect-free pilot workflow is
unchanged; a new explicit save route persists deterministic paper cycle IDs,
paper intent rows, simulated fill rows, expected-vs-simulated status, and fill
source-kind evidence for notional, quantity, and fill price. A reload route can
fetch the persisted cycle by ID.

What remains: Full broker quote/lot-size paper execution and broker
reconciliation are still not implemented. Recommendation and Preview dashboard
surfaces are not changed in this slice, so displaying persisted cycles remains
future work.

Files touched:

- `src/isa_system/db/models.py`
- `src/isa_system/db/migrations/versions/0003_paper_cycles.py`
- `src/isa_system/services/paper_persistence.py`
- `src/isa_system/api/routers/rebalances.py`
- `tests/unit/test_paper_persistence.py`
- `tests/integration/test_mvp_realignment_api.py`
- `docs/agent-coordination.md`

Tests run:

- `$env:PYTHONPATH='src'; python -m pytest -q tests/unit/test_paper_simulation.py tests/unit/test_pilot_workflow.py tests/unit/test_paper_persistence.py tests/integration/test_mvp_realignment_api.py`
- `$env:PYTHONPATH='src'; python -m pytest -q`
- `python -m ruff check .`
- `python -m ruff format --check .`

Migration impact: Adds three operational SQLite/Postgres-compatible tables:
`paper_cycles`, `paper_intents`, and `paper_simulated_fills`, plus lookup
indexes by preview/simulation hash, cycle ID, intent ID, and research symbol.
No existing table is altered and no live execution table or broker submit path
is changed.

Integration concerns: Merge this after branches that also touch
`rebalances.py` or paper workflow tests. The new persistence route is an
explicit side-effecting endpoint; `/rebalances/from-recommendations/preview` and
`/rebalances/from-recommendations/pilot-workflow` remain preview-only and
side-effect free.

### 2026-05-11 - Orchestrator Second Batch Integration

What changed: Integrated the second isolated worker batch into
`codex/parallel-partial-integration`: source freshness diagnostics, paper intent
persistence, and operator report shell. Updated roadmap, gap analysis, TODO, and
changelog to reflect the new MVP baseline.

What remains: The report shell landed independently of paper persistence, so the
next small slice should connect operator reports to a supplied persisted paper
cycle. Preview/dashboard should also gain a simple paper-cycle review surface.

Files touched:

- `CHANGELOG.md`
- `TODO.md`
- `docs/agent-coordination.md`
- `docs/implementation-roadmap.md`
- `docs/mvp-gap-analysis.md`

Checks run:

- `$env:PYTHONPATH='src'; python -m pytest -q` -> 105 passed
- `python -m ruff check .`
- `python -m ruff format --check .`
- Browser smoke on `http://127.0.0.1:8502/`: Management and Recommendations
  rendered without visible Streamlit exceptions after source freshness changes.

Integration concerns: The second batch added a DB migration plus a new report
router. Run a full integration pass after any branch touches the report/paper
service boundary or Preview page rendering.

### 2026-05-11 - Paper Cycle Review Surface

What changed: Added a small Preview-page saved paper-cycle review surface.
Operators can paste a persisted cycle ID, reload local paper evidence, and see
cycle ID, persistence status, selected/eligible/fill counts, expected and
simulated totals, warnings, intent/fill evidence, and explicit unreconciled
status. The active pilot paper workflow now also shows reconciliation status and
save/reload endpoint guidance when the workflow has not been persisted.

What remains: Full broker reconciliation, quote/lot-size paper execution, and
report integration for supplied persisted cycles remain separate workstreams.

Files touched:

- `src/isa_system/dashboard/pages/preview.py`
- `tests/unit/test_dashboard_preview.py`
- `docs/agent-coordination.md`

Tests run:

- `$env:PYTHONPATH='src'; python -m pytest -q tests/unit/test_dashboard_preview.py tests/unit/test_pilot_workflow.py tests/unit/test_paper_persistence.py tests/integration/test_mvp_realignment_api.py`
- `$env:PYTHONPATH='src'; python -m pytest -q`
- `python -m ruff check .`
- `python -m ruff format --check .`

Integration concerns: The Preview page now imports the paper persistence read
service and loads cycles only by operator-supplied ID. No live Trading 212
POST/order submission path, runtime arming, DB schema, or recommendation
service semantics changed.

### 2026-05-11 - Identity Diagnostics

What changed: Added additive identity diagnostics to broker instrument
validation and recommendation review helpers. Validation rows now expose
confidence and caveats for broker ticker/research symbol/ISIN matching, handoff
rows carry the same identity context, and dashboard helper frames include
identity confidence, ISIN, candidate broker tickers, and mismatch caveats
without changing preview eligibility semantics.

What remains: A later schema-scoped identity mapping slice can persist manual
overrides, LEI/company-number links, and official-source issuer identity once
that migration is approved.

Files touched:

- `src/isa_system/services/instrument_validation.py`
- `src/isa_system/services/recommendation_handoff.py`
- `src/isa_system/dashboard/recommendation_charts.py`
- `tests/unit/test_instrument_validation.py`
- `tests/unit/test_recommendation_handoff.py`
- `tests/unit/test_dashboard_recommendation_queue.py`
- `docs/agent-coordination.md`

Tests run:

- `$env:PYTHONPATH='src'; python -m pytest -q tests/unit/test_instrument_validation.py tests/unit/test_recommendation_handoff.py tests/unit/test_dashboard_recommendation_queue.py tests/unit/test_mvp_guardrail_helpers.py`
- `$env:PYTHONPATH='src'; python -m pytest -q`
- `python -m ruff check .`
- `python -m ruff format --check .`

Integration concerns: The change is additive to existing Pydantic response
models and does not add DB migrations, order submission, live arming, or new
broker write paths. Broker validation statuses remain the gating source; the
new confidence and caveat fields are diagnostics only.

### 2026-05-11 - Paper/report integration

What changed: Connected the operator report shell to supplied persisted paper
cycles. Reports can now include a loaded paper-cycle ID, persistence status,
intent/fill counts, expected/simulated totals, and persisted intent records
while still distinguishing simulated-only paper workflow evidence. Missing
paper reconciliation remains explicit.

What remains: Broker reconciliation remains future work. Reports can surface
persisted cycle evidence but do not make it reconciled or live-executable.

Files touched:

- `src/isa_system/services/operator_report.py`
- `src/isa_system/api/routers/operator_report.py`
- `tests/unit/test_operator_report.py`
- `tests/integration/test_operator_report_api.py`
- `docs/agent-coordination.md`

Tests run:

- `$env:PYTHONPATH='src'; python -m pytest -q tests/unit/test_operator_report.py tests/integration/test_operator_report_api.py tests/unit/test_paper_persistence.py`
- `$env:PYTHONPATH='src'; python -m pytest -q tests/integration/test_mvp_realignment_api.py`
- `$env:PYTHONPATH='src'; python -m pytest -q tests/unit/test_operator_report.py tests/integration/test_operator_report_api.py tests/unit/test_paper_persistence.py tests/integration/test_mvp_realignment_api.py`
- `$env:PYTHONPATH='src'; python -m pytest -q`
- `python -m ruff check .`
- `python -m ruff format --check .`

Integration concerns: The report route only loads a requested persisted cycle;
it does not persist paper output or mutate preview/pilot workflow endpoints.
If a report is built with a stale or mismatched simulated workflow plus a
persisted cycle, the paper section now warns and needs operator attention.

### 2026-05-11 - API Release Readiness QA

What changed: Added focused offline release-readiness checks around the newly
integrated report and paper-cycle API surface. The checks keep the report and
paper-cycle routes discoverable in OpenAPI, cover missing paper-cycle reloads,
verify report/paper-cycle calls do not arm or authorize live submit, and make
the `0003_paper_cycles` migration discoverable through Alembic with audited
table/index/downgrade shape.

What remains: Broker reconciliation remains a follow-up workstream. The report
and Preview surfaces can now inspect persisted paper cycles, but they still do
not turn simulated paper evidence into live execution authority.

Files touched:

- `tests/integration/test_api_release_readiness.py`
- `tests/unit/test_migration_readiness.py`
- `CHANGELOG.md`
- `TODO.md`
- `docs/agent-coordination.md`

Tests run:

- `$env:PYTHONPATH='src'; python -m pytest -q tests/integration/test_api_release_readiness.py`
- `$env:PYTHONPATH='src'; python -m pytest -q tests/unit/test_migration_readiness.py`
- `$env:PYTHONPATH='src'; python -m pytest -q tests/integration/test_api_release_readiness.py tests/integration/test_operator_report_api.py tests/integration/test_mvp_realignment_api.py tests/integration/test_mvp_guardrails.py tests/unit/test_migration_readiness.py`
- `$env:PYTHONPATH='src'; python -m pytest -q`
- `python -m ruff check .`
- `python -m ruff format --check .`

Integration concerns: The new tests monkeypatch provider/broker dependencies
and use temporary SQLite files, so they stay offline and should not conflict
with report/paper implementation branches. Future migrations may extend the
Alembic chain, but `0003_paper_cycles` should remain discoverable by revision
ID.

### 2026-05-11 - Portfolio Intelligence Phase 0 Bootstrap

What changed: Started the requested portfolio intelligence build by adapting
the existing `isa_system` package as the single implementation home. Added
planning/status docs, OpenBB and port-8002 settings, example YAML configs,
OpenBB keyless check script, unified API runner, placeholder phase scripts, and
an OpenBB-independent health contract that keeps live trading marked as not
implemented.

What remains: Phase 1 should add Finviz discovery, local HTML caching, parser
fixtures, candidate deduplication, and discovery/candidate API routes. Existing
live execution scaffolding remains guarded legacy MVP code and must not be
expanded for this workflow.

Files touched:

- `.env.example`
- `Makefile`
- `README.md`
- `pyproject.toml`
- `configs/*.yaml`
- `docs/acceptance_checklist.md`
- `docs/implementation_plan.md`
- `docs/implementation_status.md`
- `scripts/check_openbb.py`
- `scripts/run_api.py`
- `scripts/run_discovery.py`
- `scripts/run_top10_research.py`
- `scripts/run_portfolio_review.py`
- `scripts/smoke_test.py`
- `src/isa_system/api/main.py`
- `src/isa_system/api/routers/health.py`
- `src/isa_system/constants.py`
- `src/isa_system/settings.py`
- `tests/integration/test_portfolio_phase0_api.py`

Tests run:

- `$env:PYTHONPATH='src'; python -m pytest -q` -> 116 passed
- `python -m ruff check .`
- `python -m ruff format --check .`

Integration concerns: A direct port smoke on `127.0.0.1:8002` found an
existing listener, so the agent did not stop or replace it. Clear that process
before manual API smoke with `python scripts/run_api.py`.

### 2026-05-11 - Portfolio Intelligence Phase 1 Finviz Discovery

What changed: Added a Finviz discovery package inside `isa_system` with curated
screener YAML loading, polite cached fetching, blocked/empty page handling,
fixture parser tests, symbol-level deduplication, source screener preservation,
multi-screener boost, discovery/candidate API routes, and an offline discovery
CLI.

What remains: Phase 2 should add OpenBB enrichment with centralised route
definitions and graceful unavailable-route behaviour. Live Finviz usage remains
operator-triggered and conservative.

Files touched:

- `configs/finviz_screeners.yaml`
- `scripts/run_discovery.py`
- `src/isa_system/api/main.py`
- `src/isa_system/api/routers/candidates.py`
- `src/isa_system/api/routers/discovery.py`
- `src/isa_system/discovery/*`
- `tests/fixtures/finviz_*.html`
- `tests/integration/test_discovery_api.py`
- `tests/unit/test_candidate_intake.py`
- `tests/unit/test_finviz_parser.py`
- `docs/acceptance_checklist.md`
- `docs/implementation_status.md`
- `docs/agent-coordination.md`

Tests run:

- `$env:PYTHONPATH='src'; python -m pytest -q` -> 121 passed
- `python -m ruff check .`
- `python -m ruff format --check .`
- `$env:PYTHONPATH='src'; python scripts/run_discovery.py --fixtures`

Integration concerns: The latest discovery result is process-local for now.
Persistence can be added when score snapshots/thesis records are introduced.

### 2026-05-11 - Portfolio Intelligence Phase 2 OpenBB Enrichment

What changed: Added an OpenBB enrichment package inside `isa_system` with
centralised endpoint definitions, a configurable cached client, health checks,
candidate enrichment packets, fixture-only offline enrichment, price/fundamental
fixtures, data quality scoring, missing-section explanations, and enrichment
API routes.

What remains: Phase 3 should consume enrichment packets for factor scoring,
ranking, and top 10 selection. The exact OpenBB route paths remain isolated in
`src/isa_system/enrichment/openbb_endpoints.py` until validated against the
local OpenBB install.

Files touched:

- `src/isa_system/api/main.py`
- `src/isa_system/api/routers/enrichment.py`
- `src/isa_system/enrichment/*`
- `tests/fixtures/openbb_*.json`
- `tests/integration/test_enrichment_api.py`
- `tests/unit/test_openbb_enrichment.py`
- `docs/acceptance_checklist.md`
- `docs/implementation_status.md`
- `docs/agent-coordination.md`

Tests run:

- `$env:PYTHONPATH='src'; python -m pytest -q` -> 127 passed
- `python -m ruff check .`
- `python -m ruff format --check .`

Integration concerns: Fixture enrichment does not call OpenBB for missing
sections. Live route availability should be treated as uncertain and corrected
only in `openbb_endpoints.py`.

### 2026-05-11 - Portfolio Intelligence Phase 3 Scoring

What changed: Added deterministic opportunity scoring inside `isa_system` with
factor weights, factor score models, composite score snapshots, top 10 ranking,
missing/stale data penalties, multi-screener boosts, explanations, and score
API routes.

What remains: Phase 4 should turn top candidates into persistent thesis records
with BUY/WATCHLIST/REJECT decision rules. The scoring formulas are intentionally
conservative placeholders until richer OpenBB and official-source fields are
validated.

Files touched:

- `src/isa_system/api/main.py`
- `src/isa_system/api/routers/scores.py`
- `src/isa_system/scoring/*`
- `tests/integration/test_scores_api.py`
- `tests/unit/test_scoring.py`
- `docs/acceptance_checklist.md`
- `docs/implementation_status.md`
- `docs/agent-coordination.md`

Tests run:

- `$env:PYTHONPATH='src'; python -m pytest -q` -> 133 passed
- `python -m ruff check .`
- `python -m ruff format --check .`

Integration concerns: Score state is process-local and should become durable
when thesis/report persistence is added.

### 2026-05-11 - Portfolio Intelligence Phase 4 Thesis Engine

What changed: Added persistent investment thesis tracking with statuses,
decision labels, deterministic thesis generation, decision rules, SQLite-backed
thesis records, an Alembic migration, lifecycle helpers, and thesis API routes.
The generator avoids fabricating target or entry levels when current price data
is unavailable.

What remains: Phase 5 should generate structured research reports and update
thesis fields from report output. Phase 6 should provide the real
portfolio-improves input for BUY_NOW candidates.

Files touched:

- `src/isa_system/api/main.py`
- `src/isa_system/api/routers/thesis.py`
- `src/isa_system/db/models.py`
- `src/isa_system/db/migrations/versions/0004_investment_theses.py`
- `src/isa_system/thesis/*`
- `tests/integration/test_thesis_api.py`
- `tests/unit/test_thesis.py`
- `docs/acceptance_checklist.md`
- `docs/implementation_status.md`
- `docs/agent-coordination.md`

Tests run:

- `$env:PYTHONPATH='src'; python -m pytest -q` -> 141 passed
- `python -m ruff check .`
- `python -m ruff format --check .`

Integration concerns: BUY_NOW is a thesis/research label only. No broker order
submission or live execution path was added.

### 2026-05-11 - Portfolio Intelligence Phase 5 Research Reports

What changed: Added structured research report generation and persistence with
Markdown artifacts, SQLite report records, a source-bounded prompt builder,
deterministic no-key memo output, thesis updates from reports, and research API
routes including top-10 report generation.

What remains: Optional OpenAI memo generation is not executed yet; the prompt
builder is ready for a later explicit integration. Phase 6 should add portfolio
comparison and rebalance proposal logic.

Files touched:

- `src/isa_system/api/main.py`
- `src/isa_system/api/routers/research_reports.py`
- `src/isa_system/db/models.py`
- `src/isa_system/db/migrations/versions/0005_research_reports.py`
- `src/isa_system/reports/*`
- `tests/integration/test_research_reports_api.py`
- `tests/unit/test_reports.py`
- `docs/acceptance_checklist.md`
- `docs/implementation_status.md`
- `docs/agent-coordination.md`

Tests run:

- `$env:PYTHONPATH='src'; python -m pytest -q` -> 145 passed
- `python -m ruff check .`
- `python -m ruff format --check .`

Integration concerns: Reports remain research artifacts only and do not create
order authority.

### 2026-05-11 - Portfolio Intelligence Phase 6 Portfolio Manager

What changed: Added holdings models, risk constraints, sleeve defaults,
rationale-based rebalance proposal models, portfolio comparison logic, manual
approval flags, no-churn safeguards, material-superiority replacement logic,
cooldown blocking, broken/target-reached holding proposals, and portfolio
manager API routes.

What remains: Phase 7 should add Trading 212 read-only/order-preview support
and remove or neutralize the legacy submit route so the unified system exposes
no live order submission endpoint.

Files touched:

- `src/isa_system/api/main.py`
- `src/isa_system/api/routers/portfolio_manager.py`
- `src/isa_system/portfolio/holdings.py`
- `src/isa_system/portfolio/risk.py`
- `src/isa_system/portfolio/sleeve.py`
- `src/isa_system/portfolio/proposal_models.py`
- `src/isa_system/portfolio/comparison.py`
- `src/isa_system/portfolio/rebalance.py`
- `tests/integration/test_portfolio_manager_api.py`
- `tests/unit/test_portfolio_manager.py`
- `docs/acceptance_checklist.md`
- `docs/implementation_status.md`
- `docs/agent-coordination.md`

Tests run:

- `$env:PYTHONPATH='src'; python -m pytest -q` -> 153 passed
- `python -m ruff check .`
- `python -m ruff format --check .`

Integration concerns: Portfolio manager proposals are review-only and always
carry `manual_approval_required=true`.

### 2026-05-11 - Portfolio Intelligence Phase 7 Trading 212 Safety

What changed: Added Trading 212 read-only/order-preview package, broker account
and positions routes, local order preview route, deterministic duplicate hash
logic, manual approval warnings, and tests. Removed the legacy
`/rebalances/submit` route from the unified API surface and disabled legacy
Trading 212 provider submit methods with `NotImplementedError`.

What remains: Phase 8 should expose outputs as OpenBB Workspace-friendly widget
metadata. Any future live execution is separate work and must go through a new
safety review.

Files touched:

- `src/isa_system/api/main.py`
- `src/isa_system/api/routers/broker.py`
- `src/isa_system/api/routers/rebalances.py`
- `src/isa_system/data/providers/trading212.py`
- `src/isa_system/trading212/*`
- `tests/integration/test_api.py`
- `tests/integration/test_api_release_readiness.py`
- `tests/integration/test_broker_api.py`
- `tests/integration/test_mvp_guardrails.py`
- `tests/unit/test_trading212_preview.py`
- `docs/acceptance_checklist.md`
- `docs/implementation_status.md`
- `docs/agent-coordination.md`

Tests run:

- `$env:PYTHONPATH='src'; python -m pytest -q` -> 159 passed
- `python -m ruff check .`
- `python -m ruff format --check .`

Integration concerns: `/rebalances/submit` now returns 404. Existing callers
must use `/orders/preview` for local preview only.

### 2026-05-11 - Portfolio Intelligence Phase 8 Workspace Metadata

What changed: Added OpenBB Workspace-style widget metadata, a
`/workspace/widgets.json` route, risk-warning endpoint, and tests that all
advertised widget target endpoints are registered and work without OpenBB.

What remains: Phase 9 should add end-to-end orchestration and offline smoke
artifacts. Exact OpenBB Workspace custom backend details may require small
metadata adjustments later.

Files touched:

- `src/isa_system/api/main.py`
- `src/isa_system/api/routers/workspace.py`
- `src/isa_system/workspace/*`
- `tests/integration/test_workspace_api.py`
- `docs/acceptance_checklist.md`
- `docs/implementation_status.md`
- `docs/agent-coordination.md`

Tests run:

- `$env:PYTHONPATH='src'; python -m pytest -q` -> 161 passed
- `python -m ruff check .`
- `python -m ruff format --check .`

Integration concerns: No custom frontend was added; this is backend metadata
only.

### 2026-05-11 - Portfolio Intelligence Phase 9 Orchestration

What changed: Added the full fixture-backed orchestrator flow, orchestrator API
routes, full-pipeline script, smoke script, run summary model, and smoke
artifacts for candidates, top 10, research reports, watchlist, rebalance
proposals, order previews, and run summary.

What remains: Phase 10 should complete the documentation set and final
hardening checks.

Files touched:

- `src/isa_system/api/main.py`
- `src/isa_system/api/routers/orchestrator.py`
- `src/isa_system/orchestrator.py`
- `scripts/run_full_pipeline.py`
- `scripts/smoke_test.py`
- `tests/integration/test_orchestrator.py`
- `docs/acceptance_checklist.md`
- `docs/implementation_status.md`
- `docs/agent-coordination.md`

Tests run:

- `$env:PYTHONPATH='src'; python scripts/smoke_test.py`
- `$env:PYTHONPATH='src'; python -m pytest -q` -> 163 passed
- `python -m ruff check .`
- `python -m ruff format --check .`

Integration concerns: The orchestrator writes local artifacts and never submits
broker orders. Generated order previews are local/manual-review only.

### 2026-05-11 - Portfolio Intelligence Phase 10 Docs And Hardening

What changed: Added the required documentation set for architecture, workflow,
OpenBB, Finviz, scoring, thesis lifecycle, decision rules, portfolio manager,
Trading 212 safety, Workspace integration, runbook, and roadmap. Final smoke,
test, lint, format, and mypy checks were run.

What remains: Validate provider endpoint paths against local OpenBB and Trading
212 demo credentials. Legacy mypy warnings remain in older MVP modules and are
documented in `docs/implementation_status.md`.

Tests run:

- `$env:PYTHONPATH='src'; python -m pytest -q` -> 163 passed
- `python -m ruff check .`
- `python -m ruff format --check .`
- `$env:PYTHONPATH='src'; python scripts/smoke_test.py`
- `$env:PYTHONPATH='src'; python -m mypy` -> 25 documented legacy warnings

Integration concerns: Live Trading 212 submission is not implemented and
`/rebalances/submit` returns 404.

### 2026-05-12 - Holdings Health Check

What changed: Added an on-demand health report workflow for current holdings.
The report uses the configured OpenAI health model when `OPENAI_API_KEY` is
available, defaults to `o3-deep-research`, and falls back to conservative local
scenario targets when no key is configured. Report runs are persisted in SQLite,
and operator accepted/adjusted bear/base/bull targets plus carried-forward
actions are stored in a separate history table.

What remains: Decide whether accepted health-check targets should update thesis
records directly or remain as a separate overlay. Validate real deep-research
latency/model access with the operator's OpenAI account.

Files touched:

- `.env.example`
- `README.md`
- `docs/runbook.md`
- `docs/implementation_status.md`
- `docs/agent-coordination.md`
- `src/isa_system/settings.py`
- `src/isa_system/db/models.py`
- `src/isa_system/db/migrations/versions/0006_holding_health_reports.py`
- `src/isa_system/services/holding_health.py`
- `src/isa_system/api/main.py`
- `src/isa_system/api/routers/holding_health.py`
- `src/isa_system/dashboard/app.py`
- `src/isa_system/dashboard/pages/health_check.py`
- `tests/unit/test_holding_health.py`
- `tests/unit/test_dashboard_health_check.py`
- `tests/integration/test_holding_health_api.py`
- `tests/unit/test_migration_readiness.py`

Tests run:

- `$env:PYTHONPATH='src'; python -m pytest -q tests/unit/test_holding_health.py tests/unit/test_dashboard_health_check.py tests/integration/test_holding_health_api.py tests/unit/test_migration_readiness.py`
- `python -m ruff check src/isa_system/services/holding_health.py src/isa_system/dashboard/pages/health_check.py src/isa_system/api/routers/holding_health.py src/isa_system/settings.py src/isa_system/db/models.py src/isa_system/api/main.py tests/unit/test_holding_health.py tests/unit/test_dashboard_health_check.py tests/integration/test_holding_health_api.py tests/unit/test_migration_readiness.py`
- `$env:PYTHONPATH='src'; python -m pytest -q` -> 170 passed
- `python -m ruff check .`
- `python -m ruff format --check .`
- `$env:PYTHONPATH='src'; python -m mypy` -> unchanged 25 legacy warnings in
  pre-existing modules

Integration concerns: No broker write route, live order submission, live arming
control, or Trading 212 POST path was added. The Health Check page carries
forward review state only.

### 2026-05-12 - Command Centre Finviz Screener Page

What changed: Converted the new FastAPI-served command centre nav to only show
Overview and the first real feature page, Finviz Screener. Added a configurable
Finviz screener workbench with preset loading, curated Finviz filter capability
toggles, raw filter-code entry, dynamic Finviz URL generation, fixture/live run
actions, full filtered-table rendering, principal valuation column toggles, and
per-row Finviz profile links.

What remains: Validate live Finviz table shape against current site output over
several real screener runs and add pagination support if the operator wants
more than the first returned page.

Files touched:

- `src/isa_system/api/routers/discovery.py`
- `src/isa_system/discovery/finviz_custom.py`
- `src/isa_system/discovery/finviz_parser.py`
- `src/isa_system/discovery/candidate_intake.py`
- `src/isa_system/discovery/models.py`
- `src/isa_system/web/index.html`
- `src/isa_system/web/app.js`
- `src/isa_system/web/styles.css`
- `tests/unit/test_finviz_parser.py`
- `tests/integration/test_discovery_api.py`
- `tests/integration/test_command_center_ui.py`
- `docs/agent-coordination.md`
- `docs/implementation_status.md`

Tests run:

- `$env:PYTHONPATH='src'; python -m pytest -q tests/unit/test_finviz_parser.py tests/integration/test_discovery_api.py tests/integration/test_command_center_ui.py` -> 8 passed.
- `$env:PYTHONPATH='src'; python -m pytest -q` -> 175 passed.
- `python -m ruff check .`
- `python -m ruff format --check .`

Integration concerns: The configurable screener updates the process-local
latest discovery result for downstream scoring. Finviz remains operator-run,
cached, polite, and safely non-critical if blocked or layout changes.

### 2026-05-12 - Finviz-Like Screener Controls

What changed: Reworked the command centre screener page to mirror the main
Finviz screener interaction more closely. The page now has a compact top bar
with preset, order-by, direction, signal, ticker input, run, collapsible
filters, and icon-only external Finviz links. Filter tuning is dropdown-based
and grouped under Descriptive, Fundamental, and Technical tabs. Column selection
is category-grouped, supports adding custom column labels, and selected columns
now appear even when a particular response has blank values. Table headers sort
client-side by any visible column.

What remains: Continue validating live Finviz response columns across different
views and add pagination if the operator wants broader capture than the first
returned page.

Files touched:

- `src/isa_system/discovery/finviz_custom.py`
- `src/isa_system/web/index.html`
- `src/isa_system/web/app.js`
- `src/isa_system/web/styles.css`
- `tests/integration/test_discovery_api.py`
- `tests/integration/test_command_center_ui.py`
- `docs/agent-coordination.md`
- `docs/implementation_status.md`

Tests run:

- `$env:PYTHONPATH='src'; python -m pytest -q tests/integration/test_discovery_api.py tests/integration/test_command_center_ui.py tests/unit/test_finviz_parser.py` -> 8 passed.
- `$env:PYTHONPATH='src'; python -m pytest -q` -> 175 passed.
- `python -m ruff check .`
- `python -m ruff format --check .`

Integration concerns: Preset changes trigger a fresh operator-visible Finviz
run. Other filter dropdown changes update the pending settings and require the
Run button, avoiding rapid repeated scrape requests while tuning controls.

### 2026-05-12 - Command Centre Screener Refinement

What changed: Revised the Finviz screener page back to the command-centre
visual language while keeping presets and a collapsible, category-split filter
drawer. Expanded the exposed dropdown choices for the main descriptive,
fundamental, and technical controls, restored the lighter results-table style,
kept dynamic/sortable columns, and added local persistence for operator-saved
custom screener presets.

What remains: Validate edge-case Finviz filter codes against live pages and add
pagination if first-page capture is too narrow for the operator workflow.

Files touched:

- `src/isa_system/api/routers/discovery.py`
- `src/isa_system/discovery/finviz_custom.py`
- `src/isa_system/web/index.html`
- `src/isa_system/web/app.js`
- `src/isa_system/web/styles.css`
- `tests/integration/test_discovery_api.py`
- `docs/agent-coordination.md`
- `docs/implementation_status.md`

Tests run:

- `$env:PYTHONPATH='src'; python -m pytest tests/integration/test_discovery_api.py tests/integration/test_command_center_ui.py -q` -> 6 passed.
- `$env:PYTHONPATH='src'; python -m pytest -q` -> 176 passed.
- `python -m ruff check .`
- `node --check src/isa_system/web/app.js`
- `$env:PYTHONPATH='src'; python -m mypy` -> unchanged 25 legacy errors in
  recommendation handoff, pilot workflow, paper persistence, and operator
  report modules.
- Browser/IAB QA on `http://localhost:8501/#screener` for filter expansion,
  saved custom presets, fixture results, dynamic RSI column, and table sorting.

Integration concerns: Saved presets are stored in local artifacts only; no
broker write path, live order submission, or unattended trading path was added.

### 2026-05-12 - Screener Table Data Alignment

What changed: Fixed Finviz table parsing so the filter form is no longer used
as the results header source. The parser now scopes to `screener_table`, handles
Finviz's omitted header `</tr>`, maps valuation fields to the correct columns,
and extracts embedded company, industry, and country metadata. The command
centre table now shows Company and Industry by default, uses tighter column
widths, and applies first-pass sector-aware good/neutral/bad colour coding.

What remains: Calibrate colour bands by sector/theme after more live examples
are reviewed. Consider moving the heuristic thresholds into configuration if
the operator wants to tune them without code changes.

Files touched:

- `src/isa_system/discovery/finviz_parser.py`
- `src/isa_system/web/index.html`
- `src/isa_system/web/app.js`
- `src/isa_system/web/styles.css`
- `tests/fixtures/finviz_elite_garp.html`
- `tests/unit/test_finviz_parser.py`
- `docs/agent-coordination.md`
- `docs/implementation_status.md`

Tests run:

- `$env:PYTHONPATH='src'; python -m pytest tests/unit/test_finviz_parser.py tests/integration/test_discovery_api.py tests/integration/test_command_center_ui.py -q` -> 10 passed.
- `$env:PYTHONPATH='src'; python -m pytest -q` -> 177 passed.
- `python -m ruff check .`
- `node --check src/isa_system/web/app.js`
- `$env:PYTHONPATH='src'; python -m mypy` -> unchanged 25 legacy errors.
- Browser/IAB QA on `http://localhost:8501/#screener` confirmed company,
  industry, P/E, forward P/E, EPS, volume, and coloured metric rendering.

Integration concerns: No live trading or broker write path was touched.

### 2026-05-12 - Screener Review Cleanup

What changed: Applied browser review feedback for the screener page. The nav
label now reads `Screener`, the old page heading/eyebrow/help copy is removed,
the fixture-only dashboard button is hidden from the operator UI, and the
external Finviz icon now sits beside the preset dropdown.

What remains: Fixture runs remain available through tests/offline paths, not as
a visible operator action. Live table pagination and richer saved table-state
behaviour remain future discovery refinements.

Files touched:

- `src/isa_system/web/index.html`
- `src/isa_system/web/styles.css`
- `tests/integration/test_command_center_ui.py`
- `docs/agent-coordination.md`
- `docs/implementation_status.md`

Tests run:

- `$env:PYTHONPATH='src'; python -m pytest tests/integration/test_command_center_ui.py -q` -> 3 passed.
- `$env:PYTHONPATH='src'; python -m pytest -q` -> 177 passed.
- `python -m ruff check .`
- `python -m ruff format --check src/isa_system/web tests/integration/test_command_center_ui.py`
- `node --check src/isa_system/web/app.js`
- `$env:PYTHONPATH='src'; python -m mypy` -> unchanged 25 legacy errors in
  pre-existing modules.
- Browser/IAB QA on `http://localhost:8501/#screener` confirmed the review
  cleanup and no current-asset console errors.

Integration concerns: No live trading, broker write path, or API key exposure
was introduced.

### 2026-05-12 - Portfolio Tab And AI Model Routing

What changed: Removed the defunct Streamlit dashboard package and
dashboard-specific tests from `main`, and moved the active UI forward in the
FastAPI-served command centre. Added a Portfolio tab with read-only
portfolio analytics, GPT-5.5 Portfolio Health Check controls, selected-stock
Deep Valuation controls, Maximum Depth, and optional Source-heavy Research Pack
mode. Added central OpenAI task routing in `services/ai_model_config.py` and
rerouted portfolio health and selected-stock valuation away from
`o3-deep-research` by default.

Model routing after this slice:

- `portfolio_health_check`: `gpt-5.5`, medium reasoning.
- `portfolio_health_check_detailed`: `gpt-5.5`, high reasoning.
- `selected_stock_valuation`: `gpt-5.5`, high reasoning.
- `selected_stock_valuation_max`: `gpt-5.5`, xhigh reasoning.
- `selected_stock_source_research`: `o3-deep-research` only when
  `OPENAI_ENABLE_O3_SOURCE_RESEARCH=true` or Source-heavy mode is explicitly
  selected.

Files touched:

- `.env.example`
- `README.md`
- `Makefile`
- `pyproject.toml`
- `docs/runbook.md`
- `docs/pilot-checklist.md`
- `docs/codex_extension_prompts.md`
- `src/isa_system/settings.py`
- `src/isa_system/services/ai_model_config.py`
- `src/isa_system/services/holding_health.py`
- `src/isa_system/services/deep_research.py`
- `src/isa_system/services/stock_valuation.py`
- `src/isa_system/api/routers/holding_health.py`
- `src/isa_system/api/routers/operator.py`
- `src/isa_system/api/routers/portfolio.py`
- `src/isa_system/web/index.html`
- `src/isa_system/web/app.js`
- `src/isa_system/web/styles.css`
- focused AI/model/UI tests

Tests run:

- `$env:PYTHONPATH='src'; python -m pytest -q tests` -> 174 passed.
- `python -m ruff check .` -> passed.
- `python -m ruff format --check src tests scripts` -> passed.
- `node --check src/isa_system/web/app.js` -> passed.

Integration concerns: Deep Valuation rejects empty selections and runs only on
explicit selected stocks. Source-heavy mode remains the only path to
`o3-deep-research`. No broker write path, live order submission, live arming, or
autonomous trading path was added.
