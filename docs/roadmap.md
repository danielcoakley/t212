# Portfolio Intelligence Roadmap

The system is a local-first, long-only ISA portfolio intelligence cockpit. It
automates research workflow steps and produces manual-review previews. It is
not an autonomous trading bot.

## Phase A - Research Automation

Implemented baseline:

- Finviz discovery
- OpenBB enrichment wrapper
- Deterministic scoring and top 10 selection
- Thesis tracking
- Structured research reports
- Offline end-to-end smoke pipeline

Next improvements:

- Validate real OpenBB endpoint paths.
- Expand enrichment field coverage.
- Add more robust official-source evidence packets.

## Phase B - OpenBB Workspace Integration

Implemented baseline:

- `/workspace/widgets.json`
- Ranked candidates widget metadata
- Thesis/watchlist metadata
- Holdings and rebalance proposal metadata
- Risk warnings and report metadata

Next improvements:

- Test against the operator's exact Workspace custom backend flow.
- Add richer table schemas if Workspace expects them.

## Phase C - Trading 212 Read-Only

Implemented baseline:

- Optional API key loading
- Read-only account and position routes
- Local order preview only
- Deterministic duplicate hash
- No live submit route

Next improvements:

- Validate demo account read paths with real local credentials.
- Add instrument metadata mapping depth.

## Phase D - Paper Trading

Planned:

- Expand paper evidence and reconciliation.
- Compare expected previews against simulated and later broker-export evidence.
- Keep all paper output local and auditable.

## Phase E - Demo Execution With Explicit Approval

Future only. Requires a separate design review, idempotency, arming, kill
switch, reconciliation, and operator approval flow.

## Phase F - Live Execution

Future only after repeated paper acceptance and a separate safety review. Live
execution is not implemented in this build.
