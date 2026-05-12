# Portfolio Intelligence Runbook

## Startup Order

1. Optionally start OpenBB API on `http://127.0.0.1:6900`.
2. Optionally start OpenBB MCP on `http://127.0.0.1:8001`.
3. Start the portfolio intelligence API:

```powershell
python scripts/run_api.py
Invoke-RestMethod http://127.0.0.1:8002/health
```

Open the local command centre at `http://127.0.0.1:8002/`. The Streamlit
dashboard is unused on `main`.

## Daily Run

Use the deterministic offline smoke path first:

```powershell
$env:PYTHONPATH='src'; python scripts/smoke_test.py
```

Artifacts are written under `artifacts/smoke`:

- `latest_candidates.csv`
- `top10.csv`
- `research_reports/`
- `watchlist.csv`
- `rebalance_proposals.json`
- `order_previews.json`
- `run_summary.json`

## API Workflow

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8002/discovery/run -Body '{"use_fixtures":true}' -ContentType 'application/json'
Invoke-RestMethod -Method Post http://127.0.0.1:8002/enrichment/run -Body '{"use_fixtures":true}' -ContentType 'application/json'
Invoke-RestMethod -Method Post http://127.0.0.1:8002/scores/run -Body '{"limit":10}' -ContentType 'application/json'
Invoke-RestMethod -Method Post http://127.0.0.1:8002/research/run-top10
Invoke-RestMethod -Method Post http://127.0.0.1:8002/rebalance/propose
```

Or run all steps:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8002/orchestrator/run
```

## Weekly Review

Inspect:

- `GET /candidates/top10`
- `GET /thesis/watchlist`
- `GET /research/reports/latest`
- `POST /health-check/run`
- `GET /health-check/latest`
- `GET /rebalance/latest`
- `GET /workspace/widgets.json`

## Holdings Health Check

Use the Portfolio tab or the API to produce an on-demand report for current
holdings. With `OPENAI_API_KEY` configured, the report uses
`OPENAI_HEALTH_CHECK_MODEL` (`gpt-5.5` by default) with medium reasoning, or
high reasoning for detailed mode. It does not use `o3-deep-research`. Without a
key, it stores a conservative local fallback report so history, acceptance, and
tests still work offline.

The report includes bear, base, and bull price targets plus a review-only
recommended action per holding. The operator can accept the generated targets,
adjust them, and carry forward the chosen action. These updates are stored in
history and do not create broker order authority.

## Selected-Stock Deep Valuation

Use the Portfolio tab to select one or more holdings, then run Deep Valuation.
The default model is `OPENAI_STOCK_VALUATION_MODEL=gpt-5.5` with high
reasoning. Maximum Depth uses `OPENAI_STOCK_VALUATION_MAX_REASONING_EFFORT=xhigh`.
The optional Source-heavy Research Pack uses
`OPENAI_SOURCE_RESEARCH_MODEL=o3-deep-research` only when explicitly selected
or when `OPENAI_ENABLE_O3_SOURCE_RESEARCH=true`.

The API endpoint is `POST /portfolio/deep-valuation` with `symbols`,
`maximum_depth`, and `source_heavy`. Empty selections are rejected before any
model call.

## Common Checks

```powershell
$env:PYTHONPATH='src'; python -m pytest -q
python -m ruff check .
python -m ruff format --check .
$env:PYTHONPATH='src'; python -m mypy
```

Mypy currently has documented legacy warnings in older MVP modules; see
`docs/implementation_status.md`.

## Disable Everything

Stop the local API process. Leave `LIVE_TRADING_ENABLED=false`. There is no
live Trading 212 order submission route in this build.
