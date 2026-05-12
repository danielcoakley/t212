# Thesis Lifecycle

The core object is an investment thesis, not a ticker.

## Statuses

- DRAFT
- ACTIVE_HOLDING
- WATCHLIST_WAIT_ENTRY
- WATCHLIST_WAIT_CATALYST
- REJECTED
- NEEDS_REVIEW
- BROKEN
- TARGET_REACHED
- CLOSED

## Review Triggers

- Entry price becomes attractive.
- Catalyst confirms or invalidates the thesis.
- Price target or review level is reached.
- Thesis data becomes stale.
- Portfolio comparison shows a materially better opportunity.
- Material risk event appears.

## Persistence

Thesis records are stored in SQLite table `investment_theses` and include
confidence, conviction, data quality, target/review levels where available,
next review date, rationale, and missing-data notes.
