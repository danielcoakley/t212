"""Tests for the OpenAI-backed deep research gate."""

from __future__ import annotations

import json
from datetime import UTC
from pathlib import Path

import httpx
from pydantic import SecretStr

from isa_system.services.deep_research import (
    DeepResearchDecision,
    DeepResearchInput,
    DeepResearchStatus,
    latest_deep_research_review,
    run_deep_research,
)
from isa_system.settings import Settings


def test_openai_deep_research_parses_and_persists_review(tmp_path: Path) -> None:
    """A structured OpenAI response becomes a persisted research pass."""

    settings = Settings(
        openai_api_key=SecretStr("test-key"),
        openai_model="test-model",
        operational_db_dsn=f"sqlite:///{tmp_path / 'ops.db'}",
    )
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "output_text": json.dumps(
                    {
                        "thesis": "GOOD.L has enough evidence for review-only sizing.",
                        "bear_price_target": 80,
                        "base_price_target": 100,
                        "bull_price_target": 120,
                        "bear_case": "Margins compress.",
                        "base_case": "Execution remains steady.",
                        "bull_case": "Momentum and quality improve.",
                        "key_drivers": ["quality", "momentum"],
                        "risks": ["valuation"],
                        "evidence_gaps": ["Confirm next filing timestamp."],
                        "final_score": 84,
                        "decision": "RESEARCH_PASSED",
                    }
                )
            },
        )
    )

    review = run_deep_research(_request(), settings=settings, transport=transport)
    latest = latest_deep_research_review("GOOD.L", settings=settings)

    assert review.status == DeepResearchStatus.AVAILABLE
    assert review.decision == DeepResearchDecision.RESEARCH_PASSED
    assert review.final_score == 84
    assert latest is not None
    assert latest.id == review.id
    assert latest.generated_at_utc.tzinfo == UTC


def test_missing_openai_key_blocks_research_approval(tmp_path: Path) -> None:
    """Missing OpenAI credentials degrade safely and cannot approve a buy."""

    settings = Settings(
        openai_api_key=None,
        operational_db_dsn=f"sqlite:///{tmp_path / 'ops.db'}",
    )

    review = run_deep_research(_request(), settings=settings)

    assert review.status == DeepResearchStatus.UNAVAILABLE
    assert review.decision is None
    assert review.is_valid_pass is False
    assert "OPENAI_API_KEY" in review.warnings[0]


def test_openai_failure_blocks_research_approval(tmp_path: Path) -> None:
    """Transport failures create a failed review rather than an approval."""

    settings = Settings(
        openai_api_key=SecretStr("test-key"),
        operational_db_dsn=f"sqlite:///{tmp_path / 'ops.db'}",
    )

    def raise_timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timeout", request=request)

    review = run_deep_research(
        _request(),
        settings=settings,
        transport=httpx.MockTransport(raise_timeout),
    )

    assert review.status == DeepResearchStatus.FAILED
    assert review.decision is None
    assert review.is_valid_pass is False


def _request() -> DeepResearchInput:
    return DeepResearchInput(
        symbol="GOOD.L",
        research_symbol="GOOD.L",
        broker_ticker="GOODl_EQ",
        name="Good plc",
        action="REVIEW_BUY",
        source="watchlist",
        component_scores={
            "fundamental_valuation": 0.7,
            "technical": 0.6,
            "sentiment_news": 0.1,
            "catalysts": 0.0,
            "composite": 0.52,
        },
        valuation={"trailing_pe": 9.0, "dividend_yield": 0.04},
        technicals={"momentum_12m": 0.25, "sma50": 100, "sma200": 90},
        risk_flags=[],
        rationale=["Positive value and momentum score."],
        warnings=[],
        blockers=[],
    )
