"""OpenAI-backed health reports for current holdings."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import httpx
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from isa_system.db.crud import append_audit_log
from isa_system.db.models import (
    HoldingHealthReportRecord,
    HoldingHealthUpdateRecord,
)
from isa_system.db.session import init_db, make_engine, make_session_factory
from isa_system.services.deep_research import OPENAI_RESPONSES_URL
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot, load_trading212_portfolio
from isa_system.services.valuation import HoldingsValuationResponse, value_current_holdings
from isa_system.settings import Settings, get_settings
from isa_system.utils.hashing import sha256_digest
from isa_system.utils.time import now_utc, require_utc


class HoldingHealthAction(StrEnum):
    """Review-only action label for a current holding."""

    BUY_MORE = "BUY_MORE"
    SELL = "SELL"
    HOLD = "HOLD"
    TRIM = "TRIM"
    REVIEW = "REVIEW"


class HoldingHealthReportStatus(StrEnum):
    """Availability state for a holding health report run."""

    AVAILABLE = "AVAILABLE"
    DETERMINISTIC_FALLBACK = "DETERMINISTIC_FALLBACK"
    FAILED = "FAILED"


class HealthPriceTargets(BaseModel):
    """Bear, base, and bull case price targets for one holding."""

    bear: float | None = None
    base: float | None = None
    bull: float | None = None


class HoldingHealthInput(BaseModel):
    """Compact evidence packet for one current holding."""

    symbol: str
    broker_ticker: str
    research_symbol: str
    company_name: str | None = None
    isin: str | None = None
    currency: str | None = None
    quantity: float
    average_price_paid: float | None = None
    current_price: float | None = None
    current_value: float | None = None
    current_weight_pct: float | None = None
    valuation: dict[str, Any] = Field(default_factory=dict)
    technicals: dict[str, Any] = Field(default_factory=dict)
    upcoming_events: list[dict[str, Any]] = Field(default_factory=list)
    news: list[dict[str, Any]] = Field(default_factory=list)
    sentiment: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)


class HoldingHealthReportInput(BaseModel):
    """Evidence packet sent to the health report researcher."""

    status: str
    environment: str
    account_currency: str | None = None
    total_value: float | None = None
    available_to_trade: float | None = None
    retrieved_at_utc: datetime
    valuation_retrieved_at_utc: datetime | None = None
    holdings: list[HoldingHealthInput]
    previous_operator_updates: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("retrieved_at_utc", "valuation_retrieved_at_utc")
    @classmethod
    def _timestamps_are_utc(cls, value: datetime | None) -> datetime | None:
        return require_utc(value) if value is not None else None


class HoldingHealthAssessment(BaseModel):
    """One holding assessment in a health report run."""

    symbol: str
    broker_ticker: str | None = None
    research_symbol: str | None = None
    company_name: str | None = None
    current_price: float | None = None
    current_value: float | None = None
    current_weight_pct: float | None = None
    recommended_action: HoldingHealthAction
    action_rationale: str
    price_targets: HealthPriceTargets
    bear_case: str
    base_case: str
    bull_case: str
    key_risks: list[str] = Field(default_factory=list)
    evidence_gaps: list[str] = Field(default_factory=list)
    confidence_score: int = Field(ge=0, le=100)


class HoldingHealthReport(BaseModel):
    """Persisted health report with per-holding target/action updates."""

    id: str
    status: HoldingHealthReportStatus
    model: str
    generated_at_utc: datetime
    holdings_snapshot_at_utc: datetime
    holding_count: int
    evidence_hash: str
    summary: str
    portfolio_level_notes: list[str] = Field(default_factory=list)
    assessments: list[HoldingHealthAssessment] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    raw_response: dict[str, Any] | None = None

    @field_validator("generated_at_utc", "holdings_snapshot_at_utc")
    @classmethod
    def _timestamps_are_utc(cls, value: datetime) -> datetime:
        return require_utc(value)


class HoldingHealthUpdate(BaseModel):
    """Operator acceptance or adjustment of one health report assessment."""

    id: str
    report_id: str
    symbol: str
    updated_at_utc: datetime
    accepted_price_targets: HealthPriceTargets
    carried_forward_action: HoldingHealthAction
    adjusted: bool
    notes: str | None = None

    @field_validator("updated_at_utc")
    @classmethod
    def _updated_at_is_utc(cls, value: datetime) -> datetime:
        return require_utc(value)


class HoldingHealthUpdateRequest(BaseModel):
    """Request to accept or adjust one assessment from a health report."""

    price_targets: HealthPriceTargets | None = None
    carried_forward_action: HoldingHealthAction | None = None
    notes: str | None = None


class HoldingHealthReportDetail(BaseModel):
    """Report plus accepted or adjusted rows linked to it."""

    report: HoldingHealthReport
    updates: list[HoldingHealthUpdate] = Field(default_factory=list)


def run_holding_health_report(
    snapshot: BrokerPortfolioSnapshot | None = None,
    valuation: HoldingsValuationResponse | None = None,
    *,
    settings: Settings | None = None,
    transport: httpx.BaseTransport | None = None,
    persist: bool = True,
) -> HoldingHealthReport:
    """Generate and optionally persist a holdings health report.

    If an OpenAI key is configured, this uses the configured health model. The
    default model is the dedicated deep research model. If no key is configured
    or the model call fails, a conservative deterministic report is persisted so
    history and dashboard tests remain available without provider secrets.
    """

    app_settings = settings or get_settings()
    broker_snapshot = snapshot or load_trading212_portfolio(force_refresh=True)
    holdings_valuation = valuation or value_current_holdings(broker_snapshot)
    previous_updates = latest_holding_health_updates(
        [position.symbol for position in broker_snapshot.positions], settings=app_settings
    )
    report_input = build_holding_health_input(
        broker_snapshot,
        holdings_valuation,
        previous_updates=list(previous_updates.values()),
    )
    generated_at_utc = now_utc()
    evidence_hash = sha256_digest(report_input.model_dump(mode="json"))

    if not report_input.holdings:
        report = _deterministic_report(
            report_input,
            model="local-rules",
            status=HoldingHealthReportStatus.AVAILABLE,
            evidence_hash=evidence_hash,
            generated_at_utc=generated_at_utc,
            extra_warning="No current holdings were available for a health check.",
        )
    elif app_settings.openai_api_key is None:
        report = _deterministic_report(
            report_input,
            model=app_settings.openai_health_model,
            status=HoldingHealthReportStatus.DETERMINISTIC_FALLBACK,
            evidence_hash=evidence_hash,
            generated_at_utc=generated_at_utc,
            extra_warning=(
                "OPENAI_API_KEY is not configured; generated a deterministic "
                "operator-review fallback instead of an OpenAI deep research report."
            ),
        )
    else:
        report = _run_openai_health_report(
            report_input,
            settings=app_settings,
            transport=transport,
            evidence_hash=evidence_hash,
            generated_at_utc=generated_at_utc,
        )

    if persist:
        persist_holding_health_report(report, settings=app_settings)
    return report


def build_holding_health_input(
    snapshot: BrokerPortfolioSnapshot,
    valuation: HoldingsValuationResponse | None = None,
    *,
    previous_updates: list[HoldingHealthUpdate] | None = None,
) -> HoldingHealthReportInput:
    """Create the auditable evidence packet for the current holdings."""

    valuation_by_symbol: dict[str, Any] = {}
    if valuation is not None:
        for row in valuation.holdings:
            valuation_by_symbol[row.symbol.upper()] = row
            valuation_by_symbol[row.research_symbol.upper()] = row

    total_value = snapshot.total_value or sum(
        position.current_value or 0.0 for position in snapshot.positions
    )
    holdings: list[HoldingHealthInput] = []
    for position in snapshot.positions:
        valuation_row = valuation_by_symbol.get(position.symbol.upper())
        research_symbol = (
            valuation_row.research_symbol if valuation_row is not None else position.symbol
        )
        current_value = position.current_value or (
            position.quantity * position.current_price
            if position.current_price is not None
            else None
        )
        weight = (
            round((current_value / total_value) * 100, 4)
            if current_value is not None and total_value
            else None
        )
        holdings.append(
            HoldingHealthInput(
                symbol=position.symbol,
                broker_ticker=position.broker_ticker,
                research_symbol=research_symbol,
                company_name=position.name,
                isin=position.isin,
                currency=position.currency,
                quantity=position.quantity,
                average_price_paid=position.average_price_paid,
                current_price=position.current_price,
                current_value=current_value,
                current_weight_pct=weight,
                valuation=(
                    valuation_row.valuation.model_dump(mode="json")
                    if valuation_row is not None
                    else {}
                ),
                technicals=(
                    valuation_row.technicals.model_dump(mode="json")
                    if valuation_row is not None
                    else {}
                ),
                upcoming_events=(
                    [event.model_dump(mode="json") for event in valuation_row.upcoming_events]
                    if valuation_row is not None
                    else []
                ),
                news=(
                    [news.model_dump(mode="json") for news in valuation_row.news]
                    if valuation_row is not None
                    else []
                ),
                sentiment=(
                    valuation_row.sentiment.model_dump(mode="json")
                    if valuation_row is not None and valuation_row.sentiment is not None
                    else None
                ),
                warnings=valuation_row.warnings if valuation_row is not None else [],
            )
        )

    return HoldingHealthReportInput(
        status=snapshot.status,
        environment=snapshot.environment,
        account_currency=snapshot.account_currency,
        total_value=snapshot.total_value,
        available_to_trade=snapshot.available_to_trade,
        retrieved_at_utc=snapshot.retrieved_at_utc,
        valuation_retrieved_at_utc=valuation.retrieved_at_utc if valuation is not None else None,
        holdings=holdings,
        previous_operator_updates=[
            update.model_dump(mode="json") for update in previous_updates or []
        ],
        warnings=[
            *snapshot.warnings,
            *((valuation.warnings if valuation is not None else []) or []),
        ],
    )


def persist_holding_health_report(
    report: HoldingHealthReport, *, settings: Settings | None = None
) -> None:
    """Persist a health report and append an audit event."""

    app_settings = settings or get_settings()
    engine = make_engine(app_settings.operational_db_dsn)
    init_db(engine)
    factory = make_session_factory(engine)
    with factory() as session:
        session.merge(
            HoldingHealthReportRecord(
                id=report.id,
                status=report.status.value,
                model=report.model,
                generated_at_utc=report.generated_at_utc,
                holdings_snapshot_at_utc=report.holdings_snapshot_at_utc,
                holding_count=report.holding_count,
                evidence_hash=report.evidence_hash,
                payload_json=report.model_dump_json(),
                warnings_json=json.dumps(report.warnings, sort_keys=True),
            )
        )
        append_audit_log(
            session,
            actor="system.holding_health",
            action="holding_health_report.run",
            payload={
                "report_id": report.id,
                "status": report.status.value,
                "holding_count": report.holding_count,
                "evidence_hash": report.evidence_hash,
            },
            outcome=report.status.value,
        )
        session.commit()


def list_holding_health_reports(
    *, settings: Settings | None = None, limit: int = 20
) -> list[HoldingHealthReport]:
    """Return recent health report history, newest first."""

    app_settings = settings or get_settings()
    engine = make_engine(app_settings.operational_db_dsn)
    init_db(engine)
    factory = make_session_factory(engine)
    with factory() as session:
        records = session.scalars(
            select(HoldingHealthReportRecord)
            .order_by(HoldingHealthReportRecord.generated_at_utc.desc())
            .limit(limit)
        ).all()
    return [_report_from_record(record) for record in records]


def get_holding_health_report(
    report_id: str, *, settings: Settings | None = None
) -> HoldingHealthReport | None:
    """Return one persisted health report by ID."""

    app_settings = settings or get_settings()
    engine = make_engine(app_settings.operational_db_dsn)
    init_db(engine)
    factory = make_session_factory(engine)
    with factory() as session:
        record = session.get(HoldingHealthReportRecord, report_id)
    return _report_from_record(record) if record is not None else None


def latest_holding_health_report(*, settings: Settings | None = None) -> HoldingHealthReport | None:
    """Return the latest persisted health report."""

    reports = list_holding_health_reports(settings=settings, limit=1)
    return reports[0] if reports else None


def get_holding_health_report_detail(
    report_id: str, *, settings: Settings | None = None
) -> HoldingHealthReportDetail | None:
    """Return a report and all updates linked to it."""

    report = get_holding_health_report(report_id, settings=settings)
    if report is None:
        return None
    return HoldingHealthReportDetail(
        report=report,
        updates=list_holding_health_updates(report_id=report_id, settings=settings),
    )


def latest_holding_health_report_detail(
    *, settings: Settings | None = None
) -> HoldingHealthReportDetail | None:
    """Return the latest report plus its linked updates."""

    report = latest_holding_health_report(settings=settings)
    if report is None:
        return None
    return HoldingHealthReportDetail(
        report=report,
        updates=list_holding_health_updates(report_id=report.id, settings=settings),
    )


def list_holding_health_updates(
    *, report_id: str | None = None, settings: Settings | None = None
) -> list[HoldingHealthUpdate]:
    """Return health target/action updates, newest first."""

    app_settings = settings or get_settings()
    engine = make_engine(app_settings.operational_db_dsn)
    init_db(engine)
    factory = make_session_factory(engine)
    statement = select(HoldingHealthUpdateRecord).order_by(
        HoldingHealthUpdateRecord.updated_at_utc.desc()
    )
    if report_id is not None:
        statement = statement.where(HoldingHealthUpdateRecord.report_id == report_id)
    with factory() as session:
        records = session.scalars(statement).all()
    return [_update_from_record(record) for record in records]


def latest_holding_health_updates(
    symbols: list[str], *, settings: Settings | None = None
) -> dict[str, HoldingHealthUpdate]:
    """Return the latest accepted target/action update per requested symbol."""

    keys = {symbol.upper() for symbol in symbols if symbol}
    if not keys:
        return {}
    app_settings = settings or get_settings()
    engine = make_engine(app_settings.operational_db_dsn)
    init_db(engine)
    factory = make_session_factory(engine)
    with factory() as session:
        records = session.scalars(
            select(HoldingHealthUpdateRecord)
            .where(HoldingHealthUpdateRecord.symbol.in_(keys))
            .order_by(HoldingHealthUpdateRecord.updated_at_utc.desc())
        ).all()
    updates: dict[str, HoldingHealthUpdate] = {}
    for record in records:
        key = record.symbol.upper()
        if key not in updates:
            updates[key] = _update_from_record(record)
    return updates


def accept_holding_health_update(
    report_id: str,
    symbol: str,
    request: HoldingHealthUpdateRequest,
    *,
    settings: Settings | None = None,
) -> HoldingHealthUpdate:
    """Persist an accepted or operator-adjusted price target/action update."""

    app_settings = settings or get_settings()
    report = get_holding_health_report(report_id, settings=app_settings)
    if report is None:
        raise ValueError(f"Health report {report_id} was not found.")
    assessment = _assessment_for_symbol(report, symbol)
    if assessment is None:
        raise ValueError(f"Symbol {symbol} was not found in health report {report_id}.")

    accepted_targets = request.price_targets or assessment.price_targets
    accepted_action = request.carried_forward_action or assessment.recommended_action
    adjusted = (
        accepted_targets != assessment.price_targets
        or accepted_action != assessment.recommended_action
    )
    updated_at_utc = now_utc()
    payload = {
        "accepted_price_targets": accepted_targets.model_dump(mode="json"),
        "carried_forward_action": accepted_action.value,
        "source_report_id": report_id,
        "source_assessment": assessment.model_dump(mode="json"),
    }
    update = HoldingHealthUpdate(
        id=_update_id(report_id, assessment.symbol, payload, updated_at_utc),
        report_id=report_id,
        symbol=assessment.symbol,
        updated_at_utc=updated_at_utc,
        accepted_price_targets=accepted_targets,
        carried_forward_action=accepted_action,
        adjusted=adjusted,
        notes=request.notes,
    )

    engine = make_engine(app_settings.operational_db_dsn)
    init_db(engine)
    factory = make_session_factory(engine)
    with factory() as session:
        session.add(
            HoldingHealthUpdateRecord(
                id=update.id,
                report_id=update.report_id,
                symbol=update.symbol.upper(),
                updated_at_utc=update.updated_at_utc,
                carried_forward_action=update.carried_forward_action.value,
                adjusted=1 if update.adjusted else 0,
                payload_json=update.model_dump_json(),
                notes=update.notes,
            )
        )
        append_audit_log(
            session,
            actor="operator.health_check",
            action="holding_health_update.accept",
            payload={
                "update_id": update.id,
                "report_id": report_id,
                "symbol": update.symbol,
                "adjusted": update.adjusted,
                "carried_forward_action": update.carried_forward_action.value,
            },
            outcome="accepted_adjusted" if update.adjusted else "accepted",
        )
        session.commit()
    return update


def _run_openai_health_report(
    report_input: HoldingHealthReportInput,
    *,
    settings: Settings,
    transport: httpx.BaseTransport | None,
    evidence_hash: str,
    generated_at_utc: datetime,
) -> HoldingHealthReport:
    model = settings.openai_health_model
    assert settings.openai_api_key is not None
    try:
        with httpx.Client(timeout=3600.0, transport=transport) as client:
            response = client.post(
                OPENAI_RESPONSES_URL,
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key.get_secret_value()}",
                    "Content-Type": "application/json",
                },
                json=_openai_payload(report_input, model),
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        return _deterministic_report(
            report_input,
            model=model,
            status=HoldingHealthReportStatus.FAILED,
            evidence_hash=evidence_hash,
            generated_at_utc=generated_at_utc,
            extra_warning=f"OpenAI holdings health report failed: {exc.__class__.__name__}.",
        )

    raw_response = response.json()
    parsed = _extract_structured_response(raw_response)
    if parsed is None:
        return _deterministic_report(
            report_input,
            model=model,
            status=HoldingHealthReportStatus.FAILED,
            evidence_hash=evidence_hash,
            generated_at_utc=generated_at_utc,
            extra_warning="OpenAI response did not contain parseable holding health JSON.",
            raw_response=raw_response,
        )

    return _report_from_model_response(
        report_input,
        parsed=parsed,
        model=model,
        evidence_hash=evidence_hash,
        generated_at_utc=generated_at_utc,
        raw_response=raw_response,
    )


def _openai_payload(report_input: HoldingHealthReportInput, model: str) -> dict[str, Any]:
    prompt = {
        "task": (
            "Produce a current-holdings health report for a UK Stocks and Shares ISA "
            "operator cockpit. Use only the supplied portfolio evidence plus your web "
            "research. Return JSON only. This is review-only research, not personal "
            "financial advice and not order authority."
        ),
        "required_json_shape": {
            "summary": "string",
            "portfolio_level_notes": ["string"],
            "warnings": ["string"],
            "assessments": [
                {
                    "symbol": "string matching a supplied holding symbol",
                    "recommended_action": "BUY_MORE | SELL | HOLD | TRIM | REVIEW",
                    "action_rationale": "string",
                    "bear_case_price_target": "number or null",
                    "base_case_price_target": "number or null",
                    "bull_case_price_target": "number or null",
                    "bear_case": "string",
                    "base_case": "string",
                    "bull_case": "string",
                    "key_risks": ["string"],
                    "evidence_gaps": ["string"],
                    "confidence_score": "integer 0-100",
                }
            ],
        },
        "rules": [
            "Do not recommend live execution.",
            "Use BUY_MORE only when the updated case and entry quality are both strong.",
            "Use HOLD or REVIEW when evidence is incomplete or mixed.",
            "Use SELL or TRIM only when the thesis appears broken, risk/reward is poor, "
            "or sizing risk is high.",
            "Do not fabricate unavailable company facts; put them in evidence_gaps.",
            "Include bear, base, and bull targets only when supportable from the evidence "
            "and current research.",
            "Targets must be in the holding's trading currency where known.",
        ],
        "portfolio_evidence": report_input.model_dump(mode="json"),
    }
    payload: dict[str, Any] = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": (
                    "You are a cautious equity research analyst preparing a review-only "
                    "holdings health check for a local UK ISA operator cockpit."
                ),
            },
            {"role": "user", "content": json.dumps(prompt, sort_keys=True)},
        ],
    }
    if "deep-research" in model:
        payload["tools"] = [{"type": "web_search_preview"}]
    return payload


def _report_from_model_response(
    report_input: HoldingHealthReportInput,
    *,
    parsed: dict[str, Any],
    model: str,
    evidence_hash: str,
    generated_at_utc: datetime,
    raw_response: dict[str, Any],
) -> HoldingHealthReport:
    assessment_by_symbol = {
        str(item.get("symbol", "")).upper(): item
        for item in parsed.get("assessments", [])
        if isinstance(item, dict)
    }
    assessments = [
        _assessment_from_model_payload(holding, assessment_by_symbol.get(holding.symbol.upper()))
        for holding in report_input.holdings
    ]
    warnings = [str(item) for item in parsed.get("warnings", []) if item]
    return HoldingHealthReport(
        id=_report_id(evidence_hash, generated_at_utc),
        status=HoldingHealthReportStatus.AVAILABLE,
        model=model,
        generated_at_utc=generated_at_utc,
        holdings_snapshot_at_utc=report_input.retrieved_at_utc,
        holding_count=len(report_input.holdings),
        evidence_hash=evidence_hash,
        summary=str(parsed.get("summary") or "Holdings health report completed."),
        portfolio_level_notes=[
            str(item) for item in parsed.get("portfolio_level_notes", []) if item
        ],
        assessments=assessments,
        warnings=[*report_input.warnings, *warnings],
        raw_response=raw_response,
    )


def _assessment_from_model_payload(
    holding: HoldingHealthInput, payload: dict[str, Any] | None
) -> HoldingHealthAssessment:
    if payload is None:
        fallback = _deterministic_assessment(holding)
        return fallback.model_copy(
            update={
                "evidence_gaps": [
                    *fallback.evidence_gaps,
                    "The OpenAI report did not return a row for this holding.",
                ],
                "confidence_score": min(fallback.confidence_score, 40),
            }
        )
    return HoldingHealthAssessment(
        symbol=holding.symbol,
        broker_ticker=holding.broker_ticker,
        research_symbol=holding.research_symbol,
        company_name=holding.company_name,
        current_price=holding.current_price,
        current_value=holding.current_value,
        current_weight_pct=holding.current_weight_pct,
        recommended_action=_action(payload.get("recommended_action")),
        action_rationale=str(payload.get("action_rationale") or "No rationale supplied."),
        price_targets=HealthPriceTargets(
            bear=_positive_float_or_none(payload.get("bear_case_price_target")),
            base=_positive_float_or_none(payload.get("base_case_price_target")),
            bull=_positive_float_or_none(payload.get("bull_case_price_target")),
        ),
        bear_case=str(payload.get("bear_case") or "No bear case supplied."),
        base_case=str(payload.get("base_case") or "No base case supplied."),
        bull_case=str(payload.get("bull_case") or "No bull case supplied."),
        key_risks=[str(item) for item in payload.get("key_risks", []) if item],
        evidence_gaps=[str(item) for item in payload.get("evidence_gaps", []) if item],
        confidence_score=_bounded_score(payload.get("confidence_score")),
    )


def _deterministic_report(
    report_input: HoldingHealthReportInput,
    *,
    model: str,
    status: HoldingHealthReportStatus,
    evidence_hash: str,
    generated_at_utc: datetime,
    extra_warning: str,
    raw_response: dict[str, Any] | None = None,
) -> HoldingHealthReport:
    warnings = [*report_input.warnings, extra_warning]
    assessments = [_deterministic_assessment(holding) for holding in report_input.holdings]
    return HoldingHealthReport(
        id=_report_id(evidence_hash, generated_at_utc),
        status=status,
        model=model,
        generated_at_utc=generated_at_utc,
        holdings_snapshot_at_utc=report_input.retrieved_at_utc,
        holding_count=len(report_input.holdings),
        evidence_hash=evidence_hash,
        summary=(
            "Holdings health check generated with conservative local rules. "
            "Use OpenAI deep research for current external evidence before changing targets."
        ),
        portfolio_level_notes=[
            "No live order authority is created by this report.",
            "Treat local-rule targets as placeholders for operator review.",
        ],
        assessments=assessments,
        warnings=warnings,
        raw_response=raw_response,
    )


def _deterministic_assessment(holding: HoldingHealthInput) -> HoldingHealthAssessment:
    current_price = holding.current_price
    gaps = list(holding.warnings)
    if current_price is None or current_price <= 0:
        gaps.append("Current price is missing, so price targets were not generated.")
        targets = HealthPriceTargets()
        confidence = 25
        rationale = "Keep under review until broker price and current evidence are available."
    else:
        targets = HealthPriceTargets(
            bear=round(current_price * 0.8, 2),
            base=round(current_price * 1.08, 2),
            bull=round(current_price * 1.25, 2),
        )
        confidence = 45 if gaps else 55
        rationale = (
            "Local fallback keeps the holding on review with broad scenario targets "
            "derived from current price only."
        )

    momentum_3m = _float_or_none(holding.technicals.get("momentum_3m"))
    action = HoldingHealthAction.HOLD
    if current_price is None:
        action = HoldingHealthAction.REVIEW
    elif momentum_3m is not None and momentum_3m < -0.2:
        action = HoldingHealthAction.REVIEW
        rationale = "Three-month momentum is weak; review thesis before adding exposure."

    return HoldingHealthAssessment(
        symbol=holding.symbol,
        broker_ticker=holding.broker_ticker,
        research_symbol=holding.research_symbol,
        company_name=holding.company_name,
        current_price=current_price,
        current_value=holding.current_value,
        current_weight_pct=holding.current_weight_pct,
        recommended_action=action,
        action_rationale=rationale,
        price_targets=targets,
        bear_case="Fallback bear case uses a broad downside haircut from current price.",
        base_case="Fallback base case assumes modest progress and needs analyst confirmation.",
        bull_case="Fallback bull case assumes positive execution and market support.",
        key_risks=[
            "Provider data may be incomplete or stale.",
            "Fallback output does not include fresh external research.",
        ],
        evidence_gaps=gaps,
        confidence_score=confidence,
    )


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


def _report_from_record(record: HoldingHealthReportRecord) -> HoldingHealthReport:
    payload = json.loads(record.payload_json)
    report = HoldingHealthReport.model_validate(payload)
    return report.model_copy(
        update={
            "generated_at_utc": _stored_utc(record.generated_at_utc),
            "holdings_snapshot_at_utc": _stored_utc(record.holdings_snapshot_at_utc),
        }
    )


def _update_from_record(record: HoldingHealthUpdateRecord) -> HoldingHealthUpdate:
    payload = json.loads(record.payload_json)
    update = HoldingHealthUpdate.model_validate(payload)
    return update.model_copy(update={"updated_at_utc": _stored_utc(record.updated_at_utc)})


def _assessment_for_symbol(
    report: HoldingHealthReport, symbol: str
) -> HoldingHealthAssessment | None:
    key = symbol.upper()
    return next(
        (
            assessment
            for assessment in report.assessments
            if key
            in {
                assessment.symbol.upper(),
                (assessment.broker_ticker or "").upper(),
                (assessment.research_symbol or "").upper(),
            }
        ),
        None,
    )


def _report_id(evidence_hash: str, generated_at_utc: datetime) -> str:
    timestamp = generated_at_utc.strftime("%Y%m%d%H%M%S")
    return f"holding-health-{timestamp}-{evidence_hash[:8]}"


def _update_id(
    report_id: str, symbol: str, payload: dict[str, Any], updated_at_utc: datetime
) -> str:
    timestamp = updated_at_utc.strftime("%Y%m%d%H%M%S")
    digest = sha256_digest({"report_id": report_id, "symbol": symbol, "payload": payload})[:8]
    clean_symbol = symbol.upper().replace(".", "-")
    return f"health-update-{clean_symbol}-{timestamp}-{digest}"


def _stored_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return require_utc(value)


def _action(value: Any) -> HoldingHealthAction:
    try:
        return HoldingHealthAction(str(value))
    except ValueError:
        return HoldingHealthAction.REVIEW


def _bounded_score(value: Any) -> int:
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return 0


def _positive_float_or_none(value: Any) -> float | None:
    parsed = _float_or_none(value)
    if parsed is None or parsed <= 0:
        return None
    return parsed


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
