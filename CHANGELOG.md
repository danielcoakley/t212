# Changelog

All notable project changes should be recorded here.

## Unreleased

### Added

- Created implementation roadmap, MVP gap analysis, and agent coordination docs.
- Added a read-only Streamlit Management page for runtime mode, live arming,
  kill switch, broker status, cache window, provider configuration, and safety
  checklist.
- Added a parallel execution plan with five active MVP workstreams.
- Added root agent instructions and TODO tracking for parallel Codex work.
- Added local first-run and provider setup guidance plus a local pilot
  checklist.
- Added recommendation queue scan columns for review state, broker/research
  gates, evidence coverage, and source caveats.
- Added notional-only paper simulation support for recommendation preview rows.
- Added offline MVP guardrail regression tests for preview-only workflow,
  blocked live submit, missing providers, and management helper safety rows.
- Expanded the Management page with provider readiness, cache freshness,
  broker read-only state, live guardrails, and next safe action diagnostics.
- Added a schema-light pilot paper workflow summary service, API route, and
  Preview page display for expected-vs-simulated paper evidence.
- Added source freshness diagnostics for dashboard cache/source age and provider
  caveats on Management and Recommendations surfaces.
- Added durable paper-cycle persistence tables, deterministic paper intent and
  simulated fill IDs, and explicit save/reload paper-cycle API routes.
- Added a side-effect-free operator report service and read-only API route for
  account, recommendation, research, preview, pilot-paper, and management
  evidence summaries.

### Fixed

- Ensured file-backed SQLite creates its parent artifact directory on first run.
- Recovered from an initial shared-checkout worker dispatch by preserving useful
  work in split commits and moving ongoing work into explicit isolated
  worktrees.

### Next

- Connect operator reports to persisted paper cycles.
- Add paper cycle review surface.
- Instrument identity mapping for broker ticker, research symbol, and ISIN.
