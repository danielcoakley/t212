"""Run the full offline portfolio intelligence pipeline."""

from __future__ import annotations

from isa_system.orchestrator import PortfolioOrchestrator


def main() -> None:
    """Run the full fixture-backed pipeline and print the run summary."""

    run = PortfolioOrchestrator().run(use_fixtures=True, write_artifacts=True)
    print(run.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
