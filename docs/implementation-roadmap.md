# Implementation Roadmap

This roadmap converts the deep research report at
`C:\Users\DanielCoakley\Downloads\deep-research-report.md` into staged,
repo-specific delivery work. It complements `docs/roadmap.md`, which already
realigned the starter toward a preview-only MVP cockpit.

## Current Architecture

The codebase is a local-first Python 3.12 application with:

| Area | Current implementation |
| --- | --- |
| Backend API | FastAPI app in `src/isa_system/api/main.py` with routers for health, configs, portfolio, recommendations, research reviews, valuation, rebalance preview, modes, orders, metrics, backtests, and audit. |
| Dashboard | Streamlit app in `src/isa_system/dashboard/app.py` with front-stage workflow pages: Overview, Screener, Recommendations, Deep Research, Preview, Management, and Advanced diagnostics. |
| Data and providers | Provider adapters under `src/isa_system/data/providers`, including Trading 212, yfinance, Alpha Vantage, FMP, SEC EDGAR, Companies House, LSE RNS, FCA NSM, FRED, Reddit, and X stubs/adapters. |
| Storage | SQLAlchemy operational DB models in `src/isa_system/db/models.py`, Alembic migrations, and DuckDB/Parquet lake helpers under `src/isa_system/lake`. |
| Strategy and risk | Factors, ranking, constraints, cost model, rebalancer, recommendation services, screener funnel, deep research gate, and recommendation-to-preview hand-off. |
| Execution controls | Runtime mode state, guarded live arming, local idempotency keys, Trading 212 client, paper broker, and preview-only sizing. |
| Auth and permissions | No user auth yet. Local-only binding and preview/live controls are the current safety boundary. |
| Reporting | Smoke-test artifacts, backtest services, valuation charts, recommendation charts, audit log pages, paper workflow summaries, operator report shell, and API outputs exist. |
| Release notes | Git history, `CHANGELOG.md`, `TODO.md`, `AGENTS.md`, and coordination docs now track MVP execution. |

No `package.json` is present; this is a Python project and `pyproject.toml` is
the package manifest.

## Product Direction

The MVP should remain a daily-bar, long-only, ISA-safe operator cockpit. Trading
212 is the execution, account-state, accessible-universe, and reconciliation
truth source. Historical prices, fundamentals, official filings, catalysts, and
macro context come from external providers and official sources. The app should
not become an autonomous intraday trading bot.

The current MVP goal is:

> Let an operator review account state, inspect the broker-seeded market
> screener, evaluate a consolidated recommendation queue, run a deep research
> gate for buy/add ideas, and generate preview-only sizing while live execution
> remains explicitly guarded.

## MVP-Critical Features

| Priority | Feature | Current state | Next implementation step |
| --- | --- | --- | --- |
| P0 | Operator cockpit workflow | Implemented in Streamlit with Management visibility | Continue simplifying workflow labels and empty/error states. |
| P0 | Broker-readable portfolio and universe | Read-only account/positions, instrument metadata support, and freshness diagnostics exist | Add identity diagnostics and rate-limit context. |
| P0 | Recommendation queue and hand-off | Implemented with broker validation, research status, review-state columns, and source freshness context | Add rank-change history and official evidence links. |
| P0 | Deep research gate | Implemented and persisted; OpenAI key absent means no buy approval | Improve evidence packets, expiry controls, and comparison between current and previous reviews. |
| P0 | Preview-only sizing | Implemented for selected eligible recommendations, with pilot paper workflow shell and paper-cycle persistence | Add paper-cycle review surface and richer cash/exposure reporting. |
| P0 | Safety management | Implemented as read-only Management diagnostics plus API mode routes and sidebar status | Add richer status APIs only where they reduce dashboard coupling. |
| P1 | Paper trading loop | Paper broker, simulation, workflow summary, and replayable paper-cycle persistence exist; reconciliation still thin | Add persisted cycle review, report integration, and expected-vs-actual reconciliation. |
| P1 | Official UK evidence | Provider adapters/stubs exist | Prioritise Companies House identity, FCA NSM/RNS event tags, PDMR dealing, and short-interest parser versioning. |
| P1 | Point-in-time identity mapping | Instrument registry exists; issuer identity is incomplete | Add explicit broker ticker, research symbol, ISIN, LEI, company number mapping with confidence and manual override. |
| P1 | Reporting and release notes | Basic charts, audit pages, changelog, and operator report shell exist | Connect reports to persisted paper cycles and add export/display polish later. |

