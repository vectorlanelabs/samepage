"""one-off DATA reset: clear voting history, zero meal stats (RESET)

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-30 00:00:00.000000

Production accumulated test sessions, and the favorites / reject-rate
counters (``item.times_offered`` / ``times_kept`` / ``last_kept_at``) are
wrong. This migration deletes every row from the six voting tables in
FK-safe order (children first) and zeroes every item's counters back to
their fresh-seed state. Items, collections, tags, accounts, and groups
are untouched — the library, accounts, and group structure survive.

Destructive one-off: the deleted rows are unrecoverable and
``downgrade()`` is deliberately a no-op — the original counter values
and history cannot be reconstructed.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Children before parents (FK-safe): responses -> items -> batches ->
    # participants -> targets -> sessions. One DELETE per table (SQLite has
    # no multi-table DELETE); all six run in the migration's transaction.
    op.execute("DELETE FROM batch_response;")
    op.execute("DELETE FROM batch_item;")
    op.execute("DELETE FROM batch;")
    op.execute("DELETE FROM session_participant;")
    op.execute("DELETE FROM session_target;")
    op.execute("DELETE FROM session;")

    # Zero every item's stats; last_kept_at back to NULL (fresh-seed state).
    op.execute("UPDATE item SET times_offered = 0, times_kept = 0, last_kept_at = NULL;")


def downgrade() -> None:
    # Irreversible data migration — the deleted voting history and the
    # original counter values cannot be reconstructed. No-op by design.
    pass
