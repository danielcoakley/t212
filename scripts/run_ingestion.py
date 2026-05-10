"""Run starter ingestion checks."""

from __future__ import annotations

from isa_system.backtest.fixtures import synthetic_prices
from isa_system.data.ingestion.prices import normalise_price_bars


def main() -> None:
    """Run synthetic price ingestion."""

    print(normalise_price_bars(synthetic_prices()).head().to_string())


if __name__ == "__main__":
    main()
