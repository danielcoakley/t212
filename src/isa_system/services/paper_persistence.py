"""Persistence for preview-derived paper workflow evidence."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from isa_system.db.crud import append_audit_log
from isa_system.db.models import (
    PaperCycle as PaperCycleRecord,
)
from isa_system.db.models import (
    PaperIntent as PaperIntentRecord,
)
from isa_system.db.models import (
    PaperSimulatedFill as PaperSimulatedFillRecord,
)
from isa_system.db.session import init_db, make_engine, make_session_factory
from isa_system.services.paper_simulation import PaperFillPreview
from isa_system.services.pilot_workflow import PilotPaperWorkflowRow, PilotPaperWorkflowSummary
from isa_system.settings import Settings, get_settings
from isa_system.utils.hashing import sha256_digest
from isa_system.utils.time import require_utc


class PersistedPaperIntent(BaseModel):
    """Reloadable paper intent row captured from a selected preview row."""

    id: str
    paper_cycle_id: str
    row_index: int
    symbol: str
    research_symbol: str
    broker_ticker: str | None = None
    side: Literal["BUY", "SELL", "HOLD"]
    preview_eligible: bool
    target_weight: Decimal
    expected_notional_gbp: Decimal
    expected_fees_gbp: Decimal
    simulated_status: str
    expected_vs_simulated_status: str
    research_review_status: str | None = None
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_action: str
    preview_row_hash: str


class PersistedPaperSimulatedFill(BaseModel):
    """Reloadable simulated fill linked to a persisted paper intent."""

    id: str
    paper_cycle_id: str
    paper_intent_id: str | None = None
    simulated_fill_index: int
    symbol: str
    side: Literal["BUY", "SELL"]
    source_kind: str
    status: str
    quantity: Decimal | None = None
    fill_price_account: Decimal | None = None
    notional_gbp: Decimal
    estimated_fees_gbp: Decimal
    notional_source_kind: str
    quantity_source_kind: str
    fill_price_source_kind: str
    note: str


class PersistedPaperCycle(BaseModel):
    """Reloadable paper workflow cycle with intents and simulated fills."""

    id: str
    mode: Literal["preview"] = "preview"
    persistence_status: Literal["persisted"] = "persisted"
    reconciliation_status: Literal["not_available"] = "not_available"
    generated_at_utc: datetime
    persisted_at_utc: datetime
    source_kind: str
    workflow_status: str
    expected_vs_simulated_status: str
    selected_count: int
    preview_eligible_count: int
    simulated_fill_count: int
    preview_source_hash: str
    simulation_hash: str
    total_expected_notional_gbp: Decimal
    total_simulated_notional_gbp: Decimal
    total_simulated_fees_gbp: Decimal
    intents: list[PersistedPaperIntent]
    simulated_fills: list[PersistedPaperSimulatedFill]
    warnings: list[str] = Field(default_factory=list)

    @field_validator("generated_at_utc", "persisted_at_utc")
    @classmethod
    def _timestamps_are_utc(cls, value: datetime) -> datetime:
        return _stored_utc(value)


def persist_pilot_paper_workflow(
    workflow: PilotPaperWorkflowSummary,
    *,
    settings: Settings | None = None,
    session: Session | None = None,
) -> PersistedPaperCycle:
    """Persist a pilot paper workflow as deterministic cycle, intent, and fill rows."""

    if session is not None:
        return _persist_with_session(session, workflow)

    app_settings = settings or get_settings()
    engine = make_engine(app_settings.operational_db_dsn)
    init_db(engine)
    factory = make_session_factory(engine)
    with factory() as db_session:
        persisted = _persist_with_session(db_session, workflow)
        db_session.commit()
        return persisted


def load_paper_cycle(
    cycle_id: str,
    *,
    settings: Settings | None = None,
    session: Session | None = None,
) -> PersistedPaperCycle | None:
    """Load one persisted paper cycle by replayable ID."""

    if session is not None:
        return _load_with_session(session, cycle_id)

    app_settings = settings or get_settings()
    engine = make_engine(app_settings.operational_db_dsn)
    init_db(engine)
    factory = make_session_factory(engine)
    with factory() as db_session:
        return _load_with_session(db_session, cycle_id)


def _persist_with_session(
    session: Session,
    workflow: PilotPaperWorkflowSummary,
) -> PersistedPaperCycle:
    cycle_id = _cycle_id(workflow)
    fill_queue = _fill_queue(workflow.paper_simulation.fills)
    intent_records: list[PaperIntentRecord] = []
    fill_records: list[PaperSimulatedFillRecord] = []
    fill_index = 0
    for row_index, row in enumerate(workflow.rows):
        preview_row = workflow.preview.rows[row_index]
        intent_id = _intent_id(cycle_id, row_index, row)
        intent_records.append(
            PaperIntentRecord(
                id=intent_id,
                paper_cycle_id=cycle_id,
                row_index=row_index,
                symbol=row.symbol,
                research_symbol=row.research_symbol,
                broker_ticker=row.broker_ticker,
                side=row.side,
                preview_eligible=1 if row.preview_eligible else 0,
                target_weight=_decimal(preview_row.target_weight),
                expected_notional_gbp=_money(row.expected_notional_gbp),
                expected_fees_gbp=_money(row.expected_fees_gbp),
                simulated_status=row.simulated_status,
                expected_vs_simulated_status=row.expected_vs_simulated_status,
                research_review_status=preview_row.research_review_status,
                blockers_json=json.dumps(row.blockers, sort_keys=True),
                warnings_json=json.dumps(row.warnings, sort_keys=True),
                next_action=row.next_action,
                preview_row_hash=sha256_digest(preview_row.model_dump(mode="json")),
            )
        )
        fill = _pop_fill_for_row(fill_queue, row)
        if fill is not None:
            fill_records.append(
                _fill_record(
                    cycle_id=cycle_id,
                    intent_id=intent_id,
                    fill_index=fill_index,
                    fill=fill,
                    source_kind=workflow.paper_simulation.source_kind,
                )
            )
            fill_index += 1

    for fill in [item for fills in fill_queue.values() for item in fills]:
        fill_records.append(
            _fill_record(
                cycle_id=cycle_id,
                intent_id=None,
                fill_index=fill_index,
                fill=fill,
                source_kind=workflow.paper_simulation.source_kind,
            )
        )
        fill_index += 1

    cycle_record = PaperCycleRecord(
        id=cycle_id,
        mode=workflow.mode,
        source_kind=workflow.paper_simulation.source_kind,
        preview_source_hash=workflow.preview_source_hash,
        simulation_hash=workflow.simulation_hash,
        workflow_status=workflow.workflow_status,
        expected_vs_simulated_status=workflow.expected_vs_simulated_status,
        selected_count=workflow.selected_count,
        preview_eligible_count=workflow.preview_eligible_count,
        simulated_fill_count=len(fill_records),
        total_expected_notional_gbp=_money(
            sum((row.expected_notional_gbp for row in workflow.rows), Decimal("0"))
        ),
        total_simulated_notional_gbp=_money(workflow.paper_simulation.estimated_notional),
        total_simulated_fees_gbp=_money(workflow.paper_simulation.estimated_fees),
        generated_at_utc=workflow.generated_at_utc,
        warnings_json=json.dumps(workflow.warnings, sort_keys=True),
        workflow_json=workflow.model_dump_json(),
    )
    session.merge(cycle_record)
    for intent in intent_records:
        session.merge(intent)
    for fill in fill_records:
        session.merge(fill)
    append_audit_log(
        session,
        actor="system.paper_workflow",
        action="paper_cycle.persist",
        payload={
            "paper_cycle_id": cycle_id,
            "preview_source_hash": workflow.preview_source_hash,
            "simulation_hash": workflow.simulation_hash,
            "intent_count": len(intent_records),
            "simulated_fill_count": len(fill_records),
            "expected_vs_simulated_status": workflow.expected_vs_simulated_status,
        },
        outcome=workflow.workflow_status,
    )
    session.flush()
    persisted = _load_with_session(session, cycle_id)
    if persisted is None:  # pragma: no cover - defensive flush/load guard
        raise RuntimeError("Persisted paper cycle could not be reloaded.")
    return persisted


def _load_with_session(session: Session, cycle_id: str) -> PersistedPaperCycle | None:
    cycle = session.get(PaperCycleRecord, cycle_id)
    if cycle is None:
        return None
    intents = session.scalars(
        select(PaperIntentRecord)
        .where(PaperIntentRecord.paper_cycle_id == cycle_id)
        .order_by(PaperIntentRecord.row_index)
    ).all()
    fills = session.scalars(
        select(PaperSimulatedFillRecord)
        .where(PaperSimulatedFillRecord.paper_cycle_id == cycle_id)
        .order_by(PaperSimulatedFillRecord.simulated_fill_index)
    ).all()
    return PersistedPaperCycle(
        id=cycle.id,
        mode="preview",
        generated_at_utc=_stored_utc(cycle.generated_at_utc),
        persisted_at_utc=_stored_utc(cycle.created_at_utc),
        source_kind=cycle.source_kind,
        workflow_status=cycle.workflow_status,
        expected_vs_simulated_status=cycle.expected_vs_simulated_status,
        selected_count=cycle.selected_count,
        preview_eligible_count=cycle.preview_eligible_count,
        simulated_fill_count=cycle.simulated_fill_count,
        preview_source_hash=cycle.preview_source_hash,
        simulation_hash=cycle.simulation_hash,
        total_expected_notional_gbp=_money(cycle.total_expected_notional_gbp),
        total_simulated_notional_gbp=_money(cycle.total_simulated_notional_gbp),
        total_simulated_fees_gbp=_money(cycle.total_simulated_fees_gbp),
        intents=[_intent_from_record(intent) for intent in intents],
        simulated_fills=[_fill_from_record(fill) for fill in fills],
        warnings=[str(item) for item in json.loads(cycle.warnings_json)],
    )


def _intent_from_record(record: PaperIntentRecord) -> PersistedPaperIntent:
    return PersistedPaperIntent(
        id=record.id,
        paper_cycle_id=record.paper_cycle_id,
        row_index=record.row_index,
        symbol=record.symbol,
        research_symbol=record.research_symbol,
        broker_ticker=record.broker_ticker,
        side=record.side,
        preview_eligible=bool(record.preview_eligible),
        target_weight=_decimal(record.target_weight),
        expected_notional_gbp=_money(record.expected_notional_gbp),
        expected_fees_gbp=_money(record.expected_fees_gbp),
        simulated_status=record.simulated_status,
        expected_vs_simulated_status=record.expected_vs_simulated_status,
        research_review_status=record.research_review_status,
        blockers=[str(item) for item in json.loads(record.blockers_json)],
        warnings=[str(item) for item in json.loads(record.warnings_json)],
        next_action=record.next_action,
        preview_row_hash=record.preview_row_hash,
    )


def _fill_from_record(record: PaperSimulatedFillRecord) -> PersistedPaperSimulatedFill:
    return PersistedPaperSimulatedFill(
        id=record.id,
        paper_cycle_id=record.paper_cycle_id,
        paper_intent_id=record.paper_intent_id,
        simulated_fill_index=record.simulated_fill_index,
        symbol=record.symbol,
        side=record.side,
        source_kind=record.source_kind,
        status=record.status,
        quantity=_decimal_or_none(record.quantity),
        fill_price_account=_decimal_or_none(record.fill_price_account),
        notional_gbp=_money(record.notional_gbp),
        estimated_fees_gbp=_money(record.estimated_fees_gbp),
        notional_source_kind=record.notional_source_kind,
        quantity_source_kind=record.quantity_source_kind,
        fill_price_source_kind=record.fill_price_source_kind,
        note=record.note,
    )


def _fill_record(
    *,
    cycle_id: str,
    intent_id: str | None,
    fill_index: int,
    fill: PaperFillPreview,
    source_kind: str,
) -> PaperSimulatedFillRecord:
    quantity_source, price_source = _quantity_and_price_source_kinds(fill, source_kind)
    return PaperSimulatedFillRecord(
        id=_fill_id(cycle_id, intent_id, fill_index, fill),
        paper_cycle_id=cycle_id,
        paper_intent_id=intent_id,
        simulated_fill_index=fill_index,
        symbol=fill.symbol,
        side=fill.side,
        source_kind=source_kind,
        status=fill.status,
        quantity=fill.quantity,
        fill_price_account=fill.fill_price_account,
        notional_gbp=_money(fill.notional),
        estimated_fees_gbp=_money(fill.estimated_fees),
        notional_source_kind=f"{source_kind}.estimated_notional",
        quantity_source_kind=quantity_source,
        fill_price_source_kind=price_source,
        note=fill.note,
    )


def _cycle_id(workflow: PilotPaperWorkflowSummary) -> str:
    digest = sha256_digest(
        {
            "preview_source_hash": workflow.preview_source_hash,
            "simulation_hash": workflow.simulation_hash,
            "source_kind": workflow.paper_simulation.source_kind,
        }
    )
    return f"paper-cycle-{digest[:20]}"


def _intent_id(cycle_id: str, row_index: int, row: PilotPaperWorkflowRow) -> str:
    digest = sha256_digest(
        {
            "paper_cycle_id": cycle_id,
            "row_index": row_index,
            "research_symbol": row.research_symbol,
            "side": row.side,
            "expected_notional_gbp": str(_money(row.expected_notional_gbp)),
            "expected_fees_gbp": str(_money(row.expected_fees_gbp)),
        }
    )
    return f"paper-intent-{digest[:20]}"


def _fill_id(
    cycle_id: str,
    intent_id: str | None,
    fill_index: int,
    fill: PaperFillPreview,
) -> str:
    digest = sha256_digest(
        {
            "paper_cycle_id": cycle_id,
            "paper_intent_id": intent_id,
            "fill_index": fill_index,
            "symbol": fill.symbol,
            "side": fill.side,
            "quantity": str(fill.quantity),
            "fill_price_account": str(fill.fill_price_account),
            "notional": str(_money(fill.notional)),
            "estimated_fees": str(_money(fill.estimated_fees)),
        }
    )
    return f"paper-fill-{digest[:20]}"


def _fill_queue(
    fills: list[PaperFillPreview],
) -> dict[tuple[str, str], list[PaperFillPreview]]:
    queue: dict[tuple[str, str], list[PaperFillPreview]] = defaultdict(list)
    for fill in fills:
        queue[(fill.symbol.upper(), fill.side.upper())].append(fill)
    return queue


def _pop_fill_for_row(
    fill_queue: dict[tuple[str, str], list[PaperFillPreview]],
    row: PilotPaperWorkflowRow,
) -> PaperFillPreview | None:
    if row.simulated_status != "simulated":
        return None
    fills = fill_queue.get((row.research_symbol.upper(), row.side.upper()))
    if not fills:
        return None
    for index, fill in enumerate(fills):
        if _money(fill.notional) == _money(row.simulated_notional_gbp or Decimal("0")) and _money(
            fill.estimated_fees
        ) == _money(row.simulated_fees_gbp or Decimal("0")):
            return fills.pop(index)
    return fills.pop(0)


def _quantity_and_price_source_kinds(fill: PaperFillPreview, source_kind: str) -> tuple[str, str]:
    if fill.quantity is None:
        return (
            f"{source_kind}.notional_only_quantity_unavailable",
            f"{source_kind}.notional_only_fill_price_unavailable",
        )
    if fill.fill_price_account is None:
        return (f"{source_kind}.estimated_quantity", f"{source_kind}.fill_price_unavailable")
    return (f"{source_kind}.estimated_quantity", f"{source_kind}.notional_divided_by_quantity")


def _stored_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return require_utc(value)


def _decimal(value: Decimal | float | int | str) -> Decimal:
    return Decimal(str(value))


def _decimal_or_none(value: Decimal | None) -> Decimal | None:
    return None if value is None else _decimal(value)


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
