"""Add structured research report records."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_research_reports"
down_revision = "0004_investment_theses"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create research report persistence table when absent."""

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "research_reports" in inspector.get_table_names():
        return
    op.create_table(
        "research_reports",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("symbol", sa.String(length=80), nullable=False),
        sa.Column("thesis_id", sa.String(length=80), nullable=False),
        sa.Column("decision", sa.String(length=40), nullable=False),
        sa.Column("markdown_path", sa.Text(), nullable=False),
        sa.Column("generated_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
    )
    op.create_index("ix_research_reports_symbol", "research_reports", ["symbol"])
    op.create_index("ix_research_reports_thesis_id", "research_reports", ["thesis_id"])


def downgrade() -> None:
    """Drop research report persistence table."""

    op.drop_index("ix_research_reports_thesis_id", table_name="research_reports")
    op.drop_index("ix_research_reports_symbol", table_name="research_reports")
    op.drop_table("research_reports")
