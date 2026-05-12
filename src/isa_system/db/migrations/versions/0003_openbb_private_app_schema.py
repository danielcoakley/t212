"""Add private app research, OpenBB, and dashboard tables."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_openbb_private_app_schema"
down_revision = "0002_research_reviews"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create app-owned tables that stay outside the OpenBB vendor checkout."""

    existing = set(sa.inspect(op.get_bind()).get_table_names())
    _create_instrument_master(existing)
    _create_issuer_master(existing)
    _create_identity_map(existing)
    _create_prices_eod(existing)
    _create_json_table(
        existing,
        "fundamentals_snapshot",
        [
            sa.Column("issuer_id", sa.Integer(), nullable=True),
            sa.Column("symbol", sa.String(length=80), nullable=True),
            sa.Column("publication_date", sa.Date(), nullable=False),
            sa.Column("period_end", sa.Date(), nullable=True),
            sa.Column("metrics_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("source", sa.String(length=80), nullable=False),
        ],
    )
    _create_json_table(
        existing,
        "filings_raw",
        [
            sa.Column("issuer_id", sa.Integer(), nullable=True),
            sa.Column("source", sa.String(length=80), nullable=False),
            sa.Column("source_doc_id", sa.String(length=160), nullable=False),
            sa.Column("headline", sa.String(length=500), nullable=True),
            sa.Column("headline_code", sa.String(length=80), nullable=True),
            sa.Column("published_at_utc", sa.DateTime(timezone=True), nullable=True),
            sa.Column("document_type", sa.String(length=80), nullable=True),
            sa.Column("raw_text", sa.Text(), nullable=True),
            sa.Column("url_hash", sa.String(length=64), nullable=True),
            sa.UniqueConstraint("source", "source_doc_id", name="uq_filings_raw_doc"),
        ],
    )
    _create_json_table(
        existing,
        "catalyst_events",
        [
            sa.Column("issuer_id", sa.Integer(), nullable=True),
            sa.Column("event_type", sa.String(length=80), nullable=False),
            sa.Column("published_at_utc", sa.DateTime(timezone=True), nullable=False),
            sa.Column("sentiment_score", sa.Numeric(8, 4), nullable=True),
            sa.Column("novelty_score", sa.Numeric(8, 4), nullable=True),
            sa.Column("thesis_tags_json", sa.Text(), nullable=False, server_default="[]"),
        ],
    )
    _create_json_table(
        existing,
        "signals_daily",
        [
            sa.Column("trade_date", sa.Date(), nullable=False),
            sa.Column("instrument_id", sa.Integer(), nullable=True),
            sa.Column("symbol", sa.String(length=80), nullable=False),
            sa.Column("strategy", sa.String(length=80), nullable=False),
            sa.Column("score", sa.Numeric(10, 6), nullable=False),
            sa.Column("signal_state", sa.String(length=40), nullable=False),
            sa.Column("thesis_json", sa.Text(), nullable=False, server_default="{}"),
        ],
    )
    _create_json_table(
        existing,
        "thesis_records",
        [
            sa.Column("id", sa.String(length=80), primary_key=True),
            sa.Column("signal_id", sa.Integer(), nullable=True),
            sa.Column("symbol", sa.String(length=80), nullable=False),
            sa.Column("thesis_type", sa.String(length=80), nullable=False),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("evidence_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("invalidation_json", sa.Text(), nullable=False, server_default="{}"),
        ],
        include_default_id=False,
    )
    _create_json_table(
        existing,
        "alerts",
        [
            sa.Column("severity", sa.String(length=20), nullable=False),
            sa.Column("status", sa.String(length=40), nullable=False, server_default="open"),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("context_json", sa.Text(), nullable=False, server_default="{}"),
        ],
    )
    _create_json_table(
        existing,
        "settings_versions",
        [
            sa.Column("changed_by", sa.String(length=120), nullable=False),
            sa.Column("diff_json", sa.Text(), nullable=False),
            sa.Column("version_hash", sa.String(length=64), nullable=False),
        ],
    )
    _create_backtests(existing)


def downgrade() -> None:
    """Drop app-owned schema additions."""

    for table in [
        "backtest_trades",
        "backtest_runs",
        "settings_versions",
        "alerts",
        "thesis_records",
        "signals_daily",
        "catalyst_events",
        "filings_raw",
        "fundamentals_snapshot",
        "prices_eod",
        "identity_map",
        "issuer_master",
        "instrument_master",
    ]:
        op.drop_table(table)


def _timestamp_columns() -> list[sa.Column]:
    return [sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False)]


def _create_json_table(
    existing: set[str],
    name: str,
    columns: list[sa.Column | sa.Constraint],
    *,
    include_default_id: bool = True,
) -> None:
    if name in existing:
        return
    base_columns: list[sa.Column | sa.Constraint] = []
    if include_default_id:
        base_columns.append(sa.Column("id", sa.Integer(), primary_key=True))
    base_columns.extend(columns)
    base_columns.extend(_timestamp_columns())
    op.create_table(name, *base_columns)


def _create_instrument_master(existing: set[str]) -> None:
    if "instrument_master" in existing:
        return
    op.create_table(
        "instrument_master",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("t212_ticker", sa.String(length=80), nullable=False),
        sa.Column("isin", sa.String(length=20), nullable=True),
        sa.Column("name", sa.String(length=240), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("asset_type", sa.String(length=40), nullable=False),
        sa.Column("isa_accessible", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("working_schedule_id", sa.Integer(), nullable=True),
        sa.Column("max_open_quantity", sa.Numeric(20, 8), nullable=True),
        *_timestamp_columns(),
        sa.UniqueConstraint("t212_ticker", name="uq_instrument_master_t212_ticker"),
    )
    op.create_index("ix_instrument_master_isin", "instrument_master", ["isin"])


def _create_issuer_master(existing: set[str]) -> None:
    if "issuer_master" in existing:
        return
    op.create_table(
        "issuer_master",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_name", sa.String(length=240), nullable=False),
        sa.Column("lei", sa.String(length=40), nullable=True),
        sa.Column("company_number", sa.String(length=40), nullable=True),
        sa.Column("country", sa.String(length=2), nullable=True),
        *_timestamp_columns(),
    )
    op.create_index("ix_issuer_master_lei", "issuer_master", ["lei"])
    op.create_index("ix_issuer_master_company_number", "issuer_master", ["company_number"])


def _create_identity_map(existing: set[str]) -> None:
    if "identity_map" in existing:
        return
    op.create_table(
        "identity_map",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("instrument_id", sa.Integer(), nullable=True),
        sa.Column("issuer_id", sa.Integer(), nullable=True),
        sa.Column("id_type", sa.String(length=40), nullable=False),
        sa.Column("id_value", sa.String(length=160), nullable=False),
        sa.Column("target_type", sa.String(length=40), nullable=False),
        sa.Column("target_value", sa.String(length=160), nullable=False),
        sa.Column("confidence", sa.Numeric(6, 4), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        *_timestamp_columns(),
        sa.UniqueConstraint("id_type", "id_value", "target_type", name="uq_identity_map"),
    )
    op.create_index("ix_identity_map_instrument", "identity_map", ["instrument_id"])


def _create_prices_eod(existing: set[str]) -> None:
    if "prices_eod" in existing:
        return
    op.create_table(
        "prices_eod",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("instrument_id", sa.Integer(), nullable=True),
        sa.Column("symbol", sa.String(length=80), nullable=False),
        sa.Column("price_date", sa.Date(), nullable=False),
        sa.Column("open", sa.Numeric(20, 8), nullable=True),
        sa.Column("high", sa.Numeric(20, 8), nullable=True),
        sa.Column("low", sa.Numeric(20, 8), nullable=True),
        sa.Column("close", sa.Numeric(20, 8), nullable=False),
        sa.Column("adj_close", sa.Numeric(20, 8), nullable=True),
        sa.Column("volume", sa.Numeric(24, 4), nullable=True),
        sa.Column("source", sa.String(length=80), nullable=False),
        *_timestamp_columns(),
        sa.UniqueConstraint("instrument_id", "price_date", "source", name="uq_prices_eod"),
    )
    op.create_index("ix_prices_eod_symbol_date", "prices_eod", ["symbol", "price_date"])


def _create_backtests(existing: set[str]) -> None:
    if "backtest_runs" not in existing:
        op.create_table(
            "backtest_runs",
            sa.Column("id", sa.String(length=80), primary_key=True),
            sa.Column("config_hash", sa.String(length=64), nullable=False),
            sa.Column("from_date", sa.Date(), nullable=False),
            sa.Column("to_date", sa.Date(), nullable=False),
            sa.Column("metrics_json", sa.Text(), nullable=False, server_default="{}"),
            *_timestamp_columns(),
        )
    if "backtest_trades" not in existing:
        op.create_table(
            "backtest_trades",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("run_id", sa.String(length=80), nullable=False),
            sa.Column("symbol", sa.String(length=80), nullable=False),
            sa.Column("entry_date", sa.Date(), nullable=False),
            sa.Column("exit_date", sa.Date(), nullable=True),
            sa.Column("quantity", sa.Numeric(20, 8), nullable=False),
            sa.Column("entry_price", sa.Numeric(20, 8), nullable=False),
            sa.Column("exit_price", sa.Numeric(20, 8), nullable=True),
            sa.Column("fees", sa.Numeric(20, 8), nullable=False, server_default="0"),
            sa.Column("exit_reason", sa.String(length=80), nullable=True),
            *_timestamp_columns(),
        )
        op.create_index("ix_backtest_trades_run_symbol", "backtest_trades", ["run_id", "symbol"])
