"""Run a synthetic backtest."""

from __future__ import annotations

from isa_system.backtest.engine import BacktestEngine
from isa_system.backtest.fixtures import synthetic_prices


def main() -> None:
    """Run the backtest and print metrics."""

    result = BacktestEngine().run(synthetic_prices())
    print(result.metrics.to_string(index=False))


if __name__ == "__main__":
    main()
