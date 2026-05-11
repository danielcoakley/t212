"""Add persisted deep research review gate results."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_research_reviews"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the research review persistence table when absent."""

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "research_reviews" in inspector.get_table_names():
        return
    op.create_table(
        "research_reviews",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("symbol", sa.String(length=80), nullable=False),
        sa.Column("research_symbol", sa.String(length=80), nullable=False),
        sa.Column("broker_ticker", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("decision", sa.String(length=40), nullable=True),
        sa.Column("final_score", sa.Integer(), nullable=True),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("evidence_hash", sa.String(length=64), nullable=False),
        sa.Column("generated_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_json", sa.Text(), nullable=False),
        sa.Column("response_json", sa.Text(), nullable=False),
        sa.Column("warnings_json", sa.Text(), nullable=False, server_default="[]"),
    )
    op.create_index("ix_research_reviews_symbol", "research_reviews", ["symbol"])
    op.create_index("ix_research_reviews_research_symbol", "research_reviews", ["research_symbol"])


def downgrade() -> None:
    """Drop the research review persistence table."""

    op.drop_index("ix_research_reviews_research_symbol", table_name="research_reviews")
    op.drop_index("ix_research_reviews_symbol", table_name="research_reviews")
    op.drop_table("research_reviews")
