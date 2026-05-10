"""Ranking engine for target candidates."""

from __future__ import annotations

import pandas as pd


def rank_candidates(scores: pd.DataFrame, score_col: str = "composite_score") -> pd.DataFrame:
    """Rank candidates by descending score."""

    if scores.empty:
        return scores.copy()
    out = scores.sort_values(score_col, ascending=False).reset_index(drop=True)
    out["rank"] = out.index + 1
    return out
