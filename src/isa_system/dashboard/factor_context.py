"""Starter factor attribution helpers for current dashboard holdings."""

from __future__ import annotations

from typing import Any

import pandas as pd

from isa_system.services.valuation import HoldingsValuationResponse, HoldingValuation

FACTOR_WEIGHTS = {
    "momentum_z": 0.40,
    "value_z": 0.30,
    "dividend_z": 0.15,
    "quality_z": 0.15,
}


def factor_attribution_frame(snapshot: HoldingsValuationResponse) -> pd.DataFrame:
    """Return transparent starter factor attribution rows for current holdings.

    This is a dashboard explanation layer, not the final point-in-time factor
    engine. It uses available convenience valuation and technical fields, marks
    missing official data, and keeps the composite intentionally simple.
    """

    rows = [_raw_factor_row(holding, snapshot.provider) for holding in snapshot.holdings]
    frame = pd.DataFrame(rows, columns=_factor_columns())
    if frame.empty:
        return frame

    frame["momentum_z"] = _zscore(frame["momentum_raw"])
    frame["value_z"] = _zscore(frame["value_raw"])
    frame["dividend_z"] = _zscore(frame["dividend_raw"])
    frame["quality_z"] = _zscore(frame["quality_raw"])
    frame["composite_score"] = sum(
        frame[column].fillna(0.0) * weight for column, weight in FACTOR_WEIGHTS.items()
    )
    frame["rank"] = frame["composite_score"].rank(ascending=False, method="min").astype(int)
    return frame.sort_values(["rank", "symbol"])


def factor_coverage_summary(frame: pd.DataFrame) -> dict[str, int]:
    """Return compact factor coverage counts."""

    if frame.empty:
        return {"holdings": 0, "momentum": 0, "value": 0, "dividend": 0, "quality": 0}
    return {
        "holdings": len(frame),
        "momentum": int(frame["momentum_raw"].notna().sum()),
        "value": int(frame["value_raw"].notna().sum()),
        "dividend": int(frame["dividend_raw"].notna().sum()),
        "quality": int(frame["quality_raw"].notna().sum()),
    }


def factor_methodology_frame() -> pd.DataFrame:
    """Return the visible method and guardrails used by the starter attribution."""

    return pd.DataFrame(
        [
            {
                "factor": "Momentum",
                "current_proxy": (
                    "Average of available 1m, 3m, 6m, and 12m adjusted-close momentum."
                ),
                "roadmap_upgrade": (
                    "Use PIT-adjusted return series, volatility scaling, and sector-relative trend."
                ),
            },
            {
                "factor": "Value",
                "current_proxy": (
                    "Lower trailing P/E, forward P/E, and P/B score higher when available."
                ),
                "roadmap_upgrade": (
                    "Use official filing timestamps, EV/EBIT, FCF yield, and peer medians."
                ),
            },
            {
                "factor": "Dividend",
                "current_proxy": "Dividend yield from convenience provider when available.",
                "roadmap_upgrade": (
                    "Use dividend history, payout coverage, withholding assumptions, and stability."
                ),
            },
            {
                "factor": "Quality",
                "current_proxy": "Not scored unless provider quality fields are present.",
                "roadmap_upgrade": (
                    "Use profitability, margins, leverage, coverage, accruals, and stability."
                ),
            },
        ]
    )


def _raw_factor_row(holding: HoldingValuation, provider: str) -> dict[str, Any]:
    """Return raw, pre-normalisation factor fields for one holding."""

    valuation = holding.valuation
    technicals = holding.technicals
    missing: list[str] = []
    momentum_values = [
        value
        for value in [
            technicals.momentum_1m,
            technicals.momentum_3m,
            technicals.momentum_6m,
            technicals.momentum_12m,
        ]
        if value is not None
    ]
    momentum_raw = sum(momentum_values) / len(momentum_values) if momentum_values else None
    if momentum_raw is None:
        missing.append("momentum")

    value_inputs = [
        _inverse_positive(valuation.trailing_pe),
        _inverse_positive(valuation.forward_pe),
        _inverse_positive(valuation.price_to_book),
    ]
    value_values = [value for value in value_inputs if value is not None]
    value_raw = sum(value_values) / len(value_values) if value_values else None
    if value_raw is None:
        missing.append("value")

    dividend_raw = valuation.dividend_yield
    if dividend_raw is None:
        missing.append("dividend")

    quality_raw = None
    missing.append("quality")

    return {
        "rank": None,
        "symbol": holding.symbol,
        "research_symbol": holding.research_symbol,
        "name": holding.name,
        "provider": provider,
        "momentum_raw": momentum_raw,
        "value_raw": value_raw,
        "dividend_raw": dividend_raw,
        "quality_raw": quality_raw,
        "momentum_z": None,
        "value_z": None,
        "dividend_z": None,
        "quality_z": None,
        "composite_score": None,
        "missing_factors": ", ".join(missing),
        "warnings": "; ".join(holding.warnings),
    }


def _factor_columns() -> list[str]:
    """Return stable factor attribution columns."""

    return [
        "rank",
        "symbol",
        "research_symbol",
        "name",
        "provider",
        "momentum_raw",
        "value_raw",
        "dividend_raw",
        "quality_raw",
        "momentum_z",
        "value_z",
        "dividend_z",
        "quality_z",
        "composite_score",
        "missing_factors",
        "warnings",
    ]


def _inverse_positive(value: float | None) -> float | None:
    """Return a simple inverse valuation ratio when the value is positive."""

    if value is None or value <= 0:
        return None
    return 1.0 / value


def _zscore(series: pd.Series) -> pd.Series:
    """Return a stable z-score series that tolerates sparse inputs."""

    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().sum() < 2:
        return pd.Series(
            [0.0 if pd.notna(value) else None for value in numeric], index=series.index
        )
    std = numeric.std(ddof=0)
    if std == 0 or pd.isna(std):
        return pd.Series(
            [0.0 if pd.notna(value) else None for value in numeric], index=series.index
        )
    return (numeric - numeric.mean()) / std
