"""voting engine schema (M3a)

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-29 00:00:00.000000

Adds the six session/batch tables from PLAN-v2-samepage.md §5: ``session``,
``session_target``, ``session_participant``, ``batch``, ``batch_item``, and
``batch_response``.

SQLite forbids expressions in a PRIMARY KEY, so the plan's COALESCE
pseudo-PK for batch_item is built instead as two PARTIAL unique indexes
(one for item-backed rows, one for ad hoc rows) — raw SQL, since Alembic's
``op.create_index`` has no portable partial-predicate support.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "session",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("host_account_id", sa.Integer(), nullable=False),
        sa.Column("collection_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["group_id"], ["group.id"], ),
        sa.ForeignKeyConstraint(["host_account_id"], ["account.id"], ),
        sa.ForeignKeyConstraint(["collection_id"], ["collection.id"], ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    op.create_table(
        "session_target",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("track_label", sa.String(), nullable=False),
        sa.Column("target_count", sa.Integer(), nullable=False),
        sa.CheckConstraint("target_count > 0", name="ck_session_target_positive"),
        sa.ForeignKeyConstraint(["session_id"], ["session.id"], ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "track_label", name="uq_session_target"),
    )

    op.create_table(
        "session_participant",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("joined_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"], ),
        sa.ForeignKeyConstraint(["session_id"], ["session.id"], ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "batch",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("track_label", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["session.id"], ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "seq", name="uq_batch_seq"),
    )

    op.create_table(
        "batch_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=True),
        sa.Column("ad_hoc_label", sa.String(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("yes_count", sa.Integer(), nullable=False),
        sa.Column("no_count", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(), nullable=True),
        sa.CheckConstraint("(item_id IS NULL) != (ad_hoc_label IS NULL)", name="ck_batch_item_one_of"),
        sa.ForeignKeyConstraint(["batch_id"], ["batch.id"], ),
        sa.ForeignKeyConstraint(["item_id"], ["item.id"], ),
        sa.PrimaryKeyConstraint("id"),
    )
    # Partial unique indexes (SQLite): one item-backed row per batch, one
    # ad hoc row per batch. Raw SQL — op.create_index can't express a WHERE.
    op.execute(
        "CREATE UNIQUE INDEX uq_batch_item_item"
        " ON batch_item (batch_id, item_id) WHERE item_id IS NOT NULL;"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_batch_item_adhoc"
        " ON batch_item (batch_id, ad_hoc_label) WHERE ad_hoc_label IS NOT NULL;"
    )

    op.create_table(
        "batch_response",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("batch_item_id", sa.Integer(), nullable=False),
        sa.Column("session_participant_id", sa.Integer(), nullable=False),
        sa.Column("choice", sa.String(), nullable=False),
        sa.Column("responded_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["batch_item_id"], ["batch_item.id"], ),
        sa.ForeignKeyConstraint(["session_participant_id"], ["session_participant.id"], ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_item_id", "session_participant_id", name="uq_batch_response"),
    )


def downgrade() -> None:
    # Drop indexes first, then tables in reverse FK dependency order.
    op.execute("DROP INDEX uq_batch_item_item;")
    op.execute("DROP INDEX uq_batch_item_adhoc;")
    op.drop_table("batch_response")
    op.drop_table("batch_item")
    op.drop_table("batch")
    op.drop_table("session_participant")
    op.drop_table("session_target")
    op.drop_table("session")
