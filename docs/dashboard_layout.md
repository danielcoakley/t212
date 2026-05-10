# Dashboard Layout

| Screen area | Primary widgets | Purpose | Key actions |
| --- | --- | --- | --- |
| Header | Mode badge, kill-switch indicator, last refresh, London time | Make operational state obvious | Arm, disarm, switch preview or paper mode |
| Portfolio overview | Equity, cash, core sleeve, algo sleeve, drawdown, exposure | Show whether the system is inside mandate | Review sleeve drift |
| Holdings | Symbol, value, quantity, currency, unrealised P/L, concentration, stale flag, thesis tag | Explain current live exposures and risk concentration | Block ticker, inspect rationale |
| Catalysts | Earnings, filings, RNS/NSM validations, blackout windows | Avoid buying near unmanaged events | Open source reference, apply event veto |
| Rebalance preview | Current vs target, trades, costs, SDRT, FX, warnings | Review before any order batch | Export preview, paper submit, live submit when armed |
| Factor attribution | Factor z-scores, sector-neutral adjustments, missing data diagnostics | Explain ranks and missing-data policy | Change config in a versioned way |
| Audit and status | Audit chain, idempotency keys, heartbeats, broker reconciliation | Support replayability and incident review | Filter logs, reconcile, trigger kill switch |

## Visualisation Backlog

| Visual | Source | Purpose |
| --- | --- | --- |
| Holdings allocation chart | Trading 212 read-only positions | Show concentration and sleeve context at a glance. |
| Currency exposure chart | Trading 212 position currencies | Make USD/GBP exposure visible for FX-cost awareness. |
| Cash and invested fraction | Account summary and positions | Show deployment, cash buffer, and preview readiness. |
| Unrealised P/L bar chart | Position wallet impact where available | Highlight current risk and winners/losers without implying trade advice. |
| Rebalance impact table | Local preview and cost model | Show turnover, SDRT, FX, slippage, vetoes, and warnings before paper/live steps. |
