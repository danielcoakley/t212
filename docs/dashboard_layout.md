# Dashboard Layout

The dashboard is the operator cockpit for preview, paper, and guarded live
workflows. It should make mode, data freshness, broker state, valuation
context, and vetoes visible before any rebalance action is considered.
The recommendation MVP adds a review-only layer for current holdings and
wider-market discovery, with any trade action routed through human review and
the existing rebalance preview controls.

## Current Screen Map

| Screen area | Primary widgets | Purpose | Key actions |
| --- | --- | --- | --- |
| Header and sidebar | Mode badge, broker status, broker environment, kill-switch indicator, last refresh, London time | Make operational state obvious before reviewing data | Refresh broker state, confirm preview or paper mode, disarm live mode |
| Overview | Equity, cash, cash weight, invested value, core sleeve, algo sleeve, concentration chart, currency exposure, unrealised P/L chart | Show whether the account is inside mandate and whether live broker data is available | Review sleeve drift, spot concentration or FX exposure |
| Holdings | Symbol, name, quantity, value, currency, unrealised P/L, weight, stale or missing-value warnings | Explain current live exposures and visible portfolio risk | Inspect holding, block ticker in strategy config, flag stale data |
| Catalysts | Provider events, headline context, blackout counts, official validation coverage, RNS/NSM/SEC/Companies House roadmap status | Avoid buying near unmanaged events or unverified announcements | Open source reference, apply event veto, review blackout |
| Recommendations | Holdings action queue, wider-market candidate feed, action label, confidence, deterministic rationale, optional OpenAI/LLM rationale, blockers, source freshness | Bring current positions and discovery candidates into a single review surface without creating orders | Mark reviewed, ignore candidate, exclude ticker, send reviewed idea to rebalance preview |
| Rebalance preview | Current vs preview target, sleeve blend, drift chart, turnover, cost components, SDRT, PTM, FX, slippage, paper fill simulation, warnings, safety gates | Review proposed changes before paper or live submission | Export preview, paper simulate, reject batch, arm live only outside this page |
| Factors | Starter composite score, valuation/technical proxies, factor coverage, missing data diagnostics, method guardrails | Explain provisional ranks and missing-data policy | Review strategy config, compare factor contribution, mark exclusions |
| Valuation | Broker value, research symbol, valuation multiples, SMA50/SMA200, RSI14, 1m/3m/6m/12m momentum, events, sentiment/news context, valuation freshness | Explain whether a live holding looks cheap, fair, expensive, technically strong, or missing coverage using point-in-time-ready inputs | Review valuation evidence, mark confidence, block stale valuation |
| Audit and status | Runtime mode, live arming, kill switch, broker positions, audit-chain rows, smoke artefacts, guardrail table | Support replayability and incident review | Filter logs, reconcile, trigger kill switch, export evidence |

## Valuation Page Widgets

| Widget | Data source | Purpose | Required guardrail |
| --- | --- | --- | --- |
| Valuation summary | Latest PIT price, factor output, valuation model result | Show current price, fair-value range, upside/downside, and valuation band | Show retrieved-at timestamp and confidence level. |
| Margin-of-safety tile | Fair-value estimate, current price, configured threshold | Highlight when a candidate is below, inside, or above the required safety margin | Never turn the tile into an automatic order recommendation. |
| Multiples comparison | FMP/Alpha Vantage fundamentals, official filing timestamps, peer set | Compare P/E, EV/EBITDA, P/B, sales growth, dividend yield, and sector medians | Mark non-official or stale fields and exclude unknown timestamps from PIT ranks. |
| DCF sensitivity grid | Local valuation assumptions and cash-flow inputs | Show sensitivity to discount rate, terminal growth, and base/bear/bull cases | Store assumptions with config hash and show scenario date. |
| Dividend valuation | Dividend history, payout ratio, dividend growth factor | Connect income quality to valuation for dividend-oriented configs | Warn on missing withholding-tax or dividend-currency assumptions. |
| Quality/value bridge | Quality, value, momentum, dividend, and sector-normalised factors | Explain how valuation contributes to the composite rank | Display missing-data policy and factor z-score direction. |
| Position valuation impact | Current holdings, target weights, valuation band | Show which live holdings are expensive, fair, cheap, or missing valuation coverage | Keep this read-only and route action through rebalance preview. |
| Source provenance panel | SEC EDGAR, Companies House, LSE RNS, FCA NSM, convenience feeds, broker price source | Make point-in-time and official-source status visible | Show accepted-at, published-at, retrieved-at, provider, and caveat fields. |
| Event-adjusted warning strip | Catalyst and blackout data | Prevent valuation from overriding event or stale-data vetoes | Event vetoes must remain visible above valuation enthusiasm. |

