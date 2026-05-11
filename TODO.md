# TODO

This file tracks MVP execution tasks across worker agents. The source of truth
for ownership and merge order remains `docs/agent-coordination.md`.

## Active Now

| Priority | Task | Owner | Branch/worktree | Status |
| --- | --- | --- | --- | --- |
| P0 | Management diagnostics phase 2 | Tesla | `codex/management-diagnostics` | Active in isolated worktree |
| P0 | MVP QA and route guardrails | Zeno | `codex/mvp-qa-guardrails-2` | Active in isolated worktree |
| P1 | Pilot paper workflow shell | Meitner | `codex/pilot-paper-workflow` | Active in isolated worktree |

## Completed This Cycle

| Task | Commit | Notes |
| --- | --- | --- |
| Local onboarding and pilot setup | `6248cca` | Added local first-run docs, safer provider setup notes, and pilot checklist. |
| Recommendation display UX and evidence clarity | `2c3f050` | Added review-state, broker/research gate, evidence coverage, and source caveat columns. |
| Notional recommendation paper preview simulation | `eb33f30` | Added notional-only recommendation preview paper simulation helper and tests. |

## Next Queue

| Priority | Task | Why next |
| --- | --- | --- |
| P1 | Integrate isolated worker branches in recommended merge order | Stabilise parallel work and resolve handoff notes. |
| P1 | Add provider/source freshness to recommendation and management surfaces | Improves operator trust before deeper paper or live work. |
| P1 | Persist paper order intents and simulated fills | Required before any credible micro-live readiness review. |
| P1 | Add identity mapping slice for broker ticker, research symbol, and ISIN | Reduces the main instrument mismatch risk. |
| P2 | Add report export shell | Useful after paper workflow data exists. |

## Deferred

| Task | Reason |
| --- | --- |
| Hosted auth and roles | Local-first MVP does not need hosted auth yet. |
| Full-auto live trading | Blocked until paper acceptance, reconciliation, and explicit approval. |
| Broad official-source catalyst strategy | Needs point-in-time event ingestion and parser versioning first. |
| Framework change to React/Vite | Current Streamlit cockpit is sufficient for MVP delivery. |