## Post-MVP Features

| Feature | Why later | Dependencies |
| --- | --- | --- |
| Catalyst drift strategy | High value, but depends on official event ingestion and point-in-time timestamps. | FCA NSM/RNS, Companies House, event schema, tests for `available_at_utc`. |
| Rerating strategy | Useful but more heuristic than quality-momentum; should follow stronger evidence plumbing. | PDMR tags, short-interest changes, valuation context, thesis records. |
| Full paper reconciliation | Needed before any micro-live move, but not needed to improve the review cockpit. | Paper persistence, order batch records, broker history/export ingestion. |
| Backtest dashboard polish | Existing backtest scaffolding can be surfaced after the daily-bar pipeline is reliable. | EOD provider stability, strategy config hashes, cost model parity. |
| Local onboarding/setup screen | Valuable for pilots but secondary to core safety and evidence flow. | Management page, provider status checks, env validation. |
| Operator report export | Useful for weekly review and audit, not a blocker for MVP previews. | Recommendation, research review, preview, and paper cycle summaries. |

## Enterprise-Grade Later Features

| Feature | Reason to defer |
| --- | --- |
| Multi-user auth, roles, and permissions | The current app is local-first. Add only after cockpit workflows and data controls stabilize. |
| Hosted deployment architecture | The current safety assumption is local binding. Hosting changes need a separate threat model. |
| Team approval workflow | Useful for managed operations, but premature before paper evidence and local management controls. |
| Full-auto live trading | Explicitly guarded. Consider only after repeated paper cycles, reconciliation, idempotency drills, kill-switch drills, and an operator runbook review. |
| Provider redundancy and paid data plans | Keep the MVP free-source friendly until universe size or source reliability proves a need. |
| Advanced ML ranking | The research direction favours explainable deterministic scoring and rules-first NLP first. |

## Suggested Implementation Order

1. Connect operator reports to persisted paper cycles.
2. Add paper cycle review surface and later reconciliation dashboard section.
3. Add identity mapping table/service for broker ticker, research symbol, ISIN, LEI, and company number.
4. Add official-source event ingestion depth for Companies House and FCA NSM/RNS.
5. Expand catalyst tags and point-in-time tests.
6. Revisit auth and hosted deployment only after local workflow evidence is strong.

## Dependencies And Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Identifier mismatch | Wrong instrument could be reviewed or sized. | Prefer ISIN matching, expose broker ticker and research symbol, add identity confidence and manual override. |
| Point-in-time leakage | Backtests and recommendations look better than reality. | Store `available_at_utc`, test PIT joins, avoid convenience-source timestamps as official truth. |
| Duplicate live orders | Financial and compliance risk. | Keep local idempotency reservations mandatory before any broker POST. |
| Official feed semantics change | Catalyst signals can drift or break. | Version parsers, especially FCA short disclosures around 2026-07-13. |
| Provider limits and stale cache | Slow or stale recommendations. | Surface freshness, rate-limit notes, and cache source on management/recommendation pages. |
| Overbuilding live execution | Unsafe work before paper evidence. | Keep live guarded; focus on preview, paper, and reconciliation first. |

## Parallel Workstreams

### UI/UX Consistency And Simplification

Purpose: Keep the Streamlit cockpit focused on the MVP workflow and reduce
operator confusion.

Likely files: `src/isa_system/dashboard/app.py`,
`src/isa_system/dashboard/pages/*`, `src/isa_system/dashboard/charts.py`,
`src/isa_system/dashboard/recommendation_charts.py`,
`docs/dashboard_layout.md`.

Dependencies: Existing recommendation workflow services and portfolio snapshot
models.

Conflict risks: High with management console and preview page work; avoid
editing the same Streamlit pages in parallel.

Acceptance criteria: Core pages remain Overview, Screener, Recommendations,
Deep Research, Preview, Management, and Advanced. No duplicate front-stage
tables. Warnings, blockers, and preview-only status stay visible.

Suggested branch/worktree: `codex/ui-cockpit-simplification`.

Prompt:

```text
You are a Codex agent on the UI/UX consistency workstream. Read docs/agent-coordination.md, docs/implementation-roadmap.md, docs/mvp-gap-analysis.md, docs/dashboard_layout.md, and the Streamlit dashboard code. Improve only the operator cockpit UI structure and clarity. Do not change backend service semantics. Keep live execution guarded and preview-only language visible. Add focused tests where practical and update handoff notes in docs/agent-coordination.md.
```

