# Autonomous Investment Workflow

This system automates research workflow steps, not trading. It discovers,
enriches, scores, researches, tracks, compares, and previews. It does not place
live broker orders.

## End-To-End Flow

1. Run curated Finviz screeners.
2. Parse and normalize ticker candidates.
3. Deduplicate by symbol and preserve all source screeners.
4. Enrich candidates through local OpenBB where available.
5. Score candidates across growth, quality, valuation, momentum, catalysts,
   balance sheet, sentiment, and sector/theme tailwinds.
6. Rank candidates and select the top 10.
7. Generate deterministic thesis records and structured research memos.
8. Classify each thesis as BUY_NOW, WATCHLIST_WAIT_ENTRY,
   WATCHLIST_WAIT_CATALYST, or REJECT.
9. Keep researched non-bought candidates on the thesis watchlist.
10. Compare candidates and thesis states against current holdings.
11. Generate rebalance proposals only when a rationale-based trigger exists.
12. Generate local order previews only; manual approval is always required.

## Top 10 Selection

Top 10 selection uses the latest deduplicated candidate list plus enrichment
packets. Candidates are ranked by composite opportunity score, with explicit
penalties for missing or stale data and a small boost for appearing in multiple
screeners.

## Watchlist Behaviour

Watchlist candidates remain tracked as thesis records. They are not rebalanced
just because ranks move. They can be reconsidered when entry, valuation,
catalyst, thesis quality, or portfolio superiority materially changes.
