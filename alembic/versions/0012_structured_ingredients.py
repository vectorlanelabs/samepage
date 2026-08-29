"""structured ingredients (M2 revision)

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-29 00:00:00.000000

Replaces the free-text ``meal_detail.ingredients`` blob with a structured,
group-scoped ingredient vocabulary (``ingredient``) plus a per-meal junction
(``meal_ingredient``), mirroring tags. This makes per-ingredient metrics a
clean group-by instead of a fragile substring match.

The old free-text lines are intentionally NOT carried into the structured
model: they are quantity-laden prose ("2 onions, diced"), not the clean
ingredient identities the new model needs, and production launches with a
blank database. The column is dropped after the new tables are in place.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ingredient",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["group.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_id", "name", name="uq_ingredient_group_name"),
    )
    op.create_table(
        "meal_ingredient",
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("ingredient_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["item_id"], ["item.id"]),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredient.id"]),
        sa.PrimaryKeyConstraint("item_id", "ingredient_id"),
    )
    with op.batch_alter_table("meal_detail") as batch:
        batch.drop_column("ingredients")


def downgrade() -> None:
    with op.batch_alter_table("meal_detail") as batch:
        batch.add_column(sa.Column("ingredients", sa.Text(), nullable=True))
    op.drop_table("meal_ingredient")
    op.drop_table("ingredient")
