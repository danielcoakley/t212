# Runbook

## Daily Checks

1. Run ingestion in preview mode and review provider warnings.
2. Confirm all storage timestamps are UTC and dashboard times are London time.
3. Check broker account, cash, positions, and pending orders.
4. Review stale-data warnings and catalyst blackout windows.
5. Review recommendation output as advisory context only, with risk and event
   vetoes visible before moving any idea to rebalance preview.
6. Do not submit live orders when reconciliation is stale.

## Live Read-Only Dashboard

The dashboard may connect to Trading 212 live account state using read-only GET
endpoints for account summary and positions. This is safe for operator context
only: it must not be confused with live trading. Keep `ISA_RUNTIME_MODE=preview`
unless deliberately testing paper mode, and keep live order submission disarmed.
Recommendation actions shown in the dashboard are also review-only; they do not
authorise paper or live submission by themselves.

Store credentials in `env.local`, `.env.local`, or the process environment. Do
not commit real credentials.

## Recommendation MVP Checks

1. Review holdings actions as prompts only: hold, add, trim, reduce, avoid, or
   watch labels require human review.
2. Treat wider-market scan results as convenience-feed discovery, not official
   point-in-time evidence or a guaranteed broker-accessible universe.
3. Confirm source freshness, missing-data warnings, risk checks, and catalyst
   vetoes before any reviewed idea enters rebalance preview.
4. If OpenAI/LLM rationale is configured, compare it with the deterministic
   fields and ignore it where it conflicts with rules, risk checks, or event
   vetoes.
5. If the OpenAI/LLM key is absent or the provider fails, continue with
   deterministic rationale only; do not block the cockpit solely because the
   explanation layer is unavailable.
6. Never copy a recommendation action directly into an order. Use the rebalance
   preview, paper workflow, and guarded live controls.

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
If an OpenAI/LLM provider fails or no key is configured, disable or degrade the
rationale panel and preserve deterministic recommendation output. The LLM layer
is optional and must not create orders, set targets, or override vetoes.
