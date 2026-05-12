"""Add portfolio intelligence investment thesis records."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_investment_theses"
down_revision = "0003_paper_cycles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create investment thesis persistence table when absent."""

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "investment_theses" in inspector.get_table_names():
        return
    op.create_table(
        "investment_theses",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("symbol", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("decision", sa.String(length=40), nullable=False),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
    )
    op.create_index("ix_investment_theses_symbol", "investment_theses", ["symbol"])


def downgrade() -> None:
    """Drop investment thesis persistence table."""

    op.drop_index("ix_investment_theses_symbol", table_name="investment_theses")
    op.drop_table("investment_theses")
