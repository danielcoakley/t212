"""Composite factor scoring."""

from __future__ import annotations

import pandas as pd


def composite_score(df: pd.DataFrame, weights: dict[str, float]) -> pd.DataFrame:
    """Combine factor columns into a weighted composite score."""

    out = df.copy()
    score = pd.Series(0.0, index=out.index)
    for column, weight in weights.items():
        if column not in out:
            out[column] = 0.0
        score = score + out[column].fillna(0.0).astype(float) * float(weight)
    out["composite_score"] = score
    return out
