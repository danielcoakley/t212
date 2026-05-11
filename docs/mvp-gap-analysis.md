# MVP Gap Analysis

This analysis compares the deep research direction with the current
FastAPI/Streamlit codebase. It is intentionally practical: it identifies what
exists, what is planned, and what should happen next without duplicating
already shipped functionality.

## Executive Summary

The repository is already past a blank starter. It has a meaningful MVP cockpit:
read-only Trading 212 context, broker-universe scanning, recommendation scoring,
instrument validation, deep research review persistence, preview-only sizing,
paper simulation, guarded live arming, audit logging, and tests around several
critical flows.

The highest-value next gap is paper reconciliation clarity. The first
Management page, pilot workflow shell, paper-cycle persistence, saved-cycle
review, and operator report shell now exist, but persisted paper cycles still do
not compare against broker evidence or an explicit reconciliation summary.

## Architecture Inventory

| Layer | Exists | Only planned / thin | Notes |
| --- | --- | --- | --- |
| Frontend/dashboard | Streamlit cockpit with Overview, Screener, Recommendations, Deep Research, Preview, Management, Advanced | Onboarding checklist page, report export | Avoid adding a separate React app unless the product direction changes. |
| Backend/API | FastAPI with health, config, backtest, rebalance, pilot workflow, paper-cycle persistence, operator report, mode, order, audit, metric, portfolio, recommendation, research, valuation routes | Rich management/status endpoint, paper reconciliation APIs | Keep local-only semantics and explicit live guards. |
| Database | Operational SQLAlchemy models for configs, rebalance runs, order batches, orders, fills, paper cycles/intents/simulated fills, position/cash snapshots, risk events, audit, idempotency, registry, universe snapshots, research reviews | Issuer identity table, explicit identity mapping confidence, thesis records, alerts, settings audit diff detail | Avoid sweeping migrations until identity slices are scoped. |
| Auth/permissions | Local bind host, runtime mode, live arming, kill switch state | User auth, roles, approval permissions | Not MVP-critical for local-first use; document first. |
| Reporting | Backtest and smoke outputs, Streamlit charts, audit log page, changelog, operator report shell with persisted paper-cycle evidence | Paper acceptance evidence pack and export polish | Build from existing paper persistence and report service. |
| Workflow | Recommendation to research gate to preview-only sizing, paper workflow summary, and persisted paper cycles exist | Paper reconciliation, approval queue | Paper first, live later. |
| Management/admin | Sidebar status, API mode endpoints, read-only Management page | Rich status endpoint, write controls only after explicit safety review | Keep Management read-only for MVP. |

## Current Feature Status

| Feature | Status | Evidence in repo | MVP gap |
| --- | --- | --- | --- |
| Local setup and tests | Exists | `README.md`, `pyproject.toml`, tests | Add onboarding/setup checklist once Management page exists. |
| Trading 212 read-only portfolio | Exists | `portfolio_state.py`, Trading 212 client, dashboard overview | Better freshness and provider diagnostics. |
| Broker-universe scan seed | Exists | `market_scan.py`, `market_screener.py`, recommendation routes | Add coverage warnings and identity diagnostics. |
| Recommendations | Exists | `recommendations.py`, `recommendation_handoff.py`, dashboard charts/tests | Add rank changes and official evidence links. |
| Deep research gate | Exists | `deep_research.py`, `research_reviews.py`, migration `0002` | Improve evidence packets and review comparison. |
| Preview-only sizing | Exists | `recommendation_preview.py`, `/rebalances/from-recommendations/preview`, paper-cycle save/reload routes, Preview saved-cycle inspector | Add richer cash/exposure reporting. |
| Paper simulation | Partial | `paper_broker.py`, `paper_simulation.py`, pilot workflow endpoint, persisted paper cycles, report integration | Reconcile persisted paper cycles against preview and later broker evidence. |
| Live execution | Guarded starter | `modes.py`, Trading 212 submit client, idempotency manager | Keep guarded; do not expand before paper acceptance. |
| Official UK evidence | Partial/stub | FCA NSM, LSE RNS, Companies House provider modules | Need robust PIT ingestion and parser tests. |
| Identity mapping | Partial | Instrument registry, instrument validation | Need issuer mapping and confidence/manual overrides. |
| Cost/friction model | Exists | `portfolio/costs.py`, tests | Ensure preview/backtest/report parity. |
| Backtesting | Exists | Backtest package and API route | Needs UI polish and PIT event/fundamental integration. |
| Management console | Exists first pass | `dashboard/pages/management.py`, management tests | Add richer source freshness/status API only if it reduces coupling. |

