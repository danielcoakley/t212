"""Run Finviz discovery."""

from __future__ import annotations

import argparse
import json

from isa_system.discovery.candidate_intake import CandidateIntakeService
from isa_system.discovery.finviz_screeners import load_finviz_screeners


def main() -> None:
    """Run candidate discovery and print a compact JSON summary."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", action="store_true", help="Use local fixture HTML.")
    args = parser.parse_args()

    fixture_html = _fixture_html() if args.fixtures else None
    result = CandidateIntakeService(screeners=load_finviz_screeners()).run(
        fixture_html_by_screener=fixture_html
    )
    print(
        json.dumps(
            {
                "run_id": result.run_id,
                "candidate_count": len(result.candidates),
                "symbols": [candidate.symbol for candidate in result.candidates],
                "warnings": result.warnings,
            },
            indent=2,
        )
    )


def _fixture_html() -> dict[str, str]:
    """Load local Finviz fixture HTML for offline discovery."""

    from pathlib import Path

    fixture_dir = Path("tests/fixtures")
    return {
        "Elite GARP Compounders": (fixture_dir / "finviz_elite_garp.html").read_text(
            encoding="utf-8"
        ),
        "Hidden Compounders": (fixture_dir / "finviz_hidden_compounders.html").read_text(
            encoding="utf-8"
        ),
        "Post-Earnings Acceleration": (fixture_dir / "finviz_post_earnings.html").read_text(
            encoding="utf-8"
        ),
    }


if __name__ == "__main__":
    main()
