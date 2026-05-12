"""Selected-stock deep valuation workflow with explicit source-heavy mode."""

from __future__ import annotations

import json
import re
from datetime import datetime
from enum import StrEnum
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

from isa_system.db.crud import append_audit_log
from isa_system.db.session import init_db, make_engine, make_session_factory
from isa_system.services.ai_model_config import (
    AIModelConfig,
    AIModelTask,
    get_model_config_for_task,
)
from isa_system.services.deep_research import OPENAI_RESPONSES_URL
from isa_system.services.portfolio_analytics import summarise_portfolio
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot, load_trading212_portfolio
from isa_system.services.valuation import HoldingsValuationResponse, value_current_holdings
from isa_system.settings import Settings, get_settings
from isa_system.utils.time import now_utc, require_utc


class StockRating(StrEnum):
    """Review-only stock action label."""

    ADD = "Add"
    HOLD = "Hold"
    WATCH = "Watch"
    TRIM = "Trim"
    AVOID = "Avoid"


class ConfidenceLevel(StrEnum):
    """Confidence label for research output."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DeepValuationStatus(StrEnum):
    """Availability state for a selected-stock valuation."""

    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    FAILED = "FAILED"


class BusinessQualityAssessment(BaseModel):
    """Business quality score and notes."""

    score: int = Field(ge=0, le=100)
    notes: str


class StockValuationAssessment(BaseModel):
    """Valuation method and fair-value output."""

    score: int = Field(ge=0, le=100)
    method_used: str
    fair_value_range: str
    current_price: float | None = None
    margin_of_safety: str | None = None
    assumptions: list[str] = Field(default_factory=list)


class ScenarioAssessment(BaseModel):
    """One bull/base/bear scenario."""

    summary: str
    key_assumptions: list[str] = Field(default_factory=list)
    valuation_implication: str


class StockScenarioSet(BaseModel):
    """Bull, base, and bear case scenario set."""

    bull: ScenarioAssessment
    base: ScenarioAssessment
    bear: ScenarioAssessment


class SourceLink(BaseModel):
    """Source metadata returned by source-heavy mode or model output."""

    title: str
    url: str
    publisher: str | None = None
    date: str | None = None


class StockSourcePack(BaseModel):
    """Citation-heavy source pack for a selected stock."""

    ticker: str
    model: str
    summary: str
    important_facts: list[str] = Field(default_factory=list)
    recent_developments: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    sources: list[SourceLink] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    token_usage: dict[str, Any] | None = None


class SelectedStockValuation(BaseModel):
    """Selected-stock valuation result."""

    ticker: str
    company_name: str | None = None
    rating: StockRating
    confidence: ConfidenceLevel
    summary: str
    business_quality: BusinessQualityAssessment
    valuation: StockValuationAssessment
    scenarios: StockScenarioSet
    risks: list[str] = Field(default_factory=list)
    catalysts: list[str] = Field(default_factory=list)
    thesis_breakers: list[str] = Field(default_factory=list)
    portfolio_fit: str
    sources: list[SourceLink] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    disclaimer: str
    status: DeepValuationStatus = DeepValuationStatus.AVAILABLE
    model: str
    reasoning_effort: str | None = None
    source_pack_model: str | None = None
    used_deep_research: bool = False
    token_usage: dict[str, Any] | None = None


class DeepValuationRunRequest(BaseModel):
    """API request for selected-stock deep valuation."""

    model_config = ConfigDict(extra="forbid")

    symbols: list[str] = Field(default_factory=list)
    maximum_depth: bool = False
    source_heavy: bool = False


class DeepValuationRun(BaseModel):
    """Response for one selected-stock valuation run."""

    generated_at_utc: datetime
    selected_count: int
    requested_symbols: list[str]
    maximum_depth: bool
    source_heavy: bool
    max_concurrency: int
    results: list[SelectedStockValuation]
    warnings: list[str] = Field(default_factory=list)

    @field_validator("generated_at_utc")
    @classmethod
    def _generated_at_is_utc(cls, value: datetime) -> datetime:
        return require_utc(value)


def run_selected_stock_valuations(
    symbols: list[str],
    *,
    snapshot: BrokerPortfolioSnapshot | None = None,
    valuation: HoldingsValuationResponse | None = None,
    settings: Settings | None = None,
    maximum_depth: bool = False,
    source_heavy: bool = False,
    transport: httpx.BaseTransport | None = None,
) -> DeepValuationRun:
    """Run valuation only for explicitly selected stocks."""

    app_settings = settings or get_settings()
    requested_symbols = _normalise_symbols(symbols)
    if not requested_symbols:
        raise ValueError("Select at least one stock before running deep valuation.")
    selected_limit = max(1, app_settings.openai_deep_research_selected_stock_limit)
    if len(requested_symbols) > selected_limit:
        raise ValueError(
            f"Select at most {selected_limit} stock(s) for one deep valuation run."
        )

    broker_snapshot = snapshot or load_trading212_portfolio(force_refresh=True)
    holdings_valuation = valuation or value_current_holdings(broker_snapshot)
    portfolio_context = summarise_portfolio(broker_snapshot).model_dump(mode="json")
    valuation_config = get_model_config_for_task(
        (
            AIModelTask.SELECTED_STOCK_VALUATION_MAX
            if maximum_depth
            else AIModelTask.SELECTED_STOCK_VALUATION
        ),
        settings=app_settings,
    )
    source_config = get_model_config_for_task(
        AIModelTask.SELECTED_STOCK_SOURCE_RESEARCH,
        settings=app_settings,
        explicit_source_research=source_heavy,
    )
    warnings = list(source_config.notes)
    results: list[SelectedStockValuation] = []
    for symbol in requested_symbols:
        evidence = _stock_evidence(symbol, broker_snapshot, holdings_valuation)
        source_pack = None
        if source_config.enabled:
            source_pack = _run_source_pack(
                evidence,
                portfolio_context=portfolio_context,
                settings=app_settings,
                model_config=source_config,
                transport=transport,
            )
        results.append(
            _run_stock_valuation(
                evidence,
                portfolio_context=portfolio_context,
                source_pack=source_pack,
                settings=app_settings,
                model_config=valuation_config,
                transport=transport,
            )
        )

    run = DeepValuationRun(
        generated_at_utc=now_utc(),
        selected_count=len(requested_symbols),
        requested_symbols=requested_symbols,
        maximum_depth=maximum_depth,
        source_heavy=source_config.enabled,
        max_concurrency=max(1, app_settings.openai_deep_valuation_max_concurrency),
        results=results,
        warnings=warnings,
    )
    _audit_run(
        run,
        settings=app_settings,
        valuation_config=valuation_config,
        source_config=source_config,
    )
    return run


def _run_source_pack(
    evidence: dict[str, Any],
    *,
    portfolio_context: dict[str, Any],
    settings: Settings,
    model_config: AIModelConfig,
    transport: httpx.BaseTransport | None,
) -> StockSourcePack:
    ticker = str(evidence["ticker"])
    if settings.openai_api_key is None:
        return StockSourcePack(
            ticker=ticker,
            model=model_config.model,
            summary="Source-heavy research was requested, but OPENAI_API_KEY is not configured.",
            missing_data=["OPENAI_API_KEY is not configured."],
        )
    payload = _source_pack_payload(evidence, portfolio_context, model_config)
    try:
        raw = _post_openai(payload, settings=settings, timeout=3600.0, transport=transport)
    except httpx.HTTPError as exc:
        return StockSourcePack(
            ticker=ticker,
            model=model_config.model,
            summary=f"Source-heavy research failed: {exc.__class__.__name__}.",
            missing_data=[f"Source-heavy research failed: {exc.__class__.__name__}."],
        )
    parsed = _extract_structured_response(raw) or {}
    return StockSourcePack(
        ticker=ticker,
        model=model_config.model,
        summary=str(parsed.get("summary") or "Source-heavy research pack completed."),
        important_facts=[str(item) for item in parsed.get("importantFacts", []) if item],
        recent_developments=[
            str(item) for item in parsed.get("recentDevelopments", []) if item
        ],
        risks=[str(item) for item in parsed.get("risks", []) if item],
        sources=_sources(parsed.get("sources")),
        missing_data=[str(item) for item in parsed.get("missingData", []) if item],
        token_usage=_token_usage(raw),
    )


def _run_stock_valuation(
    evidence: dict[str, Any],
    *,
    portfolio_context: dict[str, Any],
    source_pack: StockSourcePack | None,
    settings: Settings,
    model_config: AIModelConfig,
    transport: httpx.BaseTransport | None,
) -> SelectedStockValuation:
    if settings.openai_api_key is None:
        return _fallback_valuation(
            evidence,
            model_config=model_config,
            source_pack=source_pack,
            status=DeepValuationStatus.UNAVAILABLE,
            warning="OPENAI_API_KEY is not configured; deep valuation cannot run.",
        )
    payload = _valuation_payload(evidence, portfolio_context, source_pack, model_config)
    try:
        raw = _post_openai(payload, settings=settings, timeout=240.0, transport=transport)
    except httpx.HTTPError as exc:
        return _fallback_valuation(
            evidence,
            model_config=model_config,
            source_pack=source_pack,
            status=DeepValuationStatus.FAILED,
            warning=f"OpenAI selected-stock valuation failed: {exc.__class__.__name__}.",
        )
    parsed = _extract_structured_response(raw)
    if parsed is None:
        return _fallback_valuation(
            evidence,
            model_config=model_config,
            source_pack=source_pack,
            status=DeepValuationStatus.FAILED,
            warning="OpenAI response did not contain parseable selected-stock valuation JSON.",
        )
    return _valuation_from_payload(
        evidence,
        parsed,
        model_config=model_config,
        source_pack=source_pack,
        raw_response=raw,
    )


def _post_openai(
    payload: dict[str, Any],
    *,
    settings: Settings,
    timeout: float,
    transport: httpx.BaseTransport | None,
) -> dict[str, Any]:
    assert settings.openai_api_key is not None
    with httpx.Client(timeout=timeout, transport=transport) as client:
        response = client.post(
            OPENAI_RESPONSES_URL,
            headers={
                "Authorization": f"Bearer {settings.openai_api_key.get_secret_value()}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
    raw = response.json()
    return raw if isinstance(raw, dict) else {}


def _source_pack_payload(
    evidence: dict[str, Any],
    portfolio_context: dict[str, Any],
    model_config: AIModelConfig,
) -> dict[str, Any]:
    return {
        "model": model_config.model,
        "input": [
            {
                "role": "system",
                "content": (
                    "You gather source-heavy equity research facts for a UK ISA operator. "
                    "Return concise JSON with source links. Do not make the final investment "
                    "judgement."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "task": "Gather recent source-backed facts for this selected stock only.",
                        "required_json_shape": {
                            "summary": "string",
                            "importantFacts": ["string"],
                            "recentDevelopments": ["string"],
                            "risks": ["string"],
                            "sources": [
                                {
                                    "title": "string",
                                    "url": "string",
                                    "publisher": "string or null",
                                    "date": "string or null",
                                }
                            ],
                            "missingData": ["string"],
                        },
                        "stock_evidence": evidence,
                        "portfolio_context": portfolio_context,
                    },
                    sort_keys=True,
                ),
            },
        ],
        "tools": [{"type": "web_search_preview"}],
        "max_output_tokens": model_config.max_output_tokens,
        "text": {"format": {"type": "json_object"}},
    }


def _valuation_payload(
    evidence: dict[str, Any],
    portfolio_context: dict[str, Any],
    source_pack: StockSourcePack | None,
    model_config: AIModelConfig,
) -> dict[str, Any]:
    return {
        "model": model_config.model,
        "input": [
            {
                "role": "system",
                "content": (
                    "You are a cautious equity valuation analyst for a local UK ISA operator "
                    "cockpit. Produce research and decision-support JSON only. This is not "
                    "personal financial advice and not order authority."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "task": (
                            "Perform a full valuation for the selected stock only. Use local "
                            "portfolio and fundamental data first. Use source_pack facts only "
                            "when supplied. Do not invent financial metrics."
                        ),
                        "required_json_shape": {
                            "ticker": "string",
                            "companyName": "string or null",
                            "rating": "Add | Hold | Watch | Trim | Avoid",
                            "confidence": "low | medium | high",
                            "summary": "string",
                            "businessQuality": {"score": "0-100 integer", "notes": "string"},
                            "valuation": {
                                "score": "0-100 integer",
                                "methodUsed": "string",
                                "fairValueRange": "string",
                                "currentPrice": "number or null",
                                "marginOfSafety": "string or null",
                                "assumptions": ["string"],
                            },
                            "scenarios": {
                                "bull": {
                                    "summary": "string",
                                    "keyAssumptions": ["string"],
                                    "valuationImplication": "string",
                                },
                                "base": {
                                    "summary": "string",
                                    "keyAssumptions": ["string"],
                                    "valuationImplication": "string",
                                },
                                "bear": {
                                    "summary": "string",
                                    "keyAssumptions": ["string"],
                                    "valuationImplication": "string",
                                },
                            },
                            "risks": ["string"],
                            "catalysts": ["string"],
                            "thesisBreakers": ["string"],
                            "portfolioFit": "string",
                            "sources": [
                                {
                                    "title": "string",
                                    "url": "string",
                                    "publisher": "string or null",
                                    "date": "string or null",
                                }
                            ],
                            "missingData": ["string"],
                            "disclaimer": "string",
                        },
                        "rules": [
                            "Separate facts, assumptions, and judgement.",
                            "Use DCF or owner-earnings valuation only where enough data exists.",
                            "If data is missing, stale, or unavailable, say so in missingData.",
                            "Avoid definitive predictions.",
                            "Explain why the rating is Add, Hold, Watch, Trim, or Avoid.",
                            "Consider portfolio fit against current holdings and concentration.",
                        ],
                        "stock_evidence": evidence,
                        "portfolio_context": portfolio_context,
                        "source_pack": source_pack.model_dump(mode="json")
                        if source_pack is not None
                        else None,
                    },
                    sort_keys=True,
                ),
            },
        ],
        "reasoning": {"effort": model_config.reasoning_effort},
        "max_output_tokens": model_config.max_output_tokens,
        "text": {"format": {"type": "json_object"}},
    }


def _valuation_from_payload(
    evidence: dict[str, Any],
    payload: dict[str, Any],
    *,
    model_config: AIModelConfig,
    source_pack: StockSourcePack | None,
    raw_response: dict[str, Any],
) -> SelectedStockValuation:
    valuation_payload = payload.get("valuation") if isinstance(payload.get("valuation"), dict) else {}
    business_payload = (
        payload.get("businessQuality") if isinstance(payload.get("businessQuality"), dict) else {}
    )
    scenarios_payload = payload.get("scenarios") if isinstance(payload.get("scenarios"), dict) else {}
    sources = _sources(payload.get("sources"))
    if source_pack is not None and not sources:
        sources = source_pack.sources
    missing_data = [str(item) for item in payload.get("missingData", []) if item]
    missing_data.extend(_missing_data(evidence))
    if source_pack is not None:
        missing_data.extend(source_pack.missing_data)
    return SelectedStockValuation(
        ticker=str(payload.get("ticker") or evidence["ticker"]),
        company_name=_string_or_none(payload.get("companyName") or evidence.get("company_name")),
        rating=_rating(payload.get("rating")),
        confidence=_confidence(payload.get("confidence")),
        summary=str(payload.get("summary") or "Selected-stock valuation completed."),
        business_quality=BusinessQualityAssessment(
            score=_bounded_score(business_payload.get("score")),
            notes=str(business_payload.get("notes") or "No business-quality notes supplied."),
        ),
        valuation=StockValuationAssessment(
            score=_bounded_score(valuation_payload.get("score")),
            method_used=str(valuation_payload.get("methodUsed") or "not_supplied"),
            fair_value_range=str(valuation_payload.get("fairValueRange") or "not_available"),
            current_price=_float_or_none(
                valuation_payload.get("currentPrice") or evidence.get("current_price")
            ),
            margin_of_safety=_string_or_none(valuation_payload.get("marginOfSafety")),
            assumptions=[str(item) for item in valuation_payload.get("assumptions", []) if item],
        ),
        scenarios=_scenarios(scenarios_payload),
        risks=[str(item) for item in payload.get("risks", []) if item],
        catalysts=[str(item) for item in payload.get("catalysts", []) if item],
        thesis_breakers=[str(item) for item in payload.get("thesisBreakers", []) if item],
        portfolio_fit=str(payload.get("portfolioFit") or "Portfolio fit was not supplied."),
        sources=sources,
        missing_data=_dedupe(missing_data),
        disclaimer=str(
            payload.get("disclaimer")
            or "This output is research and decision support, not personal financial advice."
        ),
        model=model_config.model,
        reasoning_effort=model_config.reasoning_effort,
        source_pack_model=source_pack.model if source_pack is not None else None,
        used_deep_research=source_pack is not None,
        token_usage=_token_usage(raw_response),
    )


def _fallback_valuation(
    evidence: dict[str, Any],
    *,
    model_config: AIModelConfig,
    source_pack: StockSourcePack | None,
    status: DeepValuationStatus,
    warning: str,
) -> SelectedStockValuation:
    missing = _missing_data(evidence)
    missing.append(warning)
    if source_pack is not None:
        missing.extend(source_pack.missing_data)
    current_price = _float_or_none(evidence.get("current_price"))
    return SelectedStockValuation(
        ticker=str(evidence["ticker"]),
        company_name=_string_or_none(evidence.get("company_name")),
        rating=StockRating.WATCH,
        confidence=ConfidenceLevel.LOW,
        summary=(
            "Deep valuation did not produce a model-backed judgement. Review the local "
            "portfolio data and missing-data list before taking any action."
        ),
        business_quality=BusinessQualityAssessment(
            score=0,
            notes="Business quality was not assessed because the model workflow was unavailable.",
        ),
        valuation=StockValuationAssessment(
            score=0,
            method_used="not_available",
            fair_value_range="not_available",
            current_price=current_price,
            margin_of_safety=None,
            assumptions=[],
        ),
        scenarios=StockScenarioSet(
            bull=ScenarioAssessment(
                summary="Unavailable.",
                key_assumptions=[],
                valuation_implication="No bull valuation was generated.",
            ),
            base=ScenarioAssessment(
                summary="Unavailable.",
                key_assumptions=[],
                valuation_implication="No base valuation was generated.",
            ),
            bear=ScenarioAssessment(
                summary="Unavailable.",
                key_assumptions=[],
                valuation_implication="No bear valuation was generated.",
            ),
        ),
        risks=[warning],
        catalysts=[],
        thesis_breakers=[],
        portfolio_fit="Portfolio fit could not be assessed by the model workflow.",
        sources=source_pack.sources if source_pack is not None else [],
        missing_data=_dedupe(missing),
        disclaimer=(
            "This output is research and decision support for manual review, not personal "
            "financial advice or order authority."
        ),
        status=status,
        model=model_config.model,
        reasoning_effort=model_config.reasoning_effort,
        source_pack_model=source_pack.model if source_pack is not None else None,
        used_deep_research=source_pack is not None,
        token_usage=None,
    )


def _stock_evidence(
    symbol: str,
    snapshot: BrokerPortfolioSnapshot,
    valuation: HoldingsValuationResponse,
) -> dict[str, Any]:
    key = symbol.upper()
    position = next(
        (
            row
            for row in snapshot.positions
            if key in {row.symbol.upper(), row.broker_ticker.upper()}
        ),
        None,
    )
    valuation_row = next(
        (
            row
            for row in valuation.holdings
            if key in {row.symbol.upper(), row.broker_ticker.upper(), row.research_symbol.upper()}
        ),
        None,
    )
    ticker = (
        valuation_row.research_symbol
        if valuation_row is not None
        else position.symbol
        if position is not None
        else symbol
    )
    return {
        "ticker": ticker,
        "broker_symbol": position.symbol if position is not None else None,
        "broker_ticker": position.broker_ticker if position is not None else None,
        "company_name": (valuation_row.name if valuation_row is not None else None)
        or (position.name if position is not None else None),
        "isin": position.isin if position is not None else None,
        "currency": (valuation_row.currency if valuation_row is not None else None)
        or (position.currency if position is not None else None),
        "quantity": position.quantity if position is not None else None,
        "average_price_paid": position.average_price_paid if position is not None else None,
        "current_price": (valuation_row.current_price if valuation_row is not None else None)
        or (position.current_price if position is not None else None),
        "current_value": (valuation_row.current_value if valuation_row is not None else None)
        or (position.current_value if position is not None else None),
        "valuation": valuation_row.valuation.model_dump(mode="json")
        if valuation_row is not None
        else {},
        "technicals": valuation_row.technicals.model_dump(mode="json")
        if valuation_row is not None
        else {},
        "upcoming_events": [
            event.model_dump(mode="json") for event in valuation_row.upcoming_events
        ]
        if valuation_row is not None
        else [],
        "news": [news.model_dump(mode="json") for news in valuation_row.news]
        if valuation_row is not None
        else [],
        "warnings": [
            *(snapshot.warnings or []),
            *(valuation.warnings or []),
            *((valuation_row.warnings if valuation_row is not None else []) or []),
        ],
        "selected_from_current_holdings": position is not None,
    }


def _audit_run(
    run: DeepValuationRun,
    *,
    settings: Settings,
    valuation_config: AIModelConfig,
    source_config: AIModelConfig,
) -> None:
    engine = make_engine(settings.operational_db_dsn)
    init_db(engine)
    factory = make_session_factory(engine)
    with factory() as session:
        append_audit_log(
            session,
            actor="system.stock_valuation",
            action="selected_stock_valuation.run",
            payload={
                "selected_count": run.selected_count,
                "maximum_depth": run.maximum_depth,
                "source_heavy": run.source_heavy,
                "valuation_model": valuation_config.model,
                "valuation_reasoning_effort": valuation_config.reasoning_effort,
                "source_model": source_config.model if source_config.enabled else None,
                "used_deep_research": source_config.enabled,
                "token_usage": {
                    item.ticker: item.token_usage for item in run.results if item.token_usage
                },
            },
            outcome="completed",
        )
        session.commit()


def _extract_structured_response(payload: dict[str, Any]) -> dict[str, Any] | None:
    output_text = payload.get("output_text")
    if isinstance(output_text, str):
        return _parse_json_object(output_text)
    for item in payload.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
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
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match is None:
            return None
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, dict) else None


def _scenarios(payload: dict[str, Any]) -> StockScenarioSet:
    return StockScenarioSet(
        bull=_scenario(payload.get("bull")),
        base=_scenario(payload.get("base")),
        bear=_scenario(payload.get("bear")),
    )


def _scenario(payload: Any) -> ScenarioAssessment:
    row = payload if isinstance(payload, dict) else {}
    return ScenarioAssessment(
        summary=str(row.get("summary") or "Not supplied."),
        key_assumptions=[str(item) for item in row.get("keyAssumptions", []) if item],
        valuation_implication=str(row.get("valuationImplication") or "Not supplied."),
    )


def _sources(payload: Any) -> list[SourceLink]:
    if not isinstance(payload, list):
        return []
    rows: list[SourceLink] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        if not title or not url:
            continue
        rows.append(
            SourceLink(
                title=title,
                url=url,
                publisher=_string_or_none(item.get("publisher")),
                date=_string_or_none(item.get("date")),
            )
        )
    return rows


def _missing_data(evidence: dict[str, Any]) -> list[str]:
    ticker = str(evidence["ticker"])
    missing: list[str] = []
    if not evidence.get("selected_from_current_holdings"):
        missing.append(f"{ticker}: not found in current broker holdings.")
    if evidence.get("current_price") is None:
        missing.append(f"{ticker}: current price is unavailable.")
    valuation = evidence.get("valuation") if isinstance(evidence.get("valuation"), dict) else {}
    if not valuation or all(value is None for value in valuation.values()):
        missing.append(f"{ticker}: valuation metrics are unavailable.")
    technicals = evidence.get("technicals") if isinstance(evidence.get("technicals"), dict) else {}
    if not technicals or all(value is None for value in technicals.values()):
        missing.append(f"{ticker}: technical history is unavailable.")
    return missing


def _normalise_symbols(symbols: list[str]) -> list[str]:
    clean: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        value = str(symbol or "").strip()
        key = value.upper()
        if not value or key in seen:
            continue
        clean.append(value)
        seen.add(key)
    return clean


def _rating(value: Any) -> StockRating:
    try:
        return StockRating(str(value))
    except ValueError:
        return StockRating.WATCH


def _confidence(value: Any) -> ConfidenceLevel:
    try:
        return ConfidenceLevel(str(value))
    except ValueError:
        return ConfidenceLevel.LOW


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


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _token_usage(raw_response: dict[str, Any] | None) -> dict[str, Any] | None:
    if not raw_response:
        return None
    usage = raw_response.get("usage")
    return usage if isinstance(usage, dict) else None


def _dedupe(items: list[str]) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item).strip()
        if not text or text in seen:
            continue
        rows.append(text)
        seen.add(text)
    return rows
