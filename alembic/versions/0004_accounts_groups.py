"""accounts and groups (M2a)

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-28 00:00:00.000000

Replaces Person-based identity with Account (email+password) + Group/GroupAdmin
ownership model. Drops the unused M0 Session/SessionParticipant/Batch/BatchMeal/Vote
tables (empty, no routes built against them, superseded by M3 schema in PLAN-v2).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop dependents first (FK-safe order): vote/batch_meal/session_participant (depend on person),
    # then batch/session, then person.
    op.drop_table("vote")
    op.drop_table("batch_meal")
    op.drop_table("session_participant")
    op.drop_table("batch")
    op.drop_index(op.f("ix_session_code"), table_name="session")
    op.drop_table("session")
    op.drop_table("person")

    # Create account, group, group_admin.
    op.create_table(
        "account",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "group",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("owner_account_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["owner_account_id"], ["account.id"], ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "group_admin",
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("added_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"], ),
        sa.ForeignKeyConstraint(["group_id"], ["group.id"], ),
        sa.PrimaryKeyConstraint("account_id", "group_id"),
    )


def downgrade() -> None:
    # Drop new tables first.
    op.drop_table("group_admin")
    op.drop_table("group")
    op.drop_table("account")

    # Recreate person and session tables (M0/M1/M2 schema).
    op.create_table(
        "person",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("pin_hash", sa.String(), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("failed_pin_attempts", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "session",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_by_person_id", sa.Integer(), nullable=True),
        sa.Column("lunch_target", sa.Integer(), nullable=False),
        sa.Column("dinner_target", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by_person_id"], ["person.id"], ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("status IN ('lobby','voting','complete','expired')", name="ck_session_status"),
    )
    op.create_index(op.f("ix_session_code"), "session", ["code"], unique=True)
    op.create_table(
        "batch",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("track", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["session.id"], ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "seq"),
        sa.CheckConstraint("status IN ('open','closed')", name="ck_batch_status"),
        sa.CheckConstraint("track IN ('dinner','lunch')", name="ck_batch_track"),
    )
    op.create_table(
        "session_participant",
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("joined_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["person_id"], ["person.id"], ),
        sa.ForeignKeyConstraint(["session_id"], ["session.id"], ),
        sa.PrimaryKeyConstraint("person_id", "session_id"),
    )
    op.create_table(
        "batch_meal",
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("meal_id", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("kept", sa.Boolean(), nullable=False),
        sa.Column("kept_by", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["batch_id"], ["batch.id"], ),
        sa.ForeignKeyConstraint(["meal_id"], ["meal.id"], ),
        sa.PrimaryKeyConstraint("batch_id", "meal_id"),
        sa.CheckConstraint("kept_by IS NULL OR kept_by IN ('unanimous','host')", name="ck_batch_meal_kept_by"),
    )
    op.create_table(
        "vote",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("meal_id", sa.Integer(), nullable=False),
        sa.Column("choice", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["batch.id"], ),
        sa.ForeignKeyConstraint(["meal_id"], ["meal.id"], ),
        sa.ForeignKeyConstraint(["person_id"], ["person.id"], ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_id", "person_id", "meal_id"),
        sa.CheckConstraint("choice IN ('yes','no')", name="ck_vote_choice"),
    )
