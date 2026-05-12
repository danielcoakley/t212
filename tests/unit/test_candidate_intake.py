"""Candidate intake tests."""

from __future__ import annotations

from pathlib import Path

from isa_system.discovery.candidate_intake import CandidateIntakeService
from isa_system.discovery.finviz_screeners import load_finviz_screeners


def test_deduplicates_candidates_across_screeners() -> None:
    """Duplicate ticker symbols are merged and source screeners preserved."""

    screeners = load_finviz_screeners()
    fixtures = _fixture_html()

    result = CandidateIntakeService(screeners=screeners).run(fixture_html_by_screener=fixtures)

    symbols = [candidate.symbol for candidate in result.candidates]
    assert symbols.count("MSFT") == 1
    msft = next(candidate for candidate in result.candidates if candidate.symbol == "MSFT")
    assert msft.screener_appearance_count == 2
    assert msft.multi_screener_boost == 5.0
    assert msft.source_screeners == ["Elite GARP Compounders", "Hidden Compounders"]


def test_discovery_can_run_from_fixture_data() -> None:
    """Offline fixture discovery produces a candidate list."""

    result = CandidateIntakeService(screeners=load_finviz_screeners()).run(
        fixture_html_by_screener=_fixture_html()
    )

    assert len(result.candidates) == 7
    assert result.warnings == []
    assert result.candidates[0].screener_appearance_count == 2


def _fixture_html() -> dict[str, str]:
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
