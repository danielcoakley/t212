"""Backtest routes."""

from __future__ import annotations

from fastapi import APIRouter

from isa_system.backtest.engine import BacktestEngine
from isa_system.backtest.fixtures import synthetic_prices

router = APIRouter()


@router.post("/backtests/run")
def run_backtest() -> dict[str, float | str]:
    """Run a tiny synthetic backtest."""

    result = BacktestEngine().run(synthetic_prices())
    return {"status": "completed", **result.metrics.iloc[0].to_dict()}