### Landing Page, Pricing, Signup, Onboarding

Purpose: For this local-first app, replace SaaS-style pricing/signup with local
operator onboarding, setup checks, and pilot readiness.

Likely files: `README.md`, `.env.example`, `docs/runbook.md`,
`docs/assumptions.md`, future `src/isa_system/dashboard/pages/onboarding.py`.

Dependencies: Management/provider status work.

Conflict risks: Low if docs only; medium if adding a new dashboard page.

Acceptance criteria: A new operator can run tests, start API/dashboard, connect
read-only broker credentials, understand preview mode, and avoid live trading.

Suggested branch/worktree: `codex/local-onboarding`.

Prompt:

```text
You are a Codex agent on the local onboarding workstream. This is not a SaaS pricing/signup app. Read the roadmap and runbook, then improve setup and pilot onboarding docs and, if low risk, add a simple dashboard onboarding/checklist surface. Preserve local-first assumptions and do not introduce auth or hosting changes. Add handoff notes in docs/agent-coordination.md.
```

### Management Console / Admin Area

Purpose: Give the operator one place to inspect runtime mode, live arming,
kill-switch state, broker/provider configuration, cache freshness, safety
checklist, and blocked capabilities.

Likely files: `src/isa_system/dashboard/app.py`,
`src/isa_system/dashboard/pages/management.py`,
`src/isa_system/api/routers/health.py`, `src/isa_system/api/routers/modes.py`,
`tests/unit/*dashboard*`, `tests/integration/test_api.py`.

Dependencies: Current settings, health, broker snapshot, and cache policy.

Conflict risks: High with UI shell edits; coordinate page names and navigation.

Acceptance criteria: Dashboard includes a Management page that is read-only for
MVP, clearly states preview/live guardrails, shows configuration gaps, and does
not submit orders.

Suggested branch/worktree: `codex/management-console-skeleton`.

Prompt:

```text
You are a Codex agent on the management console workstream. Read docs/agent-coordination.md, docs/implementation-roadmap.md, docs/mvp-gap-analysis.md, src/isa_system/dashboard/app.py, settings.py, api/deps.py, api/routers/health.py, and api/routers/modes.py. Add a low-risk Streamlit Management page that surfaces mode, live arming, kill switch, broker/provider configuration, cache freshness, and safety checklist. Keep controls read-only unless existing API semantics already support them. Add focused tests and update handoff notes.
```

### Pilot Customer Workflow

Purpose: Define and support a repeatable pilot cycle: configure, refresh,
review recommendations, run research, preview sizing, paper simulate, and
record outcome.

Likely files: `docs/runbook.md`, `docs/dashboard_layout.md`,
`src/isa_system/dashboard/pages/preview.py`,
`src/isa_system/services/paper_simulation.py`, future paper persistence models.

Dependencies: Management console, preview workflow, paper persistence.

Conflict risks: Medium with paper workflow and UI work.

Acceptance criteria: Pilot cycle has explicit steps, status outputs, and
acceptance evidence without live order submission.

Suggested branch/worktree: `codex/pilot-workflow`.

Prompt:

```text
You are a Codex agent on the pilot customer workflow workstream. Read the roadmap, runbook, preview page, and paper simulation service. Define and implement the next smallest pilot-cycle improvement that helps an operator move from recommendation review to preview and paper evidence. Do not add live execution. Add or update tests and handoff notes.
```

### Portfolio And Instrument Data Model

Purpose: Close the gap between broker instruments, research symbols, ISINs,
issuers, LEIs, and Companies House company numbers.

Likely files: `src/isa_system/db/models.py`, Alembic migrations,
`src/isa_system/domain/models.py`, `src/isa_system/services/instrument_validation.py`,
`src/isa_system/data/providers/*`, tests under `tests/unit`.

Dependencies: Trading 212 metadata and official-source provider fields.

Conflict risks: High with migrations and validation services; own schema files
carefully.

Acceptance criteria: Identity mapping is explicit, confidence-scored, indexed,
and test-covered without breaking existing instrument validation.

Suggested branch/worktree: `codex/identity-mapping`.

Prompt:

```text
You are a Codex agent on the portfolio and instrument data model workstream. Read coordination docs, db models, migrations, domain models, instrument validation, and provider schemas. Design and implement the smallest identity-mapping slice for broker ticker, research symbol, ISIN, LEI, company number, source, confidence, and manual override. Include migration impact notes and tests. Avoid changing dashboard pages unless necessary.
```

### Report Generation

