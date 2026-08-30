"""session_participant PK never reuses ids (HOTFIX4)

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-30 00:00:00.000000

SQLite reuses INTEGER PRIMARY KEY values after row deletion (the rowid
alias), and §5.5 deletes every ``session_participant`` row at session
finish. A later session's first joiners could therefore inherit finished
sessions' participant ids — and any browser still holding the finished
session's cookie would silently BECOME the person who got the recycled id
(reproduced on production). This rebuilds the table with ``AUTOINCREMENT``
(a real ``sqlite_sequence`` id space): deleted ids are never handed out
again, closing both the cross-session cookie collision and the
within-session recycle case (host removes someone, the next joiner reuses
their id, the removed person's phone becomes them).

SQLite only supports ``AUTOINCREMENT`` via a table-level declaration, and
only by rebuilding the table — Alembic batch mode copies the data across
and recreates the constraints. Data is preserved; nothing is dropped.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Batch mode rebuilds the table (data copied, FKs recreated); the
    # table-level sqlite_autoincrement flag is what makes the new DDL declare
    # "INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT" instead of the rowid-alias
    # form that recycles ids.
    with op.batch_alter_table(
        "session_participant",
        table_kwargs={"sqlite_autoincrement": True},
    ) as batch_op:
        batch_op.alter_column(
            "id", existing_type=sa.INTEGER(), autoincrement=True, existing_nullable=False
        )
