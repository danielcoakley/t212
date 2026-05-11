"""Add persisted paper workflow cycles, intents, and simulated fills."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_paper_cycles"
down_revision = "0002_research_reviews"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create paper workflow persistence tables when absent."""

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    if "paper_cycles" not in table_names:
        op.create_table(
            "paper_cycles",
            sa.Column("id", sa.String(length=80), primary_key=True),
            sa.Column("mode", sa.String(length=20), nullable=False, server_default="preview"),
            sa.Column("source_kind", sa.String(length=40), nullable=False),
            sa.Column("preview_source_hash", sa.String(length=64), nullable=False),
            sa.Column("simulation_hash", sa.String(length=64), nullable=False),
            sa.Column("workflow_status", sa.String(length=40), nullable=False),
            sa.Column("expected_vs_simulated_status", sa.String(length=40), nullable=False),
            sa.Column("selected_count", sa.Integer(), nullable=False),
            sa.Column("preview_eligible_count", sa.Integer(), nullable=False),
            sa.Column("simulated_fill_count", sa.Integer(), nullable=False),
            sa.Column("total_expected_notional_gbp", sa.Numeric(20, 4), nullable=False),
            sa.Column("total_simulated_notional_gbp", sa.Numeric(20, 4), nullable=False),
            sa.Column("total_simulated_fees_gbp", sa.Numeric(20, 4), nullable=False),
            sa.Column("generated_at_utc", sa.DateTime(timezone=True), nullable=False),
            sa.Column("warnings_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("workflow_json", sa.Text(), nullable=False),
            sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index(
            "ix_paper_cycles_preview_source_hash",
            "paper_cycles",
            ["preview_source_hash"],
        )
        op.create_index(
            "ix_paper_cycles_simulation_hash",
            "paper_cycles",
            ["simulation_hash"],
        )
    if "paper_intents" not in table_names:
        op.create_table(
            "paper_intents",
            sa.Column("id", sa.String(length=80), primary_key=True),
            sa.Column("paper_cycle_id", sa.String(length=80), nullable=False),
            sa.Column("row_index", sa.Integer(), nullable=False),
            sa.Column("symbol", sa.String(length=80), nullable=False),
            sa.Column("research_symbol", sa.String(length=80), nullable=False),
            sa.Column("broker_ticker", sa.String(length=80), nullable=True),
            sa.Column("side", sa.String(length=10), nullable=False),
            sa.Column("preview_eligible", sa.Integer(), nullable=False),
            sa.Column("target_weight", sa.Numeric(12, 8), nullable=False),
            sa.Column("expected_notional_gbp", sa.Numeric(20, 4), nullable=False),
            sa.Column("expected_fees_gbp", sa.Numeric(20, 4), nullable=False),
            sa.Column("simulated_status", sa.String(length=40), nullable=False),
            sa.Column("expected_vs_simulated_status", sa.String(length=40), nullable=False),
            sa.Column("research_review_status", sa.String(length=40), nullable=True),
            sa.Column("blockers_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("warnings_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("next_action", sa.Text(), nullable=False),
            sa.Column("preview_row_hash", sa.String(length=64), nullable=False),
            sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_paper_intents_cycle", "paper_intents", ["paper_cycle_id"])
        op.create_index(
            "ix_paper_intents_research_symbol",
            "paper_intents",
            ["research_symbol"],
        )
    if "paper_simulated_fills" not in table_names:
        op.create_table(
            "paper_simulated_fills",
            sa.Column("id", sa.String(length=80), primary_key=True),
            sa.Column("paper_cycle_id", sa.String(length=80), nullable=False),
            sa.Column("paper_intent_id", sa.String(length=80), nullable=True),
            sa.Column("simulated_fill_index", sa.Integer(), nullable=False),
            sa.Column("symbol", sa.String(length=80), nullable=False),
            sa.Column("side", sa.String(length=10), nullable=False),
            sa.Column("source_kind", sa.String(length=40), nullable=False),
            sa.Column("status", sa.String(length=40), nullable=False),
            sa.Column("quantity", sa.Numeric(20, 8), nullable=True),
            sa.Column("fill_price_account", sa.Numeric(20, 8), nullable=True),
            sa.Column("notional_gbp", sa.Numeric(20, 4), nullable=False),
            sa.Column("estimated_fees_gbp", sa.Numeric(20, 4), nullable=False),
            sa.Column("notional_source_kind", sa.String(length=80), nullable=False),
            sa.Column("quantity_source_kind", sa.String(length=80), nullable=False),
            sa.Column("fill_price_source_kind", sa.String(length=80), nullable=False),
            sa.Column("note", sa.Text(), nullable=False),
            sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index(
            "ix_paper_simulated_fills_cycle",
            "paper_simulated_fills",
            ["paper_cycle_id"],
        )
        op.create_index(
            "ix_paper_simulated_fills_intent",
            "paper_simulated_fills",
            ["paper_intent_id"],
        )


def downgrade() -> None:
    """Drop paper workflow persistence tables."""

    op.drop_index("ix_paper_simulated_fills_intent", table_name="paper_simulated_fills")
    op.drop_index("ix_paper_simulated_fills_cycle", table_name="paper_simulated_fills")
    op.drop_table("paper_simulated_fills")
    op.drop_index("ix_paper_intents_research_symbol", table_name="paper_intents")
    op.drop_index("ix_paper_intents_cycle", table_name="paper_intents")
    op.drop_table("paper_intents")
    op.drop_index("ix_paper_cycles_simulation_hash", table_name="paper_cycles")
    op.drop_index("ix_paper_cycles_preview_source_hash", table_name="paper_cycles")
    op.drop_table("paper_cycles")