## Recommendation MVP Widgets

| Widget | Data source | Purpose | Required guardrail |
| --- | --- | --- | --- |
| Holdings action queue | Trading 212 read-only positions, valuation output, factor output, catalyst vetoes, risk checks | Show hold, add, trim, reduce, avoid, or watch prompts for existing holdings | Actions are review-only and must not create orders or set live targets. |
| Wider-market scan feed | Convenience EOD bars, convenience fundamentals, cached symbol universe | Surface discovery candidates beyond current holdings for operator review | Label as prototype discovery, show provider caveats, and do not treat as official PIT or broker-accessible truth. |
| Rationale panel | Deterministic strategy fields and optional OpenAI/LLM summary | Explain why an action was suggested in plain language | Disable or degrade when the key is absent; LLM output must never override rules, risk checks, or event vetoes. |
| Blockers and veto strip | Risk engine, event calendar, freshness checks, blacklist/exclusion config | Keep stop conditions visible before review hand-off | Vetoes remain authoritative even when valuation, factor, or LLM rationale is positive. |
| Review hand-off | Operator selection and rebalance preview state | Move reviewed ideas into the preview workflow for sizing and costs | Human review is required and hand-off still produces preview-only output until paper or guarded live controls pass. |

## UI Roadmap

| Phase | Status | Screens and widgets | Done when |
| --- | --- | --- | --- |
| 1. Read-only broker cockpit | Done | Overview, Holdings, broker status sidebar, allocation, concentration, currency, cash, and P/L widgets | Operator can review live Trading 212 state without any order path being enabled. |
| 2. Portfolio analytics polish | In progress | Sleeve drift, drawdown placeholder, top holdings, missing-value warnings, data freshness captions | Risk shape and data caveats are visible without reading raw tables. |
| 3. Valuation page | Done, then expand | Valuation summary, valuation multiples, technical indicators, event/news/sentiment context, source provenance, missing-data warnings | A holding or candidate can be assessed from PIT-ready valuation context before rebalance. |
| 4. Recommendation MVP | Planned | Holdings action queue, wider-market scan feed, deterministic rationale, optional OpenAI/LLM rationale, blocker strip, review hand-off | Operator can review suggested actions and discovery candidates without any direct order path. |
| 5. Paper workflow | In progress | Preview-only sleeve targets, target drift, cost components, event vetoes, local paper simulation, future paper submit | Paper batches can be reviewed, submitted, reconciled, and audited. |
| 6. Official data and factors | In progress | Starter factor attribution, PIT source status, config hash, stale data, missing-data policy | Factor ranks show source timing and cannot use future data. |
| 7. Guarded micro-live | Guarded | Live arming state, kill switch, reconciliation state, duplicate guard, batch hash, go/no-go checklist | Live submit remains blocked unless every operator and system control passes. |
| 8. Audit evidence | In progress | Audit log, run artefacts, broker status, guardrails, CI/smoke status | A reviewer can replay why a preview, paper fill, recommendation review, or blocked live action occurred. |

## Visualisation Backlog

| Visual | Source | Purpose |
| --- | --- | --- |
| Holdings allocation chart | Trading 212 read-only positions | Show concentration and sleeve context at a glance. |
| Currency exposure chart | Trading 212 position currencies and account cash | Make USD/GBP exposure visible for FX-cost awareness. |
| Cash and invested fraction | Account summary and positions | Show deployment, cash buffer, and preview readiness. |
| Unrealised P/L bar chart | Position wallet impact where available | Highlight current risk and winners/losers without implying trade advice. |
| Valuation band chart | PIT price and local valuation output | Show cheap/fair/expensive bands and margin-of-safety threshold. |
| Multiples peer chart | Fundamentals and peer set | Compare the holding or candidate against sector and market peers. |
| DCF sensitivity heatmap | Local valuation scenarios | Show how fair value changes under discount-rate and growth assumptions. |
| Source freshness timeline | Official and convenience providers | Show accepted, published, retrieved, and dashboard refresh timestamps. |
| Recommendation action queue | Holdings analytics and candidate scan output | Compare review-only actions, confidence, blockers, and rationale without implying automatic execution. |
| Candidate scan table | Convenience market scans and cached universe metadata | Surface wider-market ideas with provider caveats and freshness warnings. |
| Rebalance impact table | Local preview and cost model | Show turnover, SDRT, FX, slippage, vetoes, and warnings before paper/live steps. |
