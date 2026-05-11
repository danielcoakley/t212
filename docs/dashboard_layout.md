# Dashboard Layout

The MVP dashboard is intentionally small. The primary operator workflow is:
review account state, inspect one consolidated recommendation queue, run a deep
research gate for any buy/add candidate, then generate preview-only sizing for
eligible rows. Legacy holdings, valuation, catalyst, factor, rebalance, and
audit views are kept as advanced diagnostics in code, not as front-stage tabs.

All storage timestamps remain UTC. Streamlit converts display timestamps to
Europe/London.

## Primary MVP Screens

| Screen area | Primary widgets | Purpose | Key actions |
| --- | --- | --- | --- |
| Sidebar | Workflow selector, mode badge, broker status, environment, kill-switch indicator, London time, broker warnings | Keep operational state visible before any analysis | Refresh broker state, confirm preview-only mode, inspect warnings |
| Overview | Account health, cash and invested value, 20% algo sleeve / 80% core sleeve summary, top holdings, concentration, currency exposure, unrealised P/L, next action | Let the operator understand current portfolio state without reading raw tables | Move to Recommendations when broker context is healthy; resolve broker warnings first |
| Recommendations | One consolidated holdings and screener table with symbol, source, action, score, broker validation, research status, preview eligibility, blockers, next step, valuation and technical context | Replace duplicated tabs/tables with one review queue for holdings and broad-market candidates | Run deep research for buy/add ideas, select eligible rows, build preview-only sizing |
| Research Review | Candidate selector, current evidence, latest thesis, bull/base/bear targets, drivers, risks, evidence gaps, final score, decision, expiry | Enforce OpenAI-backed thesis validation before buy/add preview sizing | Run deep research, inspect evidence gaps, accept only `RESEARCH_PASSED` rows into preview |

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
| Holdings table | Available as support module | The Overview already shows portfolio state; raw holding rows are for checking. |
| Valuation page | Available as support module | Key valuation and technical fields now appear in the recommendation queue; deeper valuation remains useful for diagnostics. |
| Catalysts page | Available as support module | Catalyst blockers surface in the recommendation queue; raw event feeds remain for validation. |
| Rebalance page | Available as support module | The MVP path creates preview-only sizing from selected eligible recommendations. |
| Factor attribution | Available as support module | Component scores are visible in the queue; full factor diagnostics remain for audit. |
| Audit logs | Available as support module | Research reviews and preview attempts still persist audit records; raw audit browsing is not the first screen. |

## UI Roadmap

| Phase | Status | Screens and widgets | Done when |
| --- | --- | --- | --- |
| 1. Simplify operator workflow | Done | Three-screen Streamlit shell: Overview, Recommendations, Research Review | Primary UI no longer presents repeated tables as separate tabs. |
| 2. T212 broker-universe screener | In progress | Recommendations queue sourced from Trading 212 metadata with YAML fallback | Live metadata can seed 250 instruments, filtered and capped to top 50 display rows. |
| 3. Deep research gate | In progress | Research Review page and persisted review status in queue | BUY/add rows cannot become preview-eligible without non-expired `RESEARCH_PASSED`. |
| 4. Recommendation-to-preview workflow | In progress | Selected eligible rows produce preview-only sizing and estimated costs | Preview rows show side, target weight, notional, costs, warnings, and blockers. |
| 5. Paper reconciliation | Planned | Paper fill log, expected vs simulated fills, broker reconciliation comparison | Paper cycles can be reviewed and replayed before micro-live consideration. |
| 6. Official-source enrichment | Planned | SEC, Companies House, RNS, NSM, FRED status and point-in-time diagnostics | Recommendation evidence shows official-source freshness and rejects look-ahead data. |

## Visualisation Backlog

| Visual | Source | Purpose |
| --- | --- | --- |
| Account health strip | Trading 212 account summary and positions | Make broker state, cash, and sleeves immediately visible. |
| Concentration and currency charts | Trading 212 positions | Show top holdings and USD/GBP exposure. |
| Recommendation score bars | Recommendation queue | Compare review actions and score strength without opening raw tables. |
| Component heatmap | Recommendation queue | Show fundamental, technical, sentiment, and catalyst contributions. |
| Research target cards | Deep research review JSON | Show bull/base/bear cases and final review decision. |
| Preview sizing table | Recommendation preview service | Show target weights, notional, costs, and remaining blockers. |
