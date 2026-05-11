# TODO

This file tracks MVP execution tasks across worker agents. The source of truth
for ownership and merge order remains `docs/agent-coordination.md`.

## Active Now

| Priority | Task | Owner | Branch/worktree | Status |
| --- | --- | --- | --- | --- |
| P1 | Paper/report integration | Turing | `codex/paper-report-integration` | Active in isolated worktree |
| P1 | Paper cycle review surface | Cicero | `codex/paper-cycle-review` | Active in isolated worktree |
| P1 | Identity diagnostics | Heisenberg | `codex/identity-diagnostics` | Active in isolated worktree |
| P1 | API/release readiness QA | Franklin | `codex/api-release-readiness` | Active in isolated worktree |

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

## Next Queue

| Priority | Task | Why next |
| --- | --- | --- |
| P1 | Connect operator reports to persisted paper cycles | Report shell landed before paper persistence integration, so it needs a small follow-up. |
| P1 | Add paper cycle review surface | Operators need a clear way to inspect saved paper evidence before reconciliation. |
| P1 | Add identity mapping slice for broker ticker, research symbol, and ISIN | Reduces the main instrument mismatch risk. |
| P2 | Add dashboard smoke/visual QA notes for Management, Recommendations, and Preview | Catches Streamlit rendering regressions outside pure unit tests. |

## Deferred

| Task | Reason |
| --- | --- |
| Hosted auth and roles | Local-first MVP does not need hosted auth yet. |
| Full-auto live trading | Blocked until paper acceptance, reconciliation, and explicit approval. |
| Broad official-source catalyst strategy | Needs point-in-time event ingestion and parser versioning first. |
| Framework change to React/Vite | Current Streamlit cockpit is sufficient for MVP delivery. |
