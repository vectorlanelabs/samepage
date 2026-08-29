"""google SSO (M5a): auth_identity table; drop account.password_hash

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-29 00:00:00.000000

Replaces email+password auth with Google OAuth (OIDC) per PLAN-v2-samepage.md
§4 (locked 2026-08-29): ``account`` keeps email + display_name as the
human-facing key, and ``auth_identity(account_id, provider, subject,
UNIQUE(provider, subject))`` records which external identity may sign into
each account. The password column is dropped — no password fallback exists
anymore, so there is nothing to keep. SQLite needs batch mode for column
drops.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "auth_identity",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("subject", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"], ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "subject"),
    )
    with op.batch_alter_table("account") as batch_op:
        batch_op.drop_column("password_hash")


def downgrade() -> None:
    with op.batch_alter_table("account") as batch_op:
        batch_op.add_column(
            sa.Column("password_hash", sa.String(), nullable=False, server_default="")
        )
    op.drop_table("auth_identity")
