"""Run the smoke rebalance preview."""

from __future__ import annotations

from isa_system.smoke_test import run_smoke_test


def main() -> None:
    """Run the smoke test preview."""

    print(run_smoke_test()["preview"])


if __name__ == "__main__":
    main()
