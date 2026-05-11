# TODO

This file tracks MVP execution tasks across worker agents. The source of truth
for ownership and merge order remains `docs/agent-coordination.md`.

## Active Now

| Priority | Task | Owner | Branch/worktree | Status |
| --- | --- | --- | --- | --- |
| P0 | Management diagnostics phase 2 | Beauvoir | `codex/management-diagnostics` | Active |
| P0 | Local onboarding and pilot setup | Hypatia | `codex/local-onboarding` | Active |
| P0 | Recommendation display UX and evidence clarity | Russell | `codex/recommendation-display-ux` | Active |
| P0 | MVP QA and route guardrails | Faraday | `codex/mvp-qa-guardrails` | Active |
| P1 | Pilot paper workflow shell | Dirac | `codex/pilot-paper-workflow` | Active |

## Next Queue

| Priority | Task | Why next |
| --- | --- | --- |
| P1 | Integrate worker branches in recommended merge order | Stabilise parallel work and resolve handoff notes. |
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

