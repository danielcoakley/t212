"""Run the local offline portfolio intelligence smoke test."""

from __future__ import annotations

from isa_system.orchestrator import PortfolioOrchestrator


def main() -> None:
    """Print a compact smoke-test result."""

    result = PortfolioOrchestrator().run(use_fixtures=True, write_artifacts=True)
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
