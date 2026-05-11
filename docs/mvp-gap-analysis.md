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

The highest-value next gap is operator management clarity. The code has safety
state and guardrails, but the dashboard has no dedicated Management page for
mode, live arming, kill switch, provider setup, cache freshness, and safety
checklist visibility.

## Architecture Inventory

| Layer | Exists | Only planned / thin | Notes |
| --- | --- | --- | --- |
| Frontend/dashboard | Streamlit cockpit with Overview, Screener, Recommendations, Deep Research, Preview, Advanced | Dedicated Management/Settings page, onboarding checklist, report export | Avoid adding a separate React app unless the product direction changes. |
| Backend/API | FastAPI with health, config, backtest, rebalance, mode, order, audit, metric, portfolio, recommendation, research, valuation routes | Rich management/status endpoint, persisted paper-cycle APIs, report APIs | Keep local-only semantics and explicit live guards. |
| Database | Operational SQLAlchemy models for configs, rebalance runs, order batches, orders, fills, position/cash snapshots, risk events, audit, idempotency, registry, universe snapshots, research reviews | Issuer identity table, explicit identity mapping confidence, paper-cycle records, thesis records, alerts, settings audit diff detail | Avoid sweeping migrations until identity/paper slices are scoped. |
| Auth/permissions | Local bind host, runtime mode, live arming, kill switch state | User auth, roles, approval permissions | Not MVP-critical for local-first use; document first. |
| Reporting | Backtest and smoke outputs, Streamlit charts, audit log page | Weekly operator report export, release notes, paper acceptance evidence pack | Build from existing data after paper persistence. |
| Workflow | Recommendation to research gate to preview-only sizing exists | Pilot cycle tracking, paper reconciliation, approval queue | Paper first, live later. |
| Management/admin | Sidebar status plus API mode endpoints | Dedicated page for controls, configuration gaps, provider status, safety checklist | Best first implementation target. |

## Current Feature Status

| Feature | Status | Evidence in repo | MVP gap |
| --- | --- | --- | --- |
| Local setup and tests | Exists | `README.md`, `pyproject.toml`, tests | Add onboarding/setup checklist once Management page exists. |
| Trading 212 read-only portfolio | Exists | `portfolio_state.py`, Trading 212 client, dashboard overview | Better freshness and provider diagnostics. |
| Broker-universe scan seed | Exists | `market_scan.py`, `market_screener.py`, recommendation routes | Add source freshness and coverage warnings. |
| Recommendations | Exists | `recommendations.py`, `recommendation_handoff.py`, dashboard charts/tests | Add rank changes, source freshness, official evidence links. |
| Deep research gate | Exists | `deep_research.py`, `research_reviews.py`, migration `0002` | Improve evidence packets and review comparison. |
| Preview-only sizing | Exists | `recommendation_preview.py`, `/rebalances/from-recommendations/preview` | Add quantity estimates and cash/exposure impacts. |
| Paper simulation | Partial | `paper_broker.py`, `paper_simulation.py`, paper simulation endpoint | Persist paper intents/fills and reconcile against preview. |
| Live execution | Guarded starter | `modes.py`, Trading 212 submit client, idempotency manager | Keep guarded; do not expand before paper acceptance. |
| Official UK evidence | Partial/stub | FCA NSM, LSE RNS, Companies House provider modules | Need robust PIT ingestion and parser tests. |
| Identity mapping | Partial | Instrument registry, instrument validation | Need issuer mapping and confidence/manual overrides. |
| Cost/friction model | Exists | `portfolio/costs.py`, tests | Ensure preview/backtest/report parity. |
| Backtesting | Exists | Backtest package and API route | Needs UI polish and PIT event/fundamental integration. |
| Management console | Missing | Sidebar metrics only | Add read-only Management page now. |

## MVP-Critical Gaps

### 1. Management Console

Why it matters: The research report repeatedly emphasizes paper-first safety,
manual approval, kill switch, provider status, settings versioning, and live
guardrails. These exist only as scattered API/sidebar concepts.

Recommended first slice:

- Add `src/isa_system/dashboard/pages/management.py`.
- Add "Management" to the dashboard workflow.
- Show mode, broker environment, broker status, live arming, kill switch,
  cache window, provider configuration, and safety checklist.
- Keep it read-only for the first pass.

Acceptance:

- Operator can answer "is the system safe and configured?" from one page.
- No live submit path is added.
- Tests cover any pure helper logic.

### 2. Paper Cycle Persistence

Why it matters: Paper trading is the bridge between preview and any future
micro-live readiness.

Recommended slice:

- Persist selected preview rows as paper order intents.
- Persist simulated fills.
- Add expected-vs-simulated reconciliation summary.

Acceptance:

- A paper cycle can be replayed and audited.
- Preview cost assumptions remain visible.

### 3. Identity Mapping

Why it matters: Broker tickers, research symbols, ISINs, LEIs, and company
numbers are a primary operational risk.

Recommended slice:

- Add an identity mapping model and migration.
- Connect Trading 212 metadata to ISIN and research symbol first.
- Leave LEI/company number nullable until official-source enrichment is deeper.

Acceptance:

- Validation exposes confidence and manual override status.
- No existing recommendation rows lose broker validation.

### 4. Official Evidence And PIT Controls

Why it matters: Catalyst and rerating strategies rely on official timestamps.

Recommended slice:

- Add a small official-event record shape with `available_at_utc`.
- Add tests that reject future information.
- Treat FCA NSM as validation/archive, not real-time event trading.

Acceptance:

- Recommendation evidence can show official source freshness.
- Backtests do not consume events before availability.

### 5. Reporting And Release Notes

Why it matters: The operator needs paper acceptance evidence and later agents
need implementation history.

Recommended slice:

- Add `CHANGELOG.md` after the next feature checkpoint.
- Add a weekly operator summary service after paper persistence exists.

Acceptance:

- Commits and docs form a clear release trail.

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

