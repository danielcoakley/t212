# Runbook

## Daily Checks

1. Run ingestion in preview mode and review provider warnings.
2. Confirm all storage timestamps are UTC and dashboard times are London time.
3. Check broker account, cash, positions, and pending orders.
4. Review stale-data warnings and catalyst blackout windows.
5. Do not submit live orders when reconciliation is stale.

## Live Read-Only Dashboard

The dashboard may connect to Trading 212 live account state using read-only GET
endpoints for account summary and positions. This is safe for operator context
only: it must not be confused with live trading. Keep `ISA_RUNTIME_MODE=preview`
unless deliberately testing paper mode, and keep live order submission disarmed.

Store credentials in `env.local`, `.env.local`, or the process environment. Do
not commit real credentials.

## Paper to Micro-Live Promotion

1. Run the smoke test and synthetic integration tests.
2. Paper trade for at least one full rebalance cycle.
3. Compare paper fills, preview costs, and broker constraints.
4. Enable live mode only after a human review of configs and limits.
5. Start with micro-live order sizes and submit one small batch at a time.

## Kill Switch

The kill switch blocks live submit paths even when live mode is armed.
Use it after unexpected broker responses, stale data, failed reconciliation,
major market events, or any suspected duplicate-order risk.

## Reconciliation

1. Pull Trading 212 positions and order history.
2. Compare intended batch orders to broker order ids and fills.
3. Record a broker reconciliation row and append an audit log entry.
4. Keep live mode disarmed until unresolved differences are explained.

## Fallback Procedures

If an external provider fails, the starter returns schema-valid empty
results where safe. Do not fill missing official filing timestamps from
convenience feeds without marking the precision and assumption.