Purpose: Produce weekly/operator-ready summaries from recommendations, research
reviews, previews, paper cycles, costs, and warnings.

Likely files: `src/isa_system/services/*report*` future module,
`src/isa_system/api/routers/*`, `src/isa_system/dashboard/pages/*`,
`docs/runbook.md`, tests.

Dependencies: Preview, research review, paper persistence, and audit log data.

Conflict risks: Low at first if implemented as a new service.

Acceptance criteria: One command or API route can produce a compact report from
available local data, with missing sections clearly marked.

Suggested branch/worktree: `codex/report-generation`.

Prompt:

```text
You are a Codex agent on the report generation workstream. Read the roadmap, audit/research/preview services, and existing smoke artifacts. Add a small, testable report service or documented design for weekly operator summaries. Keep it local, deterministic, and tolerant of missing data. Update coordination handoff notes.
```

### Recommendation Engine / Agent Output

Purpose: Improve explainable scoring, source freshness, rank changes, evidence
links, and the deep research evidence packet.

Likely files: `src/isa_system/services/recommendations.py`,
`src/isa_system/services/recommendation_handoff.py`,
`src/isa_system/services/deep_research.py`,
`src/isa_system/dashboard/recommendation_charts.py`, tests.

Dependencies: Valuation, technicals, catalysts, instrument validation.

Conflict risks: Medium with preview and deep research page work.

Acceptance criteria: Recommendation rows expose deterministic reason codes,
source freshness, blockers, and research status without creating order
authority.

Suggested branch/worktree: `codex/recommendation-evidence`.

Prompt:

```text
You are a Codex agent on the recommendation engine workstream. Read coordination docs and the recommendations, handoff, deep_research, and dashboard recommendation chart code. Improve the smallest high-value evidence field such as source freshness, rank-change context, or deep research packet detail. Keep deterministic rules authoritative and live execution separate. Add tests and handoff notes.
```

### Auth, Roles, Permissions

Purpose: Prepare a future permission model without adding premature hosted auth.

Likely files: `docs/architecture.md`, `docs/runbook.md`,
`src/isa_system/api/deps.py`, `src/isa_system/settings.py`.

Dependencies: Management console and local safety requirements.

Conflict risks: High if implemented too early; prefer design notes first.

Acceptance criteria: A documented permission model distinguishes read-only,
paper operator, live approver, and admin capabilities. No hosted auth is
introduced without explicit approval.

Suggested branch/worktree: `codex/auth-permission-design`.

Prompt:

```text
You are a Codex agent on the auth and permissions workstream. Do not implement hosted auth. Read the coordination docs, settings, API deps, modes, and runbook. Produce a concise permission model and identify future code seams for local password or role checks. Keep changes mostly documentation unless a small type-safe interface is clearly useful. Add handoff notes.
```

### Testing, QA, Deployment Readiness

Purpose: Keep existing functionality stable while expanding MVP confidence.

Likely files: `tests/unit`, `tests/integration`, `src/isa_system/smoke_test.py`,
`Makefile`, `.github/*`, `README.md`.

Dependencies: Active feature branches.

Conflict risks: Low to medium; avoid broad test rewrites while feature work is
in flight.

Acceptance criteria: FastAPI smoke routes, recommendation hand-off, preview
guardrails, deep research fallback, idempotency, and dashboard data transforms
have focused tests.

Suggested branch/worktree: `codex/testing-readiness`.

Prompt:

```text
You are a Codex agent on the testing and deployment readiness workstream. Read the coordination docs, pyproject, Makefile, tests, and current API/dashboard services. Add focused smoke or regression tests for the highest-risk MVP guardrails without broad refactors. Run the relevant checks and update handoff notes.
```

### Documentation And Release Notes

Purpose: Keep project direction, agent handoffs, and release history current as
the MVP evolves.

Likely files: `docs/*.md`, future `CHANGELOG.md`, future `TODO.md`.

Dependencies: All workstreams.

Conflict risks: Medium because many agents may update coordination docs.

Acceptance criteria: Roadmap, gap analysis, coordination, runbook, and release
notes reflect the shipped code and known gaps.

Suggested branch/worktree: `codex/docs-release-notes`.

Prompt:

```text
You are a Codex agent on the documentation and release notes workstream. Read all docs plus recent git history. Update docs to reflect actual implementation status, add a concise changelog/TODO structure only if useful, and keep docs aligned with code. Do not make feature code changes unless they are required to fix broken doc references. Add handoff notes.
```
