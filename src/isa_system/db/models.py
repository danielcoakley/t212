"""Operational database models for auditability and execution control."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Index, Integer, Numeric, String, Text, UniqueConstraint
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


class InstrumentMaster(Base, TimestampMixin):
    """Tradable instrument master keyed by broker ticker and ISIN where available."""

    __tablename__ = "instrument_master"
    __table_args__ = (
        UniqueConstraint("t212_ticker", name="uq_instrument_master_t212_ticker"),
        Index("ix_instrument_master_isin", "isin"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    t212_ticker: Mapped[str] = mapped_column(String(80), nullable=False)
    isin: Mapped[str | None] = mapped_column(String(20))
    name: Mapped[str | None] = mapped_column(String(240))
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(40), nullable=False)
    isa_accessible: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    working_schedule_id: Mapped[int | None] = mapped_column(Integer)
    max_open_quantity: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))


class IssuerMaster(Base, TimestampMixin):
    """Issuer identity record for joining broker, filings, and provider data."""

    __tablename__ = "issuer_master"
    __table_args__ = (
        Index("ix_issuer_master_lei", "lei"),
        Index("ix_issuer_master_company_number", "company_number"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_name: Mapped[str] = mapped_column(String(240), nullable=False)
    lei: Mapped[str | None] = mapped_column(String(40))
    company_number: Mapped[str | None] = mapped_column(String(40))
    country: Mapped[str | None] = mapped_column(String(2))


class IdentityMap(Base, TimestampMixin):
    """Manual and automated symbol crosswalk with confidence scoring."""

    __tablename__ = "identity_map"
    __table_args__ = (
        UniqueConstraint("id_type", "id_value", "target_type", name="uq_identity_map"),
        Index("ix_identity_map_instrument", "instrument_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_id: Mapped[int | None] = mapped_column(Integer)
    issuer_id: Mapped[int | None] = mapped_column(Integer)
    id_type: Mapped[str] = mapped_column(String(40), nullable=False)
    id_value: Mapped[str] = mapped_column(String(160), nullable=False)
    target_type: Mapped[str] = mapped_column(String(40), nullable=False)
    target_value: Mapped[str] = mapped_column(String(160), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)


class PriceEOD(Base, TimestampMixin):
    """Normalised daily bar cache for research and backtests."""

    __tablename__ = "prices_eod"
    __table_args__ = (
        UniqueConstraint("instrument_id", "price_date", "source", name="uq_prices_eod"),
        Index("ix_prices_eod_symbol_date", "symbol", "price_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_id: Mapped[int | None] = mapped_column(Integer)
    symbol: Mapped[str] = mapped_column(String(80), nullable=False)
    price_date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    high: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    low: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    close: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    adj_close: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    volume: Mapped[Decimal | None] = mapped_column(Numeric(24, 4))
    source: Mapped[str] = mapped_column(String(80), nullable=False)


class FundamentalsSnapshot(Base, TimestampMixin):
    """Point-in-time fundamentals snapshot used by quality signals."""

    __tablename__ = "fundamentals_snapshot"
    __table_args__ = (Index("ix_fundamentals_issuer_publication", "issuer_id", "publication_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    issuer_id: Mapped[int | None] = mapped_column(Integer)
    symbol: Mapped[str | None] = mapped_column(String(80))
    publication_date: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date | None] = mapped_column(Date)
    metrics_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)


class FilingRaw(Base, TimestampMixin):
    """Raw filing or announcement record with audit evidence."""

    __tablename__ = "filings_raw"
    __table_args__ = (UniqueConstraint("source", "source_doc_id", name="uq_filings_raw_doc"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    issuer_id: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    source_doc_id: Mapped[str] = mapped_column(String(160), nullable=False)
    headline: Mapped[str | None] = mapped_column(String(500))
    headline_code: Mapped[str | None] = mapped_column(String(80))
    published_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    document_type: Mapped[str | None] = mapped_column(String(80))
    raw_text: Mapped[str | None] = mapped_column(Text)
    url_hash: Mapped[str | None] = mapped_column(String(64))


class CatalystEvent(Base, TimestampMixin):
    """Explainable catalyst event extracted from official sources."""

    __tablename__ = "catalyst_events"
    __table_args__ = (
        Index("ix_catalyst_events_issuer_published", "issuer_id", "published_at_utc"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    issuer_id: Mapped[int | None] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    published_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sentiment_score: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    novelty_score: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    thesis_tags_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)


class SignalDaily(Base, TimestampMixin):
    """Daily strategy signal output."""

    __tablename__ = "signals_daily"
    __table_args__ = (Index("ix_signals_daily_trade_date", "trade_date", "strategy"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    instrument_id: Mapped[int | None] = mapped_column(Integer)
    symbol: Mapped[str] = mapped_column(String(80), nullable=False)
    strategy: Mapped[str] = mapped_column(String(80), nullable=False)
    score: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    signal_state: Mapped[str] = mapped_column(String(40), nullable=False)
    thesis_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)


class ThesisRecord(Base, TimestampMixin):
    """Human-readable thesis snapshot required before live approval."""

    __tablename__ = "thesis_records"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    signal_id: Mapped[int | None] = mapped_column(Integer)
    symbol: Mapped[str] = mapped_column(String(80), nullable=False)
    thesis_type: Mapped[str] = mapped_column(String(80), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    invalidation_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)


class Alert(Base, TimestampMixin):
    """Operator alert shown in the dashboard."""

    __tablename__ = "alerts"
    __table_args__ = (Index("ix_alerts_status_severity", "status", "severity"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="open", nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    context_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)


class SettingsVersion(Base, TimestampMixin):
    """Append-only settings audit entry for dashboard changes."""

    __tablename__ = "settings_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    changed_by: Mapped[str] = mapped_column(String(120), nullable=False)
    diff_json: Mapped[str] = mapped_column(Text, nullable=False)
    version_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class BacktestRun(Base, TimestampMixin):
    """Backtest run summary."""

    __tablename__ = "backtest_runs"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    from_date: Mapped[date] = mapped_column(Date, nullable=False)
    to_date: Mapped[date] = mapped_column(Date, nullable=False)
    metrics_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)


class BacktestTrade(Base, TimestampMixin):
    """Backtest trade row for audit and dashboard display."""

    __tablename__ = "backtest_trades"
    __table_args__ = (Index("ix_backtest_trades_run_symbol", "run_id", "symbol"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(80), nullable=False)
    symbol: Mapped[str] = mapped_column(String(80), nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    exit_date: Mapped[date | None] = mapped_column(Date)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    exit_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    fees: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=Decimal("0"), nullable=False)
    exit_reason: Mapped[str | None] = mapped_column(String(80))


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


class InvestmentThesisRecord(Base):
    """Persisted portfolio-intelligence thesis snapshot."""

    __tablename__ = "investment_theses"
    __table_args__ = (Index("ix_investment_theses_symbol", "symbol"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    decision: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)


class ResearchReportRecord(Base):
    """Persisted structured investment memo."""

    __tablename__ = "research_reports"
    __table_args__ = (
        Index("ix_research_reports_symbol", "symbol"),
        Index("ix_research_reports_thesis_id", "thesis_id"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(80), nullable=False)
    thesis_id: Mapped[str] = mapped_column(String(80), nullable=False)
    decision: Mapped[str] = mapped_column(String(40), nullable=False)
    markdown_path: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)


class HoldingHealthReportRecord(Base):
    """Append-only health report run for current broker holdings."""

    __tablename__ = "holding_health_reports"
    __table_args__ = (
        Index("ix_holding_health_reports_generated_at", "generated_at_utc"),
        Index("ix_holding_health_reports_evidence_hash", "evidence_hash"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    generated_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    holdings_snapshot_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    holding_count: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    warnings_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)


class HoldingHealthUpdateRecord(Base):
    """Operator-accepted or adjusted health report output for one holding."""

    __tablename__ = "holding_health_updates"
    __table_args__ = (
        Index("ix_holding_health_updates_report", "report_id"),
        Index("ix_holding_health_updates_symbol", "symbol"),
        Index("ix_holding_health_updates_updated_at", "updated_at_utc"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    report_id: Mapped[str] = mapped_column(String(80), nullable=False)
    symbol: Mapped[str] = mapped_column(String(80), nullable=False)
    updated_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    carried_forward_action: Mapped[str] = mapped_column(String(40), nullable=False)
    adjusted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


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
