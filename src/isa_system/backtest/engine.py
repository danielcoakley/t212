"""Daily-bar point-in-time aware starter backtest engine."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from isa_system.backtest.metrics import performance_metrics


@dataclass(frozen=True)
class BacktestResult:
    """Backtest output tables."""

    metrics: pd.DataFrame
    trades: pd.DataFrame
    holdings: pd.DataFrame
    monthly_returns: pd.DataFrame


class BacktestEngine:
    """Simple deterministic daily-bar backtest for starter validation."""

    def __init__(self, initial_equity: float = 10_000.0, rebalance_frequency: str = "M") -> None:
        self.initial_equity = initial_equity
        self.rebalance_frequency = rebalance_frequency

    def run(self, prices: pd.DataFrame, ranked_symbols: list[str] | None = None) -> BacktestResult:
        """Run an equal-weight synthetic backtest over selected symbols."""

        ranked_symbols = ranked_symbols or sorted(prices["symbol"].unique())[:3]
        pivot = (
            prices[prices["symbol"].isin(ranked_symbols)]
            .pivot(index="ts_utc", columns="symbol", values="adj_close")
            .sort_index()
        )
        returns = pivot.pct_change().fillna(0.0)
        portfolio_returns = returns.mean(axis=1)
        equity = (1 + portfolio_returns).cumprod() * self.initial_equity
        holdings = pd.DataFrame(
            {
                "ts_utc": equity.index,
                "equity": equity.values,
                "invested_fraction": 0.97,
            }
        )
        trades = pd.DataFrame(
            {
                "ts_utc": equity.index[::21],
                "symbol": ranked_symbols[0],
                "side": "BUY",
                "turnover": 0.03,
                "cost": 0.25,
                "pnl": portfolio_returns.reindex(equity.index[::21]).fillna(0).values
                * self.initial_equity,
            }
        )
        metrics = pd.DataFrame([performance_metrics(equity, trades)])
        monthly = (
            equity.resample("ME").last().pct_change().fillna(0.0).rename("return").reset_index()
        )
        return BacktestResult(
            metrics=metrics, trades=trades, holdings=holdings, monthly_returns=monthly
        )
