# Data Sources

| Source | Role | Typical granularity | Point-in-time suitability | Rate-limit notes | Licence and caveats |
| --- | --- | --- | --- | --- | --- |
| Trading 212 Public API | Official execution, account state, accessible instruments, positions, orders, history, broker-universe scan seed | Account and order events; instrument metadata snapshots | High for broker state and instrument identity; not a historical price source | Endpoint-specific limits, per account | Public API is beta, Invest and Stocks ISA only. POST order endpoints are treated as non-idempotent. Instrument metadata validates symbols but does not prove liquidity or order suitability. |
| SEC EDGAR | Official US filings, submissions, company facts | Filing and fact timestamps | High when acceptance timestamps are present | Conservative fair-access rate limiting | Use a clear user-agent. |
| Companies House | UK issuer matching, registry metadata, filing history | Filing metadata | Medium to high depending on publication timing | API key, public throttling | Not a market data substitute. |
| LSE RNS | UK announcement validation | Announcement metadata | Medium; timing precision can vary | Public pages can change | Used for validation, not guaranteed real-time signal capture. |
| FCA NSM | Official UK regulated-information archive | Archive metadata and documents | Medium; archive/validation layer | Public search limitations | The NSM is not treated as a real-time feed. |
| yfinance | Convenience research bars and corporate actions | Daily bars by default | Low to medium; convenience feed | Unofficial limits | Not a sole truth layer for live risk decisions. |
| Alpha Vantage | Convenience prices, selected fundamentals, earnings fields | Daily and endpoint-specific | Low to medium | Free tier is rate constrained | Some endpoints or volume require paid plans. |
| Financial Modeling Prep | Convenience fundamentals, profiles, ratios, earnings | Daily or filing-derived | Low to medium | Plan-dependent | Some endpoints are non-free or tier-gated. |
| FRED | Macro and regime features | Daily, weekly, monthly | Medium, with retrieved timestamps | API key supported | Macro releases may be revised. |
| Reddit / X | Optional sentiment overlays | Post or message time | Low unless archived carefully | API and licence constraints | Disabled by default and low-weight only. |
| OpenAI API or other LLM provider | Deep research thesis validation and optional recommendation rationale summarisation | Request/response level | Not a market or point-in-time truth source | API key and model limits | Disabled or marked unavailable when no key is present. A `RESEARCH_PASSED` review can unlock preview eligibility for BUY/add rows, but must not create orders, set targets, or override risk/event vetoes. |

Official filing and event sources are the truth layer for point-in-time
availability. Convenience feeds are useful for screening and cached
research, but they must not silently override official timestamps.
Wider-market scans are seeded from authenticated Trading 212 instrument
metadata when available and fall back to the YAML universe when broker metadata
or market data is unavailable. Ranking still depends on convenience research
feeds and must display provider caveats, retrieved timestamps, and missing
coverage clearly before any candidate is reviewed.
LLM output is an evidence gate and explanation aid only. Recommendation
decisions must remain reproducible from deterministic valuation, factor, risk,
event, and freshness fields, and live execution remains separately guarded.
