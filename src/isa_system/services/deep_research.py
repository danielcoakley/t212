"""OpenAI-backed deep research gate for review-only buy/add candidates."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import httpx
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import or_, select

from isa_system.db.crud import append_audit_log
from isa_system.db.models import ResearchReview as ResearchReviewRecord
from isa_system.db.session import init_db, make_engine, make_session_factory
from isa_system.services.instrument_validation import InstrumentValidationRow
from isa_system.services.recommendations import TradeRecommendation
from isa_system.settings import Settings, get_settings
from isa_system.utils.hashing import sha256_digest
from isa_system.utils.time import now_utc, require_utc

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_REVIEW_TTL_DAYS = 7


class DeepResearchDecision(StrEnum):
    """Decision returned by the evidence gate."""

    REJECT = "REJECT"
    WATCH = "WATCH"
    RESEARCH_PASSED = "RESEARCH_PASSED"


class DeepResearchStatus(StrEnum):
    """Availability state for a persisted research review."""

    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


class PriceTarget(BaseModel):
    """One review price target."""

    label: str
    price: float | None = None
    rationale: str


class DeepResearchInput(BaseModel):
    """Evidence packet sent to the deep research gate."""

    symbol: str
    research_symbol: str
    broker_ticker: str | None = None
    name: str | None = None
    action: str
    source: str
    component_scores: dict[str, float | None]
    valuation: dict[str, Any]
    technicals: dict[str, Any]
    catalysts: list[dict[str, Any]] = Field(default_factory=list)
    news: list[dict[str, Any]] = Field(default_factory=list)
    sentiment: dict[str, Any] | None = None
    risk_flags: list[str] = Field(default_factory=list)
    rationale: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)


class DeepResearchReview(BaseModel):
    """Persisted deep research gate result."""

    id: str
    symbol: str
    research_symbol: str
    broker_ticker: str | None = None
    status: DeepResearchStatus
    decision: DeepResearchDecision | None = None
    thesis: str
    price_targets: list[PriceTarget] = Field(default_factory=list)
    key_drivers: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    evidence_gaps: list[str] = Field(default_factory=list)
    final_score: int | None = Field(default=None, ge=0, le=100)
    model: str
    evidence_hash: str
    generated_at_utc: datetime
    expires_at_utc: datetime
    warnings: list[str] = Field(default_factory=list)
    request: DeepResearchInput

    @field_validator("generated_at_utc", "expires_at_utc")
    @classmethod
    def _timestamps_are_utc(cls, value: datetime) -> datetime:
        return require_utc(value)

    @property
    def is_valid_pass(self) -> bool:
        """Return whether this review currently approves preview eligibility."""

        return (
            self.status == DeepResearchStatus.AVAILABLE
            and self.decision == DeepResearchDecision.RESEARCH_PASSED
            and self.expires_at_utc > now_utc()
        )


def build_deep_research_input(
    item: TradeRecommendation,
    *,
    instrument_row: InstrumentValidationRow | None = None,
    blockers: list[str] | None = None,
) -> DeepResearchInput:
    """Create a compact, auditable evidence packet for one recommendation."""

    candidate = item.candidate
    scores = item.scores
    return DeepResearchInput(
        symbol=candidate.symbol,
        research_symbol=candidate.research_symbol,
        broker_ticker=instrument_row.broker_ticker if instrument_row else None,
        name=candidate.name or (instrument_row.name if instrument_row else None),
        action=item.action.value,
        source=candidate.source,
        component_scores={
            "fundamental_valuation": scores.fundamental_valuation.score,
            "technical": scores.technical.score,
            "sentiment_news": scores.sentiment_news.score,
            "catalysts": scores.catalysts.score,
            "composite": scores.composite,
        },
        valuation=item.valuation.model_dump(mode="json"),
        technicals=item.technicals.model_dump(mode="json"),
        catalysts=[event.model_dump(mode="json") for event in item.upcoming_events],
        news=[news.model_dump(mode="json") for news in item.news],
        sentiment=item.sentiment.model_dump(mode="json") if item.sentiment else None,
        risk_flags=list(item.risk_flags),
        rationale=list(item.rationale),
        warnings=list(item.warnings),
        blockers=blockers or [],
    )


def run_deep_research(
    request: DeepResearchInput,
    *,
    settings: Settings | None = None,
    transport: httpx.BaseTransport | None = None,
    persist: bool = True,
    ttl_days: int = DEFAULT_REVIEW_TTL_DAYS,
) -> DeepResearchReview:
    """Run the OpenAI research gate and persist the result.

    A missing key or model failure creates an unavailable review. That keeps the
    app runnable offline while ensuring buy/add candidates cannot pass the gate.
    """

    app_settings = settings or get_settings()
    generated_at_utc = now_utc()
    expires_at_utc = generated_at_utc + timedelta(days=ttl_days)
    evidence_hash = sha256_digest(request.model_dump(mode="json"))
    if app_settings.openai_api_key is None:
        review = _unavailable_review(
            request,
            status=DeepResearchStatus.UNAVAILABLE,
            model=app_settings.openai_model,
            evidence_hash=evidence_hash,
            generated_at_utc=generated_at_utc,
            expires_at_utc=expires_at_utc,
            warning="OPENAI_API_KEY is not configured; deep research cannot approve buys.",
        )
        if persist:
            persist_deep_research_review(review, settings=app_settings)
        return review

    payload = _openai_payload(request, app_settings.openai_model)
    api_key = app_settings.openai_api_key.get_secret_value()
    try:
        with httpx.Client(timeout=60.0, transport=transport) as client:
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
        review = _unavailable_review(
            request,
            status=DeepResearchStatus.FAILED,
            model=app_settings.openai_model,
            evidence_hash=evidence_hash,
            generated_at_utc=generated_at_utc,
            expires_at_utc=expires_at_utc,
            warning=f"OpenAI deep research failed: {exc.__class__.__name__}.",
        )
        if persist:
            persist_deep_research_review(review, settings=app_settings)
        return review

    parsed = _extract_structured_response(response.json())
    if parsed is None:
        review = _unavailable_review(
            request,
            status=DeepResearchStatus.FAILED,
            model=app_settings.openai_model,
            evidence_hash=evidence_hash,
            generated_at_utc=generated_at_utc,
            expires_at_utc=expires_at_utc,
            warning="OpenAI response did not contain structured deep research JSON.",
        )
        if persist:
            persist_deep_research_review(review, settings=app_settings)
        return review

    review = _review_from_model_response(
        request,
        parsed=parsed,
        model=app_settings.openai_model,
        evidence_hash=evidence_hash,
        generated_at_utc=generated_at_utc,
        expires_at_utc=expires_at_utc,
    )
    if persist:
        persist_deep_research_review(review, settings=app_settings)
    return review


def persist_deep_research_review(
    review: DeepResearchReview, *, settings: Settings | None = None
) -> None:
    """Persist one deep research review and append an audit event."""

    app_settings = settings or get_settings()
    engine = make_engine(app_settings.operational_db_dsn)
    init_db(engine)
    factory = make_session_factory(engine)
    with factory() as session:
        session.merge(
            ResearchReviewRecord(
                id=review.id,
                symbol=review.symbol,
                research_symbol=review.research_symbol,
                broker_ticker=review.broker_ticker,
                status=review.status.value,
                decision=review.decision.value if review.decision else None,
                final_score=review.final_score,
                model=review.model,
                evidence_hash=review.evidence_hash,
                generated_at_utc=review.generated_at_utc,
                expires_at_utc=review.expires_at_utc,
                request_json=review.request.model_dump_json(),
                response_json=json.dumps(_response_json(review), sort_keys=True),
                warnings_json=json.dumps(review.warnings, sort_keys=True),
            )
        )
        append_audit_log(
            session,
            actor="system.deep_research",
            action="research_review.run",
            payload={
                "review_id": review.id,
                "symbol": review.research_symbol,
                "status": review.status.value,
                "decision": review.decision.value if review.decision else None,
                "evidence_hash": review.evidence_hash,
            },
            outcome=review.status.value,
        )
        session.commit()


def latest_deep_research_review(
    symbol: str, *, settings: Settings | None = None
) -> DeepResearchReview | None:
    """Return the latest persisted review for a broker or research symbol."""

    reviews = latest_deep_research_reviews([symbol], settings=settings)
    return reviews.get(symbol.upper())


def latest_deep_research_reviews(
    symbols: list[str], *, settings: Settings | None = None
) -> dict[str, DeepResearchReview]:
    """Return latest reviews keyed by requested upper-case symbol."""

    if not symbols:
        return {}
    app_settings = settings or get_settings()
    engine = make_engine(app_settings.operational_db_dsn)
    init_db(engine)
    keys = {symbol.upper() for symbol in symbols}
    factory = make_session_factory(engine)
    with factory() as session:
        records = session.scalars(
            select(ResearchReviewRecord)
            .where(
                or_(
                    ResearchReviewRecord.symbol.in_(keys),
                    ResearchReviewRecord.research_symbol.in_(keys),
                )
            )
            .order_by(ResearchReviewRecord.generated_at_utc.desc())
        ).all()
    rows: dict[str, DeepResearchReview] = {}
    for record in records:
        review = _review_from_record(record)
        for key in {record.symbol.upper(), record.research_symbol.upper()}:
            if key in keys and key not in rows:
                rows[key] = review
    return rows


def _review_from_model_response(
    request: DeepResearchInput,
    *,
    parsed: dict[str, Any],
    model: str,
    evidence_hash: str,
    generated_at_utc: datetime,
    expires_at_utc: datetime,
) -> DeepResearchReview:
    decision = _decision(parsed.get("decision"))
    final_score = _bounded_score(parsed.get("final_score"))
    return DeepResearchReview(
        id=_review_id(request, evidence_hash, generated_at_utc),
        symbol=request.symbol,
        research_symbol=request.research_symbol,
        broker_ticker=request.broker_ticker,
        status=DeepResearchStatus.AVAILABLE,
        decision=decision,
        thesis=str(parsed.get("thesis") or "No thesis supplied."),
        price_targets=_price_targets(parsed),
        key_drivers=[str(item) for item in parsed.get("key_drivers", [])],
        risks=[str(item) for item in parsed.get("risks", [])],
        evidence_gaps=[str(item) for item in parsed.get("evidence_gaps", [])],
        final_score=final_score,
        model=model,
        evidence_hash=evidence_hash,
        generated_at_utc=generated_at_utc,
        expires_at_utc=expires_at_utc,
        warnings=list(request.warnings),
        request=request,
    )


def _unavailable_review(
    request: DeepResearchInput,
    *,
    status: DeepResearchStatus,
    model: str,
    evidence_hash: str,
    generated_at_utc: datetime,
    expires_at_utc: datetime,
    warning: str,
) -> DeepResearchReview:
    return DeepResearchReview(
        id=_review_id(request, evidence_hash, generated_at_utc),
        symbol=request.symbol,
        research_symbol=request.research_symbol,
        broker_ticker=request.broker_ticker,
        status=status,
        decision=None,
        thesis="Deep research is unavailable, so this candidate cannot approve preview sizing.",
        price_targets=[
            PriceTarget(label="bear", price=None, rationale="Unavailable."),
            PriceTarget(label="base", price=None, rationale="Unavailable."),
            PriceTarget(label="bull", price=None, rationale="Unavailable."),
        ],
        key_drivers=[],
        risks=[warning],
        evidence_gaps=[warning],
        final_score=None,
        model=model,
        evidence_hash=evidence_hash,
        generated_at_utc=generated_at_utc,
        expires_at_utc=expires_at_utc,
        warnings=[warning, *request.warnings],
        request=request,
    )


def _openai_payload(request: DeepResearchInput, model: str) -> dict[str, Any]:
    """Build a strict JSON Responses API payload for thesis validation."""

    return {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": (
                    "You are a cautious equity research reviewer for a UK Stocks and Shares ISA "
                    "dashboard. You validate evidence for review-only, long-only buy/add ideas. "
                    "You do not provide personal financial advice or order authority. Reject or "
                    "watch candidates where evidence is stale, missing, inconsistent, or blocked."
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
                "name": "deep_research_review",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "thesis": {"type": "string"},
                        "bear_price_target": {"type": ["number", "null"]},
                        "base_price_target": {"type": ["number", "null"]},
                        "bull_price_target": {"type": ["number", "null"]},
                        "bear_case": {"type": "string"},
                        "base_case": {"type": "string"},
                        "bull_case": {"type": "string"},
                        "key_drivers": {"type": "array", "items": {"type": "string"}},
                        "risks": {"type": "array", "items": {"type": "string"}},
                        "evidence_gaps": {"type": "array", "items": {"type": "string"}},
                        "final_score": {"type": "integer", "minimum": 0, "maximum": 100},
                        "decision": {
                            "type": "string",
                            "enum": ["REJECT", "WATCH", "RESEARCH_PASSED"],
                        },
                    },
                    "required": [
                        "thesis",
                        "bear_price_target",
                        "base_price_target",
                        "bull_price_target",
                        "bear_case",
                        "base_case",
                        "bull_case",
                        "key_drivers",
                        "risks",
                        "evidence_gaps",
                        "final_score",
                        "decision",
                    ],
                },
            }
        },
    }


def _extract_structured_response(payload: dict[str, Any]) -> dict[str, Any] | None:
    output_text = payload.get("output_text")
    if isinstance(output_text, str):
        return _parse_json_object(output_text)

    for item in payload.get("output", []):
        if not isinstance(item, dict):
            continue
        content_rows = item.get("content", [])
        if not isinstance(content_rows, list):
            continue
        for content in content_rows:
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if isinstance(text, str):
                parsed = _parse_json_object(text)
                if parsed is not None:
                    return parsed
    return None


def _parse_json_object(text: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _price_targets(parsed: dict[str, Any]) -> list[PriceTarget]:
    return [
        PriceTarget(
            label="bear",
            price=_float_or_none(parsed.get("bear_price_target")),
            rationale=str(parsed.get("bear_case") or ""),
        ),
        PriceTarget(
            label="base",
            price=_float_or_none(parsed.get("base_price_target")),
            rationale=str(parsed.get("base_case") or ""),
        ),
        PriceTarget(
            label="bull",
            price=_float_or_none(parsed.get("bull_price_target")),
            rationale=str(parsed.get("bull_case") or ""),
        ),
    ]


def _decision(value: Any) -> DeepResearchDecision:
    try:
        return DeepResearchDecision(str(value))
    except ValueError:
        return DeepResearchDecision.WATCH


def _bounded_score(value: Any) -> int:
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return 0


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _review_id(request: DeepResearchInput, evidence_hash: str, generated_at_utc: datetime) -> str:
    timestamp = generated_at_utc.strftime("%Y%m%d%H%M%S")
    symbol = request.research_symbol.upper().replace(".", "-")
    return f"research-{symbol}-{timestamp}-{evidence_hash[:8]}"


def _response_json(review: DeepResearchReview) -> dict[str, Any]:
    return {
        "status": review.status.value,
        "decision": review.decision.value if review.decision else None,
        "thesis": review.thesis,
        "price_targets": [target.model_dump(mode="json") for target in review.price_targets],
        "key_drivers": review.key_drivers,
        "risks": review.risks,
        "evidence_gaps": review.evidence_gaps,
        "final_score": review.final_score,
    }


def _review_from_record(record: ResearchReviewRecord) -> DeepResearchReview:
    response_payload = json.loads(record.response_json)
    request = DeepResearchInput.model_validate(json.loads(record.request_json))
    status = DeepResearchStatus(record.status)
    generated_at_utc = _stored_utc(record.generated_at_utc)
    expires_at_utc = _stored_utc(record.expires_at_utc)
    if status == DeepResearchStatus.AVAILABLE and expires_at_utc <= now_utc():
        status = DeepResearchStatus.EXPIRED
    decision_raw = record.decision or response_payload.get("decision")
    decision = DeepResearchDecision(decision_raw) if decision_raw else None
    return DeepResearchReview(
        id=record.id,
        symbol=record.symbol,
        research_symbol=record.research_symbol,
        broker_ticker=record.broker_ticker,
        status=status,
        decision=decision,
        thesis=str(response_payload.get("thesis") or ""),
        price_targets=[
            PriceTarget.model_validate(target)
            for target in response_payload.get("price_targets", [])
            if isinstance(target, dict)
        ],
        key_drivers=[str(item) for item in response_payload.get("key_drivers", [])],
        risks=[str(item) for item in response_payload.get("risks", [])],
        evidence_gaps=[str(item) for item in response_payload.get("evidence_gaps", [])],
        final_score=record.final_score,
        model=record.model,
        evidence_hash=record.evidence_hash,
        generated_at_utc=generated_at_utc,
        expires_at_utc=expires_at_utc,
        warnings=[str(item) for item in json.loads(record.warnings_json)],
        request=request,
    )


def _stored_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return require_utc(value)
