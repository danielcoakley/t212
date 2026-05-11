"""Tests for optional LLM rationale generation."""

from __future__ import annotations

import json

import httpx

from isa_system.services.llm_rationale import LLMRationaleRequest, generate_llm_rationale
from isa_system.settings import Settings


def test_llm_rationale_falls_back_without_key() -> None:
    """Missing OpenAI configuration returns deterministic rationale."""

    response = generate_llm_rationale(_request(), settings=Settings(openai_api_key=None))

    assert not response.enabled
    assert response.provider == "deterministic"
    assert "OPENAI_API_KEY" in response.evidence_gaps[0]


def test_llm_rationale_parses_openai_response() -> None:
    """Structured OpenAI response text is parsed into the typed response."""

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["text"]["format"]["type"] == "json_schema"
        return httpx.Response(
            200,
            json={
                "output_text": json.dumps(
                    {
                        "headline": "AAPL review",
                        "rationale": "Evidence is balanced.",
                        "risks": ["valuation stretch"],
                        "evidence_gaps": ["official filing refresh pending"],
                    }
                )
            },
        )

    response = generate_llm_rationale(
        _request(),
        settings=Settings(openai_api_key="test-key", openai_model="test-model"),
        transport=httpx.MockTransport(handler),
    )

    assert response.enabled
    assert response.provider == "openai"
    assert response.headline == "AAPL review"
    assert response.risks == ["valuation stretch"]


def _request() -> LLMRationaleRequest:
    return LLMRationaleRequest(
        symbol="AAPL",
        action="HOLD",
        component_scores={"technical": 0.5, "fundamental": 0.2},
        evidence=["Momentum positive."],
        warnings=[],
    )
