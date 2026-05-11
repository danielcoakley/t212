# Agent Coordination

## Current Goal

Ship a practical MVP operator cockpit for a local-first UK Stocks and Shares ISA
trading system. The immediate objective is not autonomous trading; it is a safe,
auditable workflow from account state to broker-seeded screener, consolidated
recommendations, deep research gate, and preview-only sizing. Paper evidence and
management visibility come before any deeper live execution work.

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
| Paper/report integration | Turing | `codex/paper-report-integration` | Active in isolated worktree |
| Paper cycle review surface | Cicero | `codex/paper-cycle-review` | Active in isolated worktree |
| Identity diagnostics | Heisenberg | `codex/identity-diagnostics` | Active in isolated worktree |
| API/release readiness QA | Franklin | `codex/api-release-readiness` | Active in isolated worktree |
| Auth, roles, permissions | Unassigned | `codex/auth-permission-design` | Pending |
| Testing, QA, deployment readiness | Zeno | `codex/parallel-partial-integration` | Completed guardrail slice |
| Management diagnostics phase 2 | Tesla | `codex/parallel-partial-integration` | Integrated |

## Parallel Execution Plan

This plan selects the next five practical MVP workstreams for separate Codex
execution agents. The selection favours operator readiness, workflow clarity,
pilot evidence, and regression protection over deeper enterprise architecture.

Status update: the first two isolated worker batches have been integrated into
`codex/parallel-partial-integration`. The latest integrated batch landed source
freshness diagnostics, paper intent persistence, and an operator report shell.
Full tests and lint are green after integration.

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

### Next Parallel Batch

The next batch should use `codex/parallel-partial-integration` as its base
after commit `261c92a` or later. Keep these streams MVP-focused and avoid live
execution work:

| Priority | Workstream | Branch/worktree | Likely files/directories | Acceptance criteria | Conflict risk |
| --- | --- | --- | --- | --- | --- |
| 1 | Paper/report integration | `codex/paper-report-integration` | `src/isa_system/services/operator_report.py`, `src/isa_system/services/paper_persistence.py`, `src/isa_system/api/routers/operator_report.py`, focused tests | Operator reports can include a supplied persisted paper cycle ID or clearly show no persisted cycle. Missing reconciliation remains explicit. | Moderate; owns report and paper service boundary. |
| 2 | Paper cycle review surface | `codex/paper-cycle-review` | `src/isa_system/dashboard/pages/preview.py`, `src/isa_system/api/routers/rebalances.py`, `tests/unit`, `tests/integration` | Operators can see how to save/reload paper cycles from Preview/API output without changing live execution. | Moderate; avoid report service files. |
| 3 | Identity diagnostics | `codex/identity-diagnostics` | `src/isa_system/services/instrument_validation.py`, `src/isa_system/dashboard/recommendation_charts.py`, `tests/unit`, docs | Broker ticker, research symbol, ISIN, and validation confidence are easier to inspect before schema-heavy mapping. | Moderate; avoid migrations unless separately approved. |
| 4 | API/release readiness QA | `codex/api-release-readiness` | `tests/integration`, `src/isa_system/smoke_test.py`, `docs/runbook.md`, `TODO.md` | Fast offline checks cover new report and paper-cycle endpoints, migration shape, and no-live-submit guardrails. | Low; tests/docs first. |

Recommended merge order for the next batch: API/release readiness QA, identity
diagnostics, paper/report integration, then paper cycle review surface. Merge
dashboard work last if it touches Preview rendering.

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

### 2026-05-11 - Paper/report integration

What changed: Connected the operator report shell to supplied persisted paper
cycles. Reports can now include a loaded paper-cycle ID, persistence status,
intent/fill counts, expected/simulated totals, and persisted intent records
while still distinguishing simulated-only paper workflow evidence. Missing
paper reconciliation remains explicit.

What remains: Broker reconciliation and a dashboard paper-cycle review surface
are still future work. Reports can surface persisted cycle evidence but do not
make it reconciled or live-executable.

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
