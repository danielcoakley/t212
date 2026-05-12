# Trading 212 Safety

Trading 212 is execution infrastructure only. It is not the research source.

## Current Build

- Read-only account route: `GET /broker/account`
- Read-only positions route: `GET /broker/positions`
- Local preview route: `POST /orders/preview`
- No live order submission route exists.
- Legacy `/rebalances/submit` has been removed and returns 404.

## Order Preview

Order preview estimates direction, quantity where computable, trade value, FX
impact, SDRT placeholder, cash buffer effect, target weight, risk warnings, and
a deterministic duplicate order hash.

Preview output is not an order. Manual approval is always required.

## Future Work

Any live execution must be a separate future phase after paper evidence,
reconciliation, arming, kill switch, idempotency, and operator runbook review.
