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

### Fixed

- Ensured file-backed SQLite creates its parent artifact directory on first run.
- Recovered from an initial shared-checkout worker dispatch by preserving useful
  work in split commits and moving ongoing work into explicit isolated
  worktrees.

### In Progress

- Management diagnostics phase 2.
- Local onboarding and pilot setup.
- Recommendation display UX and evidence clarity.
- Pilot paper workflow shell.
- MVP QA and route guardrails.
