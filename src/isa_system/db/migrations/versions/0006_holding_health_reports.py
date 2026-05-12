"""Add holding health report history."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_holding_health_reports"
down_revision = "0005_research_reports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create holding health report and operator update tables."""

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "holding_health_reports" not in tables:
        op.create_table(
            "holding_health_reports",
            sa.Column("id", sa.String(length=80), primary_key=True),
            sa.Column("status", sa.String(length=40), nullable=False),
            sa.Column("model", sa.String(length=120), nullable=False),
            sa.Column("generated_at_utc", sa.DateTime(timezone=True), nullable=False),
            sa.Column("holdings_snapshot_at_utc", sa.DateTime(timezone=True), nullable=False),
            sa.Column("holding_count", sa.Integer(), nullable=False),
            sa.Column("evidence_hash", sa.String(length=64), nullable=False),
            sa.Column("payload_json", sa.Text(), nullable=False),
            sa.Column("warnings_json", sa.Text(), nullable=False, server_default="[]"),
        )
        op.create_index(
            "ix_holding_health_reports_generated_at",
            "holding_health_reports",
            ["generated_at_utc"],
        )
        op.create_index(
            "ix_holding_health_reports_evidence_hash",
            "holding_health_reports",
            ["evidence_hash"],
        )

    if "holding_health_updates" in tables:
        return
    op.create_table(
        "holding_health_updates",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("report_id", sa.String(length=80), nullable=False),
        sa.Column("symbol", sa.String(length=80), nullable=False),
        sa.Column("updated_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("carried_forward_action", sa.String(length=40), nullable=False),
        sa.Column("adjusted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_holding_health_updates_report", "holding_health_updates", ["report_id"])
    op.create_index("ix_holding_health_updates_symbol", "holding_health_updates", ["symbol"])
    op.create_index(
        "ix_holding_health_updates_updated_at",
        "holding_health_updates",
        ["updated_at_utc"],
    )


def downgrade() -> None:
    """Drop holding health report tables."""

    op.drop_index("ix_holding_health_updates_updated_at", table_name="holding_health_updates")
    op.drop_index("ix_holding_health_updates_symbol", table_name="holding_health_updates")
    op.drop_index("ix_holding_health_updates_report", table_name="holding_health_updates")
    op.drop_table("holding_health_updates")
    op.drop_index("ix_holding_health_reports_evidence_hash", table_name="holding_health_reports")
    op.drop_index("ix_holding_health_reports_generated_at", table_name="holding_health_reports")
    op.drop_table("holding_health_reports")
