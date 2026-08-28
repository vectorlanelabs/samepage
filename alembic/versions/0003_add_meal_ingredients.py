"""meal ingredients column

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-26 00:00:00.000000

Adds ``meal.ingredients`` (M2, T2.1): a NEWLINE-separated ingredient list,
one item per line (the edit form textarea round-trips it; the recipe view
splits on newlines). NULL = no ingredients saved yet.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("meal", sa.Column("ingredients", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("meal", "ingredients")
