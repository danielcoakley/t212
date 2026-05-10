"""Offline smoke test for the ISA starter system."""

from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal
from pathlib import Path

import pandas as pd

from isa_system.backtest.engine import BacktestEngine
from isa_system.backtest.fixtures import synthetic_fundamentals, synthetic_prices
from isa_system.factors.composite import composite_score
from isa_system.factors.dividend import compute_dividend_growth
from isa_system.factors.quality import compute_quality
from isa_system.factors.value import compute_value
from isa_system.portfolio.costs import CostModel
from isa_system.portfolio.optimiser import optimise_from_ranks
from isa_system.portfolio.rebalancer import build_rebalance_plan
from isa_system.signals.ranking import rank_candidates
from isa_system.utils.io import ensure_directory, write_json


def run_smoke_test(output_dir: Path | None = None) -> dict[str, Path]:
    """Run a synthetic backtest and rebalance preview without API keys."""

    root = ensure_directory(output_dir or Path("artifacts") / "smoke_test")
    prices = synthetic_prices()
    fundamentals = synthetic_fundamentals()
    scores = fundamentals[["symbol", "sector", "country", "price", "adv_gbp"]].copy()
    for frame in [
        compute_quality(fundamentals),
        compute_value(fundamentals),
        compute_dividend_growth(fundamentals),
    ]:
        scores = scores.merge(frame, on="symbol", how="left")
    scores["momentum"] = [0.1, 0.2, 0.3, 0.4]
    ranked = rank_candidates(
        composite_score(
            scores, {"quality": 0.35, "momentum": 0.30, "value": 0.20, "dividend_growth": 0.15}
        )
    )
    targets = optimise_from_ranks(
        ranked, max_positions=3, max_single_name_weight=0.06, cash_buffer=0.03
    )
    result = BacktestEngine().run(prices, ranked["symbol"].head(3).tolist())
    metrics_path = root / "metrics.csv"
    trades_path = root / "trades.csv"
    holdings_path = root / "holdings.csv"
    result.metrics.to_csv(metrics_path, index=False)
    result.trades.to_csv(trades_path, index=False)
    result.holdings.to_csv(holdings_path, index=False)
    latest_prices = (
        prices.sort_values("ts_utc")
        .groupby("symbol")
        .tail(1)
        .set_index("symbol")["adj_close"]
        .to_dict()
    )
    plan = build_rebalance_plan(
        run_id="smoke",
        current_weights={},
        targets=targets,
        prices={symbol: Decimal(str(price)) for symbol, price in latest_prices.items()},
        total_equity_gbp=Decimal("10000"),
        cost_model=CostModel(),
    )
    preview_payload = {
        "run_id": plan.run_id,
        "as_of_utc": plan.as_of_utc.isoformat(),
        "batch_hash": plan.batch_hash,
        "turnover": plan.turnover,
        "estimated_total_cost": str(plan.estimated_total_cost),
        "warnings": list(plan.warnings),
        "vetoes": list(plan.vetoes),
        "trades": [{**asdict(trade), "side": trade.side.value} for trade in plan.trades],
    }
    preview_path = write_json(root / "rebalance_preview.json", preview_payload)
    pd.DataFrame({"config_name": ["smoke"], "config_hash": ["synthetic"]}).to_csv(
        root / "config_snapshot.csv", index=False
    )
    (root / "summary.md").write_text(
        "# Smoke Test Summary\n\nSynthetic backtest and preview completed.\n", encoding="utf-8"
    )
    return {
        "metrics": metrics_path,
        "trades": trades_path,
        "holdings": holdings_path,
        "preview": preview_path,
    }


def main() -> None:
    """CLI entry point."""

    paths = run_smoke_test()
    print("Smoke test completed:")
    for name, path in paths.items():
        print(f"- {name}: {path}")


if __name__ == "__main__":
    main()
