# TODO

This file tracks MVP execution tasks across worker agents. The source of truth
for ownership and merge order remains `docs/agent-coordination.md`.

## Active Now

| Priority | Task | Owner | Branch/worktree | Status |
| --- | --- | --- | --- | --- |
| P1 | Source freshness diagnostics | Pascal | `codex/source-freshness-diagnostics` | Active in isolated worktree |
| P1 | Operator report export shell | Kant | `codex/operator-report-shell` | Active in isolated worktree |
| P1 | Paper intent and simulated fill persistence | Feynman | `codex/paper-intent-persistence` | Active in isolated worktree |

## Completed This Cycle

| Task | Commit | Notes |
| --- | --- | --- |
| Local onboarding and pilot setup | `6248cca` | Added local first-run docs, safer provider setup notes, and pilot checklist. |
| Recommendation display UX and evidence clarity | `2c3f050` | Added review-state, broker/research gate, evidence coverage, and source caveat columns. |
| Notional recommendation paper preview simulation | `eb33f30` | Added notional-only recommendation preview paper simulation helper and tests. |
| MVP QA and route guardrails | `1f2e6ea` | Added offline regression coverage for preview-only and no-live-submit guardrails. |
| Management diagnostics phase 2 | `2d6b47d` | Expanded the read-only Management page into an operational status surface. |
| Pilot paper workflow shell | `1e1e5c7` | Added a side-effect-free pilot paper workflow summary service, API route, and Preview page display. |

## Next Queue

| Priority | Task | Why next |
| --- | --- | --- |
| P1 | Add provider/source freshness to recommendation and management surfaces | Improves operator trust before deeper paper or live work. |
| P1 | Persist paper order intents and simulated fills | Required before any credible micro-live readiness review. |
| P1 | Add report export shell | Turns preview/research/paper summaries into auditable pilot evidence. |
| P1 | Add identity mapping slice for broker ticker, research symbol, and ISIN | Reduces the main instrument mismatch risk. |
| P2 | Add dashboard smoke/visual QA notes for Management, Recommendations, and Preview | Catches Streamlit rendering regressions outside pure unit tests. |

## Deferred

| Task | Reason |
| --- | --- |
| Hosted auth and roles | Local-first MVP does not need hosted auth yet. |
| Full-auto live trading | Blocked until paper acceptance, reconciliation, and explicit approval. |
| Broad official-source catalyst strategy | Needs point-in-time event ingestion and parser versioning first. |
| Framework change to React/Vite | Current Streamlit cockpit is sufficient for MVP delivery. |
