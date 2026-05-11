# Agent Instructions

This repository is a local-first, safety-first UK Stocks and Shares ISA
operator cockpit. It is not an autonomous trading bot.

## Project Priorities

1. Keep the MVP focused on read-only broker context, recommendations, deep
   research gating, preview-only sizing, paper evidence, and operator safety.
2. Do not add live order submission paths unless explicitly requested and
   already guarded by mode, arming, kill switch, idempotency, and reconciliation.
3. Prefer small, shippable changes with tests over broad refactors.
4. Preserve the existing Python/FastAPI/Streamlit stack.
5. Keep provider credentials local. Never print, copy, commit, or expose
   `.env.local` values.

## Required Context

Before significant work, read:

- `docs/agent-coordination.md`
- `docs/implementation-roadmap.md`
- `docs/mvp-gap-analysis.md`
- `docs/roadmap.md`
- `README.md`
- Relevant source and tests for your workstream

## Workstream Rules

- You are not alone in the codebase. Other agents may be editing parallel
  workstreams.
- Do not revert changes you did not make.
- Stay inside your assigned file ownership where possible.
- If you need to touch shared files, keep edits narrow and document why.
- If you hit a blocker, document it and continue with another safe subtask.
- Add or update focused tests for behaviour changes.
- Add a concise handoff note under `docs/agent-coordination.md` when done.

## Safe Defaults

- Runtime mode is preview-first.
- Paper workflow can be expanded.
- Live remains disarmed by default.
- Buy/add preview eligibility requires broker validation and a non-expired
  `RESEARCH_PASSED` review.
- Convenience market-data feeds are not official point-in-time truth.
- Official-source work must preserve `available_at_utc` semantics.

## Common Checks

Use the local source tree explicitly when running tests:

```powershell
$env:PYTHONPATH='src'; python -m pytest -q
python -m ruff check .
python -m ruff format --check .
```

For narrower work, run the focused tests plus Ruff on touched files.

