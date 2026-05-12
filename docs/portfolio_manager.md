# Portfolio Manager

The portfolio manager asks whether a candidate improves the portfolio, not only
whether the candidate is interesting.

## Comparison Logic

For BUY_NOW candidates, the manager compares against cash and the weakest
existing holding. It can propose:

- BUY_NEW
- ADD_TO_EXISTING
- TRIM
- SELL_THESIS_BROKEN
- SELL_TARGET_REACHED
- REPLACE_WITH_CANDIDATE
- HOLD
- WATCHLIST_WAIT_ENTRY
- WATCHLIST_WAIT_CATALYST

## Anti-Churn Rules

No rebalance is proposed for small rank changes, poor entries, unresolved
catalysts, weak data quality, cooldown windows, or non-material score
differences.

## Material Superiority

Replacement requires higher conviction, better upside/downside, and a weaker or
stale existing holding. Every proposal carries rationale, risks, confidence,
and `manual_approval_required=true`.
