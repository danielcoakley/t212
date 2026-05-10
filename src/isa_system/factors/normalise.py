"""Winsorisation and z-score normalisation helpers."""

from __future__ import annotations

import pandas as pd


def winsorise(series: pd.Series, lower: float = 0.05, upper: float = 0.95) -> pd.Series:
    """Clip a series by quantiles."""

    if series.dropna().empty:
        return series
    return series.clip(series.quantile(lower), series.quantile(upper))


def zscore(series: pd.Series) -> pd.Series:
    """Return a conservative z-score, with missing values at zero."""

    clean = series.astype(float)
    std = clean.std(ddof=0)
    if std == 0 or pd.isna(std):
        return pd.Series(0.0, index=series.index)
    return ((clean - clean.mean()) / std).fillna(0.0)


def zscore_by_date(df: pd.DataFrame, value_col: str, out_col: str) -> pd.DataFrame:
    """Z-score a value by date."""

    out = df.copy()
    out[out_col] = out.groupby("date")[value_col].transform(zscore)
    return out