## MVP-Critical Gaps

### 1. Paper Reconciliation Summary

Why it matters: Paper trading is the bridge between preview and any future
micro-live readiness. The current workflow can persist and inspect expected vs
simulated paper output, but operators still need a clear reconciliation
placeholder and later expected-vs-actual comparison path.

Recommended slice:

- Add a small paper reconciliation summary shape.
- Include cycle ID, expected totals, simulated totals, missing broker evidence,
  and next action.
- Keep reconciliation status explicit as unavailable until broker evidence is
  ingested.

Acceptance:

- Persisted paper cycles can be summarized as unreconciled without ambiguity.
- Report and dashboard output distinguish simulated, persisted, and reconciled
  evidence.
- No live submit path is added.

### 2. Identity Mapping

Why it matters: Broker tickers, research symbols, ISINs, LEIs, and company
numbers are a primary operational risk.

Recommended slice:

- Add an identity diagnostics view/service before a schema-heavy mapping table.
- Expose broker ticker, research symbol, ISIN, and validation confidence.
- Leave LEI/company number nullable until official-source enrichment is deeper.

Acceptance:

- Validation exposes confidence and manual override status.
- No existing recommendation rows lose broker validation.

### 3. Official Evidence And PIT Controls

Why it matters: Catalyst and rerating strategies rely on official timestamps.

Recommended slice:

- Add a small official-event record shape with `available_at_utc`.
- Add tests that reject future information.
- Treat FCA NSM as validation/archive, not real-time event trading.

Acceptance:

- Recommendation evidence can show official source freshness.
- Backtests do not consume events before availability.

### 4. API And Release Readiness

Why it matters: The operator needs paper acceptance evidence and later agents
need implementation history.

Recommended slice:

- Add smoke/regression coverage around new report and paper-cycle endpoints.
- Ensure migration naming and API docs are discoverable.
- Keep CHANGELOG/TODO and coordination docs synchronized after each batch.

Acceptance:

- Fast offline checks protect report, paper persistence, and no-live-submit
  guardrails.
- Documentation tells the next operator what is safe to try locally.

### 5. Management Status API

Why it matters: Management diagnostics currently live mostly in Streamlit
helpers. A thin read-only status API may reduce duplication if external clients
or report generation need the same state.

Recommended slice:

- Extract only stable management status fields that multiple surfaces need.
- Keep live controls read-only unless existing API semantics already authorize
  a safe state change.

Acceptance:

- Dashboard and report surfaces can share the same status shape.
- No new live arming or broker submit path is introduced.

## Non-MVP Or Deferred

| Item | Decision |
| --- | --- |
| Landing page, pricing, signup | Not relevant to the current local-first repo. Replace with onboarding/setup docs and possibly a dashboard checklist. |
| Hosted auth and roles | Defer. Document local permission model first. |
| Full-auto live trading | Defer behind paper evidence, reconciliation, kill-switch drills, and explicit approval. |
| Intraday/HFT logic | Non-goal. The research direction is daily/EOD and multi-day to multi-month holds. |
| Paid data-provider dependency | Defer until free-source limits become a measured blocker. |
| Opaque ML ranking | Defer. Keep explainable deterministic scoring plus transparent research review. |

## First Implementation Choice

Chosen task: add a Management console skeleton to the Streamlit dashboard.

Why this is safest and highest value:

- It is low conflict with the scoring, data, and execution engines.
- It improves operator safety without adding live capabilities.
- It creates a natural home for future settings, provider diagnostics, paper
  readiness, and onboarding checks.
- It aligns directly with the deep research report's emphasis on manual
  oversight, paper-first operation, and kill-switch visibility.

Expected files:

- `src/isa_system/dashboard/app.py`
- `src/isa_system/dashboard/pages/management.py`
- `tests/unit/test_dashboard_management.py`
- Documentation updates in `docs/dashboard_layout.md` and coordination notes if needed.
