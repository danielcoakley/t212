# ISA Portfolio Intelligence

This is one local-first, safety-first UK Stocks and Shares ISA portfolio
intelligence system. The existing `isa_system` package is the implementation
home for the Finviz discovery, OpenBB enrichment, thesis tracking, portfolio
comparison, and Trading 212 read-only/order-preview workflow.

It is not a day-trading bot, it is not investment advice, and it does not
implement live Trading 212 order submission.

Startup order:

1. Optionally start OpenBB API on `http://127.0.0.1:6900`.
2. Optionally start OpenBB MCP on `http://127.0.0.1:8001`.
3. Start this API on `http://127.0.0.1:8002` with `python scripts/run_api.py`.
4. Check local health with `Invoke-RestMethod http://127.0.0.1:8002/health`.

Local port map:

| Service | URL |
| --- | --- |
| OpenBB API | `http://127.0.0.1:6900` |
| OpenBB MCP | `http://127.0.0.1:8001` |
| ISA Portfolio Intelligence API | `http://127.0.0.1:8002` |

Safety notes:

- Live Trading 212 order submission is not implemented.
- Trading 212 support is read-only plus order preview only.
- Order previews require manual review and approval outside this app.
- Tests and smoke scripts run without real API keys.
- Keep `.env.local` local and never commit secrets.

A local-first, Codex-assisted starter repository for a long-only,
buy-and-hold or multi-day trading system for a UK Stocks and Shares ISA
using Trading 212 for execution.

The starter prioritises safety, auditability, point-in-time correctness,
and operational simplicity. It is not financial, tax, or investment
advice.

## Local First Run

Use this path for a safe first run on a local workstation. It does not require
external API keys, Trading 212 credentials, hosted auth, or live trading.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[dev]"
Copy-Item .env.example .env.local
python -m pytest -q
python -m isa_system.smoke_test
```

Start the local API in one terminal:

```powershell
python scripts/run_api.py
Invoke-RestMethod http://127.0.0.1:8002/health
```

Start the dashboard in another terminal:

```powershell
python -m streamlit run src/isa_system/dashboard/app.py
```

Then open the Streamlit URL printed by the command, usually
`http://localhost:8501`. Begin on Overview, then use Management to confirm
runtime mode, broker status, provider gaps, cache freshness, and live guardrails.

Expected first-run state:

- `ISA_RUNTIME_MODE=preview` and the API control plane starts disarmed.
- No Trading 212 credentials means the dashboard shows synthetic or empty local
  context with a broker setup warning.
- No `OPENAI_API_KEY` means deep research is unavailable, so buy/add rows cannot
  receive the `RESEARCH_PASSED` gate needed for preview approval.
- Health Check still runs without `OPENAI_API_KEY`, but it uses conservative
  local fallback targets instead of the configured OpenAI deep research model.
- Recommendation and preview pages are review-only. They do not submit orders.

## Configuration

Copy `.env.example` to `env.local` or `.env.local`; both are loaded, with
`.env.local` used in the quick-start example. Fill only the keys you intend to
use. The smoke test, tests, API, and dashboard run without external API keys.
Services bind to `127.0.0.1` by default.

Keep real broker-specific identifiers, account values, and secrets outside
tracked files. Never paste `.env.local` contents into issues, docs, commits, or
agent prompts.

### Provider Setup

| Provider | Variables | When to configure | First-run impact if blank |
| --- | --- | --- | --- |
| Trading 212 | `TRADING212_API_KEY`, `TRADING212_API_SECRET`, `TRADING212_ENVIRONMENT` | Configure for read-only account summary, positions, active orders, and broker universe context. Use `demo` first; use `live` only when the operator intentionally wants live account context. | Dashboard remains safe with `not_configured` broker status. |
| OpenAI | `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_HEALTH_MODEL` | Configure when the pilot needs the deep research gate for buy/add candidates or on-demand holdings health reports. `OPENAI_HEALTH_MODEL` defaults to `o3-deep-research`. | Buy/add preview approval remains blocked because no non-expired `RESEARCH_PASSED` review can be produced. Health Check falls back to local scenario targets. |
| Alpha Vantage, FMP, FRED | `ALPHA_VANTAGE_API_KEY`, `FMP_API_KEY`, `FRED_API_KEY` | Optional convenience enrichment for prices, fundamentals, and macro context. | The app uses local fallbacks or empty provider results where safe. |
| Companies House, SEC EDGAR | `COMPANIES_HOUSE_API_KEY`, `SEC_USER_AGENT` | Optional official-source identity and filing context. SEC asks automated clients to identify themselves. | Official-source coverage stays partial. |
| Sentiment overlays | `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `X_BEARER_TOKEN` | Optional, low-weight sentiment enrichment. | Sentiment stays disabled and must not block the local cockpit. |

Trading 212 credentials are used by the current dashboard for read-only GET
context. Setting `TRADING212_ENVIRONMENT=live` allows live account reads, but it
does not arm live submission. During the pilot, leave `ISA_RUNTIME_MODE=preview`,
do not call live arming endpoints, and treat all recommendation and preview
output as operator review material.

## Pilot Checklist

Use `docs/pilot-checklist.md` for an auditable pilot acceptance checklist. The
checklist is designed for local operation only: install, safe startup, provider
readiness, Trading 212 read-only context, recommendation review, deep research
gate behaviour, preview-only sizing, paper simulation, and evidence capture.

## Architecture Summary

The system is split into four planes:

| Plane | Purpose |
| --- | --- |
| Research/data | Ingest raw and curated prices, fundamentals, filings, events, and macro data into a DuckDB/Parquet lake. |
| Strategy/risk | Compute point-in-time factors, rankings, target weights, constraints, costs, and warnings. |
| Execution/control | Preview, paper trade, reconcile, arm or disarm live mode, and protect against duplicates. |
| Operator/dashboard | Show holdings, catalysts, previews, audit logs, and mode state in Europe/London display time. |

Trading 212 is treated as the execution and reconciliation source. yfinance,
Alpha Vantage, and FMP are convenience feeds for research and enrichment.
SEC EDGAR, Companies House, LSE RNS, and FCA NSM are treated as official
filing or event validation layers where practical.

OpenBB is kept as an updateable upstream checkout under `vendor/OpenBB`.
App code must call it only through `isa_system.openbb_adapter`. To update
OpenBB, run `scripts/update_openbb.ps1`, then keep the updated
`configs/openbb.lock.json` only after compatibility tests pass.

See `docs/` for runbooks, data-source caveats, ISA notes, roadmap, and
extension prompts.
