"""drop item.is_active (dead column)

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-29 00:00:00.000000

Drops the dead ``item.is_active`` column: ``archived_at`` is the real
mechanism, and the column was written but never read (OSCAR-REVIEW
2026-08-29). SQLite needs batch mode for column drops.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("item") as batch_op:
        batch_op.drop_column("is_active")


def downgrade() -> None:
    with op.batch_alter_table("item") as batch_op:
        batch_op.add_column(
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1"))
        )
