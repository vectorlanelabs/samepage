"""people security columns

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-26 00:00:00.000000

Adds the PIN-verify attempt-limiting state to ``person`` (T1.2):
``failed_pin_attempts`` (NOT NULL, default 0 — existing rows are backfilled)
and ``locked_until`` (NULL = not locked).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "person",
        sa.Column("failed_pin_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("person", sa.Column("locked_until", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("person", "locked_until")
    op.drop_column("person", "failed_pin_attempts")
