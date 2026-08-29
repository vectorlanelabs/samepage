"""collections and items (M2b)

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-28 00:00:00.000000

Replaces Meal-based schema with generic Collection/Item/MealDetail schema.
Scopes Category to collection (UNIQUE(collection_id, name)) and Tag to group
(UNIQUE(group_id, name)). Adds Item with times_offered, times_kept, and
MealDetail as a 1:1 extension for meal-specific fields (type, ingredients,
recipe_text, source_url).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop dependents first (FK-safe order).
    op.drop_table("meal_tag")
    op.drop_index(op.f("ix_meal_normalized_name"), table_name="meal")
    op.drop_table("meal")
    op.drop_table("category")
    op.drop_table("tag")

    # Create collection first (referenced by category, item).
    op.create_table(
        "collection",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["group.id"], ),
        sa.PrimaryKeyConstraint("id"),
    )

    # New category scoped to collection.
    op.create_table(
        "category",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("collection_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=True),
        sa.Column("legacy_sheet_index", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["collection_id"], ["collection.id"], ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("collection_id", "name"),
    )

    # New tag scoped to group.
    op.create_table(
        "tag",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["group.id"], ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_id", "name"),
    )

    # Item table (replaces meal).
    op.create_table(
        "item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("collection_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("normalized_name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.Column("times_offered", sa.Integer(), nullable=False),
        sa.Column("times_kept", sa.Integer(), nullable=False),
        sa.Column("last_kept_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["category.id"], ),
        sa.ForeignKeyConstraint(["collection_id"], ["collection.id"], ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_item_normalized_name"), "item", ["normalized_name"], unique=False)

    # ItemTag (replaces meal_tag).
    op.create_table(
        "item_tag",
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["item_id"], ["item.id"], ),
        sa.ForeignKeyConstraint(["tag_id"], ["tag.id"], ),
        sa.PrimaryKeyConstraint("item_id", "tag_id"),
    )

    # MealDetail (1:1 extension for meal-specific fields).
    op.create_table(
        "meal_detail",
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("ingredients", sa.Text(), nullable=True),
        sa.Column("recipe_text", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["item_id"], ["item.id"], ),
        sa.PrimaryKeyConstraint("item_id"),
        sa.CheckConstraint("type IN ('dinner','lunch','both')", name="ck_meal_detail_type"),
    )


def downgrade() -> None:
    # Drop new tables in reverse dependency order.
    op.drop_table("meal_detail")
    op.drop_table("item_tag")
    op.drop_index(op.f("ix_item_normalized_name"), table_name="item")
    op.drop_table("item")
    op.drop_table("tag")
    op.drop_table("category")
    op.drop_table("collection")

    # Recreate old schema (from 0001-0003).
    op.create_table(
        "tag",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "category",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=True),
        sa.Column("legacy_sheet_index", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "meal",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("normalized_name", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("recipe_text", sa.Text(), nullable=True),
        sa.Column("ingredients", sa.Text(), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.Column("times_kept", sa.Integer(), nullable=False),
        sa.Column("last_kept_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["category.id"], ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("type IN ('dinner','lunch','both')", name="ck_meal_type"),
    )
    op.create_index(op.f("ix_meal_normalized_name"), "meal", ["normalized_name"], unique=False)
    op.create_table(
        "meal_tag",
        sa.Column("meal_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["meal_id"], ["meal.id"], ),
        sa.ForeignKeyConstraint(["tag_id"], ["tag.id"], ),
        sa.PrimaryKeyConstraint("meal_id", "tag_id"),
    )
