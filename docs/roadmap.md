# Roadmap

| Month | Milestone | Outcome |
| --- | --- | --- |
| 1 | Stabilise local data lake and smoke tests | Repeatable offline research loop, PIT checks, provider mocks |
| 2 | Paper trading and reconciliation | Broker state snapshots, duplicate guards, paper fill comparisons |
| 3 | Controlled micro-live readiness | Human arming, runbook rehearsals, dashboard review, small live batches |

```mermaid
gantt
    title Three-month ISA System Roadmap
    dateFormat  YYYY-MM-DD
    section Month 1
    Data lake layout and provider mocks      :a1, 2026-05-11, 14d
    PIT factor tests and smoke backtest      :a2, after a1, 14d
    section Month 2
    Paper broker and reconciliation soak     :b1, 2026-06-08, 21d
    Dashboard operator workflow             :b2, 2026-06-15, 14d
    section Month 3
    Micro-live controls and audit rehearsals :c1, 2026-07-06, 21d
    Human validation and go/no-go review     :c2, 2026-07-27, 7d
```
