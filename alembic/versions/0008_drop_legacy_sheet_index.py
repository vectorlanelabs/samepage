"""drop category.legacy_sheet_index (M2e seed purge)

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-29 00:00:00.000000

The seed pipeline is gone (M2e): no pre-seeded library, no spreadsheet
provenance in the repo. ``legacy_sheet_index`` only ever carried the source
spreadsheet's tab number for seeded categories, so the column has no
meaning for collections created in-app. SQLite needs batch mode for column
drops.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("category") as batch_op:
        batch_op.drop_column("legacy_sheet_index")


def downgrade() -> None:
    with op.batch_alter_table("category") as batch_op:
        batch_op.add_column(sa.Column("legacy_sheet_index", sa.Integer(), nullable=True))
