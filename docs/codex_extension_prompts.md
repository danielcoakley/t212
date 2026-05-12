# Codex Extension Prompts

## Add a New Data Provider

"Add a new provider adapter behind `data.providers.base.ProviderClient`.
It must return schema-valid empty data when credentials are missing, cache
raw payloads, produce UTC timestamps, and include mocked HTTP tests."

## Modify Factor Calculations

"Update the quality/value/momentum/dividend factor definitions while
preserving point-in-time joins and adding focused factor tests."

## Change Ranking Weights

"Add a new versioned YAML strategy config and ensure backtests and
rebalance runs record the config hash."

## Alter Optimisation Constraints

"Extend `portfolio.constraints` with a pure function and property tests,
then wire it through the rebalancer preview output."

## Add a FastAPI Endpoint

"Add a typed route under `api/routers`, include Pydantic request and
response schemas, update tests with `TestClient`, and keep live actions
blocked unless armed."

## Expand the Dashboard

"Extend the FastAPI-served command centre under `src/isa_system/web`, add or
reuse typed API routes under `api/routers`, display UTC data in Europe/London
where applicable, and keep warnings and vetoes visible. The old Streamlit
dashboard is unused on `main`."
