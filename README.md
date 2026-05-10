# ISA System Starter

A local-first, Codex-assisted starter repository for a long-only,
buy-and-hold or multi-day trading system for a UK Stocks and Shares ISA
using Trading 212 for execution.

The starter prioritises safety, auditability, point-in-time correctness,
and operational simplicity. It is not financial, tax, or investment
advice.

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[dev]"
python -m pytest -q
python -m isa_system.smoke_test
```

Start the local control plane:

```powershell
uvicorn isa_system.api.main:app --host 127.0.0.1 --port 8000
```

Start the dashboard:

```powershell
streamlit run src/isa_system/dashboard/app.py
```

## Configuration

Copy `.env.example` to `.env.local` and fill only the keys you intend to
use. The smoke test, tests, API, and dashboard run without external API
keys. Services bind to `127.0.0.1` by default.

Config examples live under `configs/`. Real broker-specific identifiers,
account values, and secrets must stay outside tracked files.

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

See `docs/` for runbooks, data-source caveats, ISA notes, roadmap, and
extension prompts.
