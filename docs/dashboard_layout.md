# Dashboard Layout

The MVP dashboard is intentionally small. The primary operator workflow is:
review account state, inspect the screener funnel, review one consolidated
recommendation queue, run a deep research gate for any buy/add candidate,
generate preview-only sizing for eligible rows, then inspect management and
safety status before any paper or later live workflow. Legacy holdings,
valuation, catalyst, factor, rebalance, and audit views are kept behind one
Advanced page, not as front-stage tabs.

All storage timestamps remain UTC. Streamlit converts display timestamps to
Europe/London.

## Primary MVP Screens

| Screen area | Primary widgets | Purpose | Key actions |
| --- | --- | --- | --- |
| Sidebar | Workflow selector, screening scope, mode badge, broker status, environment, kill-switch indicator, London time, cache window, next scheduled refresh, broker warnings | Keep operational state visible before any analysis | Add manual symbols, include/exclude T212 scan, refresh market data manually, confirm preview-only mode, inspect warnings |
| Overview | Account health, cash and invested value, 20% algo sleeve / 80% core sleeve summary, top holdings, concentration, currency exposure, unrealised P/L, next action | Let the operator understand current portfolio state without reading raw tables | Move to Recommendations when broker context is healthy; resolve broker warnings first |
| Screener | Additive funnel, stage counts, removal reasons, passed/removed rows, top deep research candidates, loading progress | Show how the broad Trading 212 universe becomes a shortlist instead of hiding the workings | Inspect universe filters, evidence blockers, event vetoes, and shortlist candidates |
| Recommendations | One consolidated holdings and screener table with symbol, source, action, score, broker validation, research status, preview eligibility, blockers, next step, valuation and technical context, score chart, loading progress | Replace duplicated tabs/tables with one review queue for holdings and broad-market candidates | Choose candidates for deep research or identify blockers before preview sizing |
| Research Review | Candidate selector, current evidence, latest thesis, bull/base/bear targets, drivers, risks, evidence gaps, final score, decision, expiry, loading progress | Enforce OpenAI-backed thesis validation before buy/add preview sizing | Run deep research, inspect evidence gaps, accept only `RESEARCH_PASSED` rows into preview |
| Preview | Eligible recommendations, not-yet-eligible blockers, preview-only sizing, target weights, notional estimates, cost estimates, warnings | Keep sizing and cost context separate from recommendation scoring and deep research | Select eligible rows and build preview-only sizing; no orders are submitted |
| Management | Runtime mode, live arming, kill switch, broker status, operational status model, cache freshness, provider configuration, safety checklist, next required safe action, blocked future capabilities | Give the operator one read-only control surface for setup, stale/missing state, and safety status | Confirm provider gaps, deep research availability, paper readiness, live guardrails, and the next safe operator action |
| Advanced | Single diagnostic selector for holdings, valuation, catalysts, legacy rebalance, factor attribution, and audit logs | Preserve detail for audit/development without crowding the operator workflow | Inspect raw support tables when troubleshooting or validating data quality |

## Recommendation Queue Columns

| Column | Source | Purpose | Guardrail |
| --- | --- | --- | --- |
| `action` | Deterministic recommendation service | Shows HOLD, WATCH, REVIEW_BUY, REVIEW_SELL, or BLOCKED | Action labels never submit orders |
| `composite`, component scores | Valuation, technical, sentiment/news, catalyst evidence | Shows why a row rose or fell in the queue | Missing evidence is visible and conservative |
| `broker_validation` and `broker_ticker` | Trading 212 `/equity/metadata/instruments` and holdings | Confirms a plausible broker symbol for holdings and screener candidates | Metadata match is not ISA, liquidity, or order approval |
| `research_review_status` | Persisted deep research reviews | Shows whether a buy/add idea has a valid review | BUY/add rows require non-expired `RESEARCH_PASSED` |
| `preview_eligible` | Recommendation hand-off service | Shows whether a selected row can enter preview-only sizing | Sells/trims do not need a new deep review; buys/adds do |
| `preview_blockers` | Risk flags, broker validation, research gate | Shows why a row cannot be preview-sized | Blockers must be resolved, not hidden in another tab |
| Valuation and technical fields | yfinance/convenience feeds and current calculations | Gives immediate context for P/E, yield, RSI, momentum | Convenience feed caveats remain visible |

## Advanced Diagnostics

| Diagnostic surface | Status | Why it is not front-stage |
| --- | --- | --- |
| Holdings table | Available through Advanced | The Overview already shows portfolio state; raw holding rows are for checking. |
| Valuation page | Available through Advanced | Key valuation and technical fields now appear in the recommendation queue; deeper valuation remains useful for diagnostics. |
| Catalysts page | Available through Advanced | Catalyst blockers surface in the screener and recommendation queue; raw event feeds remain for validation. |
| Legacy rebalance page | Available through Advanced | The MVP path creates preview-only sizing from selected eligible recommendations. |
| Factor attribution | Available through Advanced | Component scores are visible in the queue; full factor diagnostics remain for audit. |
| Audit logs | Available through Advanced | Research reviews and preview attempts still persist audit records; raw audit browsing is not the first screen. |

## UI Roadmap

| Phase | Status | Screens and widgets | Done when |
| --- | --- | --- | --- |
| 1. Simplify operator workflow | Done | Core Streamlit shell: Overview, Screener, Recommendations, Deep Research, Preview, Advanced | Primary UI no longer presents repeated tables as separate tabs. |
| 2. Twice-daily dashboard cache | Done, then expand | Market-session cache keyed to London open and US open, ignored disk cache under `artifacts/dashboard_cache/`, manual refresh button, loading progress | Navigation and app restarts reuse cached broker/recommendation workflow data instead of rebuilding expensive feeds every page change. |
| 3. T212 broker-universe screener | Done, then expand | Screener page sourced from Trading 212 metadata with YAML fallback and additive filter stages | Live metadata can seed 250 instruments, filtered and capped to top 50 display rows, with removal reasons visible. |
| 4. Deep research gate | In progress | Research Review page and persisted review status in queue | BUY/add rows cannot become preview-eligible without non-expired `RESEARCH_PASSED`. |
| 5. Recommendation-to-preview workflow | In progress | Dedicated Preview page for selected eligible rows and estimated costs | Preview rows show side, target weight, notional, costs, warnings, and blockers. |
| 6. Management and safety status | In progress | Read-only Management page with runtime mode, live arming, kill switch, cache window, cache freshness, provider status, broker read-only state, deep research availability, safety checklist, and next safe action | Operator can see setup gaps, stale/missing state, and live guardrails without leaving the dashboard. |
| 7. Paper reconciliation | Planned | Paper fill log, expected vs simulated fills, broker reconciliation comparison | Paper cycles can be reviewed and replayed before micro-live consideration. |
| 8. Official-source enrichment | Planned | SEC, Companies House, RNS, NSM, FRED status and point-in-time diagnostics | Recommendation evidence shows official-source freshness and rejects look-ahead data. |

## Visualisation Backlog

| Visual | Source | Purpose |
| --- | --- | --- |
| Account health strip | Trading 212 account summary and positions | Make broker state, cash, and sleeves immediately visible. |
| Concentration and currency charts | Trading 212 positions | Show top holdings and USD/GBP exposure. |
| Recommendation score bars | Recommendation queue | Compare review actions and score strength without opening raw tables. |
| Component heatmap | Recommendation queue | Show fundamental, technical, sentiment, and catalyst contributions. |
| Research target cards | Deep research review JSON | Show bull/base/bear cases and final review decision. |
| Preview sizing table | Recommendation preview service | Show target weights, notional, costs, and remaining blockers. |
