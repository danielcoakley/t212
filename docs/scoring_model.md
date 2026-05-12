# Scoring Model

The scoring engine is deterministic and explainable. It is designed for
research triage, not trading authority.

## Factor Weights

| Factor | Weight |
| --- | ---: |
| Growth | 20% |
| Quality | 15% |
| Valuation | 15% |
| Momentum | 15% |
| Catalyst | 15% |
| Balance sheet | 10% |
| Sentiment | 5% |
| Sector/theme tailwind | 5% |

## Adjustments

- Missing or weak enrichment data reduces the composite score.
- Stale enrichment data receives a penalty.
- Appearing in multiple Finviz screeners gives a small transparent boost.
- Extreme valuation and parabolic momentum are penalized.

Every score snapshot includes factor scores, weighted scores, penalties,
boosts, data quality score, and a concise explanation.
