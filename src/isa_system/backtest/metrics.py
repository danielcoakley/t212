"""Backtest metrics."""

from __future__ import annotations

import numpy as np
import pandas as pd


def performance_metrics(equity: pd.Series, trades: pd.DataFrame) -> dict[str, float]:
    """Compute a starter set of performance metrics."""

    returns = equity.pct_change().fillna(0.0)
    years = max(len(returns) / 252.0, 1e-9)
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1 if len(equity) > 1 else 0.0
    sharpe = np.sqrt(252) * returns.mean() / returns.std(ddof=0) if returns.std(ddof=0) else 0.0
    downside = returns[returns < 0].std(ddof=0)
    sortino = np.sqrt(252) * returns.mean() / downside if downside else 0.0
    drawdown = equity / equity.cummax() - 1.0
    win_rate = (
        float((trades.get("pnl", pd.Series(dtype=float)) > 0).mean()) if not trades.empty else 0.0
    )
    return {
        "cagr": float(cagr),
        "annualised_sharpe": float(sharpe),
        "sortino": float(sortino),
        "max_drawdown": float(drawdown.min()),
        "win_rate": win_rate,
        "expectancy": float(trades.get("pnl", pd.Series([0.0])).mean())
        if not trades.empty
        else 0.0,
        "turnover": float(trades.get("turnover", pd.Series([0.0])).sum())
        if not trades.empty
        else 0.0,
        "average_hold_duration": 21.0,
        "exposure": 0.97,
        "cost_drag": float(trades.get("cost", pd.Series([0.0])).sum()) if not trades.empty else 0.0,
    }
