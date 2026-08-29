"""per-group API tokens (M6a)

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-29 00:00:00.000000

Adds the ``api_token`` table (plan §8 M6): one row per group, storing only
the SHA-256 hash of the token — the plaintext is shown to the owner exactly
once at generation and never stored. The UNIQUE constraint on ``group_id``
enforces one live token per group; regenerating replaces the row (the route
deletes the old and inserts the new in one transaction). ``token_hash`` is
UNIQUE too, so the same token can never be minted for two groups.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "api_token",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["group_id"], ["group.id"], ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_id", name="uq_api_token_group"),
        sa.UniqueConstraint("token_hash", name="uq_api_token_hash"),
    )


def downgrade() -> None:
    op.drop_table("api_token")
