# Portfolio Intelligence Implementation Plan

This plan tracks the phased build for the local-first ISA portfolio intelligence
system. The existing `isa_system` package is the single implementation home; it
will be adapted in place so there is one coherent system rather than parallel
packages.

## Principles

- Keep every phase runnable and testable offline.
- Prefer deterministic rule-based behaviour when external providers or API keys
  are missing.
- Treat OpenBB and Finviz as optional inputs that must fail gracefully.
- Keep Trading 212 read-only plus order preview only; no live order submission
  route is introduced in this build.
- Store uncertain provider paths and future execution seams in central modules
  rather than scattering them through the codebase.

## Phase Sequence

1. Bootstrap project package, configuration, scripts, health API, and OpenBB
   connectivity check.
2. Add polite Finviz discovery with local caching, fixtures, candidate
   deduplication, and discovery endpoints.
3. Add OpenBB enrichment wrapper with centralised endpoint definitions, cache,
   mocked/offline-friendly behaviour, and data quality scoring.
4. Add factor scoring, composite opportunity ranking, explanations, top 10
   selection, and score endpoints.
5. Add thesis models, deterministic thesis generation, decision rules, lifecycle
   tracking, and thesis endpoints.
6. Add structured research reports that update thesis fields and save Markdown
   plus SQLite records.
7. Add portfolio holdings, comparison, risk constraints, rebalance proposal
   logic, and rationale-based proposal endpoints.
8. Add Trading 212 read-only models/client helpers and order preview only.
9. Add OpenBB Workspace-compatible widget metadata and JSON endpoints.
10. Add end-to-end orchestration, offline smoke artifacts, and full-pipeline
    API/CLI entry points.
11. Complete docs and hardening checks.

## Current Scope Assumption

The existing repository is not blank. The implementation keeps and adapts the
current `isa_system` codebase, preserving safety-first preview behaviour while
adding the requested portfolio intelligence workflow.
