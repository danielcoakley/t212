"""Operational database models for auditability and execution control."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from isa_system.db.base import Base
from isa_system.utils.time import now_utc


class TimestampMixin:
    """Common UTC timestamp column."""

    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )


class StrategyConfig(Base, TimestampMixin):
    """Mutable strategy config with optimistic versioning."""

    __tablename__ = "strategy_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    config_text: Mapped[str] = mapped_column(Text, nullable=False)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )


class ConfigVersion(Base, TimestampMixin):
    """Append-only config version snapshot."""

    __tablename__ = "config_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    config_id: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    config_text: Mapped[str] = mapped_column(Text, nullable=False)


class RebalanceRun(Base, TimestampMixin):
    """Rebalance run record."""

    __tablename__ = "rebalance_runs"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    warnings_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)


class OrderBatch(Base, TimestampMixin):
    """Order batch produced by a rebalance preview."""

    __tablename__ = "order_batches"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    rebalance_run_id: Mapped[str] = mapped_column(String(80), nullable=False)
    batch_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)


class Order(Base, TimestampMixin):
    """Order intent or broker order."""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(80), nullable=False)
    symbol: Mapped[str] = mapped_column(String(40), nullable=False)
    broker_ticker: Mapped[str] = mapped_column(String(80), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    order_type: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    limit_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    broker_order_id: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(40), nullable=False)


class Fill(Base, TimestampMixin):
    """Broker or paper fill."""

    __tablename__ = "fills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int | None] = mapped_column(Integer)
    symbol: Mapped[str] = mapped_column(String(40), nullable=False)
    filled_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    fees: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=Decimal("0"), nullable=False)


class PositionSnapshot(Base, TimestampMixin):
    """Position snapshot from broker reconciliation."""

    __tablename__ = "position_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(40), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    market_value: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    as_of_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CashSnapshot(Base, TimestampMixin):
    """Cash snapshot from broker state."""

    __tablename__ = "cash_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    available_to_trade: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    as_of_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RiskEvent(Base, TimestampMixin):
    """Risk check or veto event."""

    __tablename__ = "risk_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    context_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)


class AuditLog(Base):
    """Append-only tamper-evident audit record."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    action: Mapped[str] = mapped_column(String(160), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_hash: Mapped[str | None] = mapped_column(String(64))
    outcome: Mapped[str] = mapped_column(String(80), nullable=False)


class IdempotencyKey(Base, TimestampMixin):
    """Local duplicate-order prevention key."""

    __tablename__ = "idempotency_keys"
    __table_args__ = (UniqueConstraint("key", name="uq_idempotency_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    order_batch_id: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(40), default="reserved", nullable=False)


class Heartbeat(Base, TimestampMixin):
    """Subsystem heartbeat."""

    __tablename__ = "heartbeats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subsystem: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    checked_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BrokerReconciliation(Base, TimestampMixin):
    """Broker reconciliation record."""

    __tablename__ = "broker_reconciliations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    details_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)


class AppState(Base, TimestampMixin):
    """Mutable app state value."""

    __tablename__ = "app_state"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class InstrumentRegistry(Base, TimestampMixin):
    """Broker instrument registry snapshot."""

    __tablename__ = "instrument_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(40), nullable=False)
    broker_ticker: Mapped[str] = mapped_column(String(80), nullable=False)
    isin: Mapped[str | None] = mapped_column(String(20))
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(40), nullable=False)
    is_isa_eligible: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class UniverseSnapshot(Base, TimestampMixin):
    """Versioned universe snapshot."""

    __tablename__ = "universe_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)


class ResearchReview(Base):
    """Persisted deep research gate result for one recommendation candidate."""

    __tablename__ = "research_reviews"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(80), nullable=False)
    research_symbol: Mapped[str] = mapped_column(String(80), nullable=False)
    broker_ticker: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    decision: Mapped[str | None] = mapped_column(String(40))
    final_score: Mapped[int | None] = mapped_column(Integer)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    generated_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    request_json: Mapped[str] = mapped_column(Text, nullable=False)
    response_json: Mapped[str] = mapped_column(Text, nullable=False)
    warnings_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)


class PaperCycle(Base, TimestampMixin):
    """Persisted paper workflow cycle derived from preview-only recommendation rows."""

    __tablename__ = "paper_cycles"
    __table_args__ = (
        Index("ix_paper_cycles_preview_source_hash", "preview_source_hash"),
        Index("ix_paper_cycles_simulation_hash", "simulation_hash"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    mode: Mapped[str] = mapped_column(String(20), default="preview", nullable=False)
    source_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    preview_source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    simulation_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    workflow_status: Mapped[str] = mapped_column(String(40), nullable=False)
    expected_vs_simulated_status: Mapped[str] = mapped_column(String(40), nullable=False)
    selected_count: Mapped[int] = mapped_column(Integer, nullable=False)
    preview_eligible_count: Mapped[int] = mapped_column(Integer, nullable=False)
    simulated_fill_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_expected_notional_gbp: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    total_simulated_notional_gbp: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    total_simulated_fees_gbp: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    generated_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    warnings_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    workflow_json: Mapped[str] = mapped_column(Text, nullable=False)


class PaperIntent(Base, TimestampMixin):
    """Persisted selected recommendation preview row intended for paper simulation."""

    __tablename__ = "paper_intents"
    __table_args__ = (
        Index("ix_paper_intents_cycle", "paper_cycle_id"),
        Index("ix_paper_intents_research_symbol", "research_symbol"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    paper_cycle_id: Mapped[str] = mapped_column(String(80), nullable=False)
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    symbol: Mapped[str] = mapped_column(String(80), nullable=False)
    research_symbol: Mapped[str] = mapped_column(String(80), nullable=False)
    broker_ticker: Mapped[str | None] = mapped_column(String(80))
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    preview_eligible: Mapped[int] = mapped_column(Integer, nullable=False)
    target_weight: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    expected_notional_gbp: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    expected_fees_gbp: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    simulated_status: Mapped[str] = mapped_column(String(40), nullable=False)
    expected_vs_simulated_status: Mapped[str] = mapped_column(String(40), nullable=False)
    research_review_status: Mapped[str | None] = mapped_column(String(40))
    blockers_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    warnings_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    next_action: Mapped[str] = mapped_column(Text, nullable=False)
    preview_row_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class PaperSimulatedFill(Base, TimestampMixin):
    """Persisted simulated fill linked back to a paper intent row."""

    __tablename__ = "paper_simulated_fills"
    __table_args__ = (
        Index("ix_paper_simulated_fills_cycle", "paper_cycle_id"),
        Index("ix_paper_simulated_fills_intent", "paper_intent_id"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    paper_cycle_id: Mapped[str] = mapped_column(String(80), nullable=False)
    paper_intent_id: Mapped[str | None] = mapped_column(String(80))
    simulated_fill_index: Mapped[int] = mapped_column(Integer, nullable=False)
    symbol: Mapped[str] = mapped_column(String(80), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    fill_price_account: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    notional_gbp: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    estimated_fees_gbp: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    notional_source_kind: Mapped[str] = mapped_column(String(80), nullable=False)
    quantity_source_kind: Mapped[str] = mapped_column(String(80), nullable=False)
    fill_price_source_kind: Mapped[str] = mapped_column(String(80), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
