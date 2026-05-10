"""Initial operational schema."""

from __future__ import annotations

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all starter operational tables."""

    import isa_system.db.models  # noqa: F401
    from isa_system.db.base import Base

    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    """Drop all starter operational tables."""

    import isa_system.db.models  # noqa: F401
    from isa_system.db.base import Base

    Base.metadata.drop_all(bind=op.get_bind())
