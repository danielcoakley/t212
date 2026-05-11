"""Optional OpenAI-backed rationale generation for recommendation reviews."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx
from pydantic import BaseModel, Field

from isa_system.settings import Settings, get_settings
from isa_system.utils.time import now_utc

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


class LLMRationaleRequest(BaseModel):
    """Compact recommendation evidence sent to an optional LLM."""

    symbol: str
    action: str
    component_scores: dict[str, float]
    evidence: list[str]
    warnings: list[str] = Field(default_factory=list)


class LLMRationaleResponse(BaseModel):
    """Structured rationale returned by deterministic fallback or OpenAI."""

    enabled: bool
    provider: str
    generated_at_utc: datetime
    headline: str
    rationale: str
    risks: list[str]
    evidence_gaps: list[str]
    warnings: list[str]


def generate_llm_rationale(
    request: LLMRationaleRequest,
    *,
    settings: Settings | None = None,
    transport: httpx.BaseTransport | None = None,
) -> LLMRationaleResponse:
    """Generate review-only rationale, degrading safely when OpenAI is unavailable."""

    app_settings = settings or get_settings()
    if app_settings.openai_api_key is None:
        return _fallback(request, warning="OPENAI_API_KEY is not configured.")

    api_key = app_settings.openai_api_key.get_secret_value()
    payload = _payload(request, app_settings.openai_model)
    try:
        with httpx.Client(timeout=30.0, transport=transport) as client:
            response = client.post(
                OPENAI_RESPONSES_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        return _fallback(request, warning=f"OpenAI rationale failed: {exc.__class__.__name__}.")

    parsed = _extract_structured_response(response.json())
    if parsed is None:
        return _fallback(request, warning="OpenAI response did not contain structured rationale.")
    return LLMRationaleResponse(
        enabled=True,
        provider="openai",
        generated_at_utc=now_utc(),
        headline=str(parsed.get("headline") or f"{request.symbol} review"),
        rationale=str(parsed.get("rationale") or ""),
        risks=[str(item) for item in parsed.get("risks", [])],
        evidence_gaps=[str(item) for item in parsed.get("evidence_gaps", [])],
        warnings=request.warnings,
    )


def _payload(request: LLMRationaleRequest, model: str) -> dict[str, Any]:
    """Build a Responses API payload with structured output."""

    return {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": (
                    "You are a cautious investment-research assistant for a UK Stocks and "
                    "Shares ISA trading dashboard. Produce review-only JSON rationale. Do not "
                    "tell the operator to place an order. Emphasise evidence, risks, and gaps."
                ),
            },
            {
                "role": "user",
                "content": request.model_dump_json(),
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "recommendation_rationale",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "headline": {"type": "string"},
                        "rationale": {"type": "string"},
                        "risks": {"type": "array", "items": {"type": "string"}},
                        "evidence_gaps": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["headline", "rationale", "risks", "evidence_gaps"],
                },
            }
        },
    }


def _extract_structured_response(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Extract JSON object text from common Responses API output shapes."""

    output_text = payload.get("output_text")
    if isinstance(output_text, str):
        return _parse_json_object(output_text)

    for item in payload.get("output", []):
        for content in item.get("content", []) if isinstance(item, dict) else []:
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if isinstance(text, str):
                parsed = _parse_json_object(text)
                if parsed is not None:
                    return parsed
    return None


def _parse_json_object(text: str) -> dict[str, Any] | None:
    """Parse a JSON object from model text."""

    import json

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _fallback(request: LLMRationaleRequest, *, warning: str) -> LLMRationaleResponse:
    """Return deterministic rationale when LLM use is unavailable."""

    scores = ", ".join(
        f"{name}={value:.2f}" for name, value in sorted(request.component_scores.items())
    )
    return LLMRationaleResponse(
        enabled=False,
        provider="deterministic",
        generated_at_utc=now_utc(),
        headline=f"{request.symbol}: {request.action} review",
        rationale=(
            f"Review-only action {request.action} is based on current component scores "
            f"({scores}) and available evidence. No order path is enabled."
        ),
        risks=request.warnings or ["Recommendation evidence is incomplete."],
        evidence_gaps=[warning],
        warnings=[warning, *request.warnings],
    )
