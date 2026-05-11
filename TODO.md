# TODO

This file tracks MVP execution tasks across worker agents. The source of truth
for ownership and merge order remains `docs/agent-coordination.md`.

## Active Now

| Priority | Task | Owner | Branch/worktree | Status |
| --- | --- | --- | --- | --- |
| P1 | Paper reconciliation summary | Unassigned | `codex/paper-reconciliation-summary` | Queued |
| P1 | Dashboard smoke automation | Unassigned | `codex/dashboard-smoke-readiness` | Queued |
| P1 | Official evidence packet diagnostics | Unassigned | `codex/evidence-packet-diagnostics` | Queued |
| P2 | MVP release notes | Unassigned | `codex/mvp-release-notes` | Queued |

## Completed This Cycle

| Task | Commit | Notes |
| --- | --- | --- |
| Local onboarding and pilot setup | `6248cca` | Added local first-run docs, safer provider setup notes, and pilot checklist. |
| Recommendation display UX and evidence clarity | `2c3f050` | Added review-state, broker/research gate, evidence coverage, and source caveat columns. |
| Notional recommendation paper preview simulation | `eb33f30` | Added notional-only recommendation preview paper simulation helper and tests. |
| MVP QA and route guardrails | `1f2e6ea` | Added offline regression coverage for preview-only and no-live-submit guardrails. |
| Management diagnostics phase 2 | `2d6b47d` | Expanded the read-only Management page into an operational status surface. |
| Pilot paper workflow shell | `1e1e5c7` | Added a side-effect-free pilot paper workflow summary service, API route, and Preview page display. |
| Source freshness diagnostics | `2ad537e` | Added dashboard source/cache age helpers and source freshness displays. |
| Paper intent and simulated fill persistence | `98b6754` | Added paper-cycle, paper-intent, and simulated-fill persistence with deterministic IDs. |
| Operator report export shell | `261c92a` | Added side-effect-free report service and API route for MVP evidence summaries. |
| Paper cycle review surface | `016d1ce` | Added Preview-page saved paper-cycle inspector and helper tests. |
| Paper/report integration | `62cc85b` | Connected operator reports to supplied persisted paper-cycle evidence. |
| API/release readiness QA | `3c077ea` | Added offline release-readiness checks for report/paper-cycle API contracts, migration discovery/shape, missing paper-cycle reloads, and no-live-submit guardrails. |
| Identity diagnostics | `6df047d` | Added identity confidence, ISIN, candidate broker tickers, and mismatch caveats to validation/handoff/dashboard helper output. |

## Next Queue

| Priority | Task | Why next |
| --- | --- | --- |
| P1 | Add paper reconciliation summary | Next logical step after persisted paper cycles and report integration. |
| P1 | Add evidence packet diagnostics | Deep research and official-source caveats remain the next trust gap before paper acceptance. |
| P2 | Add dashboard smoke/visual QA notes for Management, Recommendations, and Preview | Catches Streamlit rendering regressions outside pure unit tests. |

## Deferred

| Task | Reason |
| --- | --- |
| Hosted auth and roles | Local-first MVP does not need hosted auth yet. |
| Full-auto live trading | Blocked until paper acceptance, reconciliation, and explicit approval. |
| Broad official-source catalyst strategy | Needs point-in-time event ingestion and parser versioning first. |
| Framework change to React/Vite | Current Streamlit cockpit is sufficient for MVP delivery. |
