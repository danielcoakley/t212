# Finviz Discovery

Finviz is used only for initial candidate discovery. It is not the research,
valuation, thesis, or trading authority.

## Curated Screeners

The screeners live in `configs/finviz_screeners.yaml`:

- Elite GARP Compounders
- Hidden Compounders
- Post-Earnings Acceleration

The command centre also exposes a configurable Finviz Screener page. It starts
from these presets, lets the operator toggle a curated subset of supported
Finviz filter codes, accepts an explicit raw filter code when needed, and builds
one dynamic Finviz URL for manual inspection.

## Polite Usage

The fetcher uses browser-like headers, timeout handling, retry/backoff, and
local HTML caching under `artifacts/finviz_cache`. It is operator-triggered and
not designed for aggressive scraping.

## Layout Risk

The parser extracts ticker symbols from Finviz quote links and preserves
best-effort table cells where available. If Finviz blocks, returns empty HTML,
or changes layout, discovery returns no rows with warnings instead of crashing.

The first configurable screener slice handles the first returned table page.
Pagination and saved custom presets are future enhancements.

## Offline Tests

Fixture HTML lives under `tests/fixtures/finviz_*.html`. Run:

```powershell
$env:PYTHONPATH='src'; python scripts/run_discovery.py --fixtures
```
