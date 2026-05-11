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
| Management console / admin area | Current orchestrator | `codex/mvp-roadmap-orchestration` | Completed first slice |
| UI/UX consistency and simplification | Unassigned | `codex/ui-cockpit-simplification` | Pending |
| Local onboarding and pilot setup | Unassigned | `codex/local-onboarding` | Pending |
| Pilot customer workflow | Unassigned | `codex/pilot-workflow` | Pending |
| Portfolio and instrument data model | Unassigned | `codex/identity-mapping` | Pending |
| Recommendation engine / agent output | Unassigned | `codex/recommendation-evidence` | Pending |
| Report generation | Unassigned | `codex/report-generation` | Pending |
| Auth, roles, permissions | Unassigned | `codex/auth-permission-design` | Pending |
| Testing, QA, deployment readiness | Unassigned | `codex/testing-readiness` | Pending |

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
