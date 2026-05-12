# Pilot Checklist

Use this checklist for a local, preview-first pilot cycle. It is designed to
collect evidence before any future micro-live discussion.

## 1. Local Setup

- Create a virtual environment.
- Install the project with development dependencies.
- Copy `.env.example` to `.env.local`.
- Keep real keys and account identifiers out of commits, issues, docs, and
  agent prompts.
- Run the test suite.
- Run the smoke test.

## 2. Safe Startup

- Start the FastAPI control plane on `127.0.0.1`.
- Open the command centre at `http://127.0.0.1:8002/`.
- Confirm `ISA_RUNTIME_MODE=preview`.
- Confirm live arming is false.
- Confirm the kill switch is clear or intentionally enabled.
- Review provider/configuration gaps from the command centre and API health
  endpoints. The old Streamlit dashboard is unused on `main`.

## 3. Provider Readiness

- Trading 212 credentials are optional for first run and required only for
  read-only account and broker-universe context.
- Use `TRADING212_ENVIRONMENT=demo` first.
- Use `TRADING212_ENVIRONMENT=live` only when intentionally reading live account
  state.
- Configure `OPENAI_API_KEY` only when the pilot needs buy/add deep research
  reviews, Portfolio Health Check, or selected-stock Deep Valuation.
- Keep `OPENAI_ENABLE_O3_SOURCE_RESEARCH=false` unless an explicit
  source-heavy selected-stock research pack is needed.
- Leave optional convenience providers blank until a pilot needs their data.

## 4. Recommendation Review

- Review the Overview page for broker/account context.
- Review the Screener funnel for source warnings and filter removals.
- Review the Recommendations page for action, broker validation, blockers,
  research gate status, and preview eligibility.
- Treat all recommendation rows as review-only.
- Do not copy a recommendation directly into an order.

## 5. Deep Research Gate

- For buy/add candidates, run a deep research review only after broker
  validation and source warnings are understood.
- If `OPENAI_API_KEY` is absent, buy/add preview approval should remain blocked.
- Accept only non-expired `RESEARCH_PASSED` reviews into preview sizing.
- Keep evidence gaps and risks visible in the review notes.

## 6. Preview And Paper Evidence

- Build preview-only sizing for eligible rows.
- Check notional, target weight, estimated costs, and blockers.
- Run or inspect paper simulation where available.
- Record expected-vs-simulated differences.
- Keep live submission out of scope for the pilot cycle.

## 7. Acceptance Evidence

- Save or record the date/time of the pilot cycle.
- Record provider readiness and known gaps.
- Record recommendation rows reviewed and why they were accepted or rejected.
- Record deep research review ids where applicable.
- Record preview warnings, estimated costs, and paper simulation warnings.
- Record any blocker that prevents moving to a later paper persistence or
  reconciliation slice.

## Stop Conditions

Stop the pilot cycle and do not proceed if:

- Broker identity or instrument mapping is unclear.
- Source freshness or point-in-time availability is questionable.
- Deep research is unavailable for a buy/add candidate.
- Preview blockers remain unresolved.
- Reconciliation or duplicate-order protection is stale or untested.
- The operator is uncertain whether a page is preview-only or live-capable.

