"""meal types as a multi-select set (M2 revision)

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-29 00:00:00.000000

Replaces the single-valued ``meal_detail.type`` (dinner/lunch/both) with a
``meal_type`` set table: one row per applicable slot, so a meal can be
breakfast *and* dinner in any combination. Existing rows are backfilled:
dinner -> {dinner}, lunch -> {lunch}, both -> {lunch, dinner}. The old
``type`` column and its check constraint are then dropped.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "meal_type",
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("meal_type", sa.String(), nullable=False),
        sa.CheckConstraint(
            "meal_type IN ('breakfast','lunch','dinner')", name="ck_meal_type_value"
        ),
        sa.ForeignKeyConstraint(["item_id"], ["item.id"]),
        sa.PrimaryKeyConstraint("item_id", "meal_type"),
    )

    # Backfill from the old scalar type. 'both' fans out to lunch + dinner.
    op.execute(
        "INSERT INTO meal_type (item_id, meal_type) "
        "SELECT item_id, 'dinner' FROM meal_detail WHERE type IN ('dinner','both')"
    )
    op.execute(
        "INSERT INTO meal_type (item_id, meal_type) "
        "SELECT item_id, 'lunch' FROM meal_detail WHERE type IN ('lunch','both')"
    )

    # Drop the old scalar column and its check constraint. The constraint must
    # go explicitly: batch mode rebuilds the table and would otherwise carry the
    # CHECK (which references the now-absent `type` column) into the new schema.
    with op.batch_alter_table("meal_detail") as batch:
        batch.drop_constraint("ck_meal_detail_type", type_="check")
        batch.drop_column("type")


def downgrade() -> None:
    with op.batch_alter_table("meal_detail") as batch:
        batch.add_column(
            sa.Column("type", sa.String(), nullable=False, server_default="dinner")
        )
    # Collapse the set back to the scalar: both slots -> 'both', else the one slot.
    op.execute(
        "UPDATE meal_detail SET type = 'both' WHERE item_id IN ("
        " SELECT item_id FROM meal_type WHERE meal_type = 'lunch'"
        " INTERSECT SELECT item_id FROM meal_type WHERE meal_type = 'dinner')"
    )
    op.execute(
        "UPDATE meal_detail SET type = 'lunch' WHERE item_id IN ("
        " SELECT item_id FROM meal_type WHERE meal_type = 'lunch'"
        " EXCEPT SELECT item_id FROM meal_type WHERE meal_type = 'dinner')"
    )
    op.execute(
        "UPDATE meal_detail SET type = 'dinner' WHERE item_id IN ("
        " SELECT item_id FROM meal_type WHERE meal_type = 'dinner'"
        " EXCEPT SELECT item_id FROM meal_type WHERE meal_type = 'lunch')"
    )
    op.drop_table("meal_type")
