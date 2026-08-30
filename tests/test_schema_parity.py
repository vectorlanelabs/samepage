"""Guard: the SQLAlchemy models and the Alembic migrations must describe the
same schema.

The rest of the suite builds its database from the models via
``Base.metadata.create_all`` (fast, no migration chain), while the real app
runs the migrations. That gap once let a column drift through undetected: a
migration dropped ``meal_detail.ingredients`` while the model still declared
it, so every test passed but the live app 500'd on the first query. This test
closes that gap by comparing the column set of every table built each way.
"""


import sqlalchemy as sa
from alembic.config import Config

from alembic import command
from app.models import Base


def _columns_by_table(db_path) -> dict[str, set[str]]:
    engine = sa.create_engine(f"sqlite:///{db_path}")
    try:
        inspector = sa.inspect(engine)
        return {
            table: {col["name"] for col in inspector.get_columns(table)}
            for table in inspector.get_table_names()
            if table != "alembic_version"
        }
    finally:
        engine.dispose()


def test_models_match_migrations(tmp_path, monkeypatch):
    # Schema as the models describe it (what the test suite normally uses).
    model_db = tmp_path / "model.db"
    engine = sa.create_engine(f"sqlite:///{model_db}")
    Base.metadata.create_all(engine)
    engine.dispose()
    model_cols = _columns_by_table(model_db)

    # Schema as the migrations build it (what production runs).
    migration_db = tmp_path / "migration.db"
    monkeypatch.setenv("SP_DB_PATH", str(migration_db))
    command.upgrade(Config("alembic.ini"), "head")
    migration_cols = _columns_by_table(migration_db)

    assert model_cols.keys() == migration_cols.keys(), (
        "Tables differ between models and migrations: "
        f"models-only={model_cols.keys() - migration_cols.keys()}, "
        f"migrations-only={migration_cols.keys() - model_cols.keys()}"
    )
    mismatches = {
        table: {
            "models_only": sorted(model_cols[table] - migration_cols[table]),
            "migrations_only": sorted(migration_cols[table] - model_cols[table]),
        }
        for table in model_cols
        if model_cols[table] != migration_cols[table]
    }
    assert not mismatches, f"Column drift between models and migrations: {mismatches}"


def test_migration_head_participant_pk_autoincrement(tmp_path, monkeypatch):
    """HOTFIX4: the migration chain (what production runs) ends with the
    AUTOINCREMENT participant PK — the same DDL the models emit — so the
    id-reuse guard holds on the migrated schema too (a batch-rebuilt table
    could otherwise silently lose the flag)."""
    migration_db = tmp_path / "migration.db"
    monkeypatch.setenv("SP_DB_PATH", str(migration_db))
    command.upgrade(Config("alembic.ini"), "head")

    engine = sa.create_engine(f"sqlite:///{migration_db}")
    try:
        sql = engine.connect().execute(
            sa.text(
                "SELECT sql FROM sqlite_master "
                "WHERE type='table' AND name='session_participant'"
            )
        ).scalar()
        assert sql is not None and "AUTOINCREMENT" in sql
    finally:
        engine.dispose()


def test_migration_0014_resets_voting_history_and_zeroes_item_stats(tmp_path, monkeypatch):
    """RESET: the one-off data migration (0014) deletes every voting-history
    row (six session/batch tables, children-first) and zeroes every item's
    counters — while leaving items/collections/accounts/groups intact.
    Schema parity only compares columns, so this test exercises the data move
    directly: a pre-0014 DB seeded with a counter-carrying item and a full
    session hierarchy, then ``upgrade head``, then the assertions."""
    migration_db = tmp_path / "migration.db"
    monkeypatch.setenv("SP_DB_PATH", str(migration_db))
    command.upgrade(Config("alembic.ini"), "0013")

    engine = sa.create_engine(f"sqlite:///{migration_db}")
    try:
        with engine.begin() as conn:
            # Seeded library row (account -> group -> collection -> item) with
            # accumulated counter history from prod test sessions, plus a full
            # session hierarchy (one row per voting table).
            conn.execute(
                sa.text(
                    "INSERT INTO account (id, email, display_name, created_at) "
                    "VALUES (1, 'host@example.com', 'Host', '2026-08-01 12:00:00')"
                )
            )
            conn.execute(
                sa.text(
                    'INSERT INTO "group" (id, name, owner_account_id, created_at) '
                    "VALUES (1, 'Test Group', 1, '2026-08-01 12:00:00')"
                )
            )
            conn.execute(
                sa.text(
                    "INSERT INTO collection (id, group_id, kind, name, created_at) "
                    "VALUES (1, 1, 'meal', 'Meal Planner', '2026-08-01 12:00:00')"
                )
            )
            conn.execute(
                sa.text(
                    "INSERT INTO item (id, collection_id, name, normalized_name,"
                    " description, category_id, archived_at, times_offered,"
                    " times_kept, last_kept_at, created_at, updated_at) "
                    "VALUES (1, 1, 'Seeded Meal', 'seeded meal', NULL, NULL, NULL,"
                    " 5, 3, '2026-08-02 19:00:00', '2026-08-01 12:00:00',"
                    " '2026-08-02 19:00:00')"
                )
            )
            conn.execute(
                sa.text(
                    "INSERT INTO session (id, code, status, group_id,"
                    " host_account_id, collection_id, created_at,"
                    " last_activity_at, finished_at) "
                    "VALUES (1, 'Amber-1234', 'complete', 1, 1, 1,"
                    " '2026-08-01 19:00:00', '2026-08-01 20:00:00',"
                    " '2026-08-01 20:00:00')"
                )
            )
            conn.execute(
                sa.text(
                    "INSERT INTO session_target (id, session_id, track_label,"
                    " target_count) VALUES (1, 1, 'dinner', 1)"
                )
            )
            conn.execute(
                sa.text(
                    "INSERT INTO session_participant (id, session_id, account_id,"
                    " display_name, joined_at) "
                    "VALUES (1, 1, NULL, 'Sam', '2026-08-01 19:05:00')"
                )
            )
            conn.execute(
                sa.text(
                    "INSERT INTO batch (id, session_id, seq, track_label, status,"
                    " closed_at) "
                    "VALUES (1, 1, 1, 'dinner', 'closed', '2026-08-01 19:30:00')"
                )
            )
            conn.execute(
                sa.text(
                    "INSERT INTO batch_item (id, batch_id, item_id, ad_hoc_label,"
                    " sort_order, yes_count, no_count, outcome) "
                    "VALUES (1, 1, 1, NULL, 0, 1, 0, 'kept_unanimous')"
                )
            )
            conn.execute(
                sa.text(
                    "INSERT INTO batch_response (id, batch_item_id,"
                    " session_participant_id, choice, responded_at) "
                    "VALUES (1, 1, 1, 'yes', '2026-08-01 19:20:00')"
                )
            )
            # Sanity: the history exists before the reset runs.
            assert conn.execute(sa.text('SELECT COUNT(*) FROM "session"')).scalar() == 1
            assert conn.execute(
                sa.text("SELECT COUNT(*) FROM batch_response")
            ).scalar() == 1

        command.upgrade(Config("alembic.ini"), "head")

        with engine.begin() as conn:
            for table in (
                "batch_response",
                "batch_item",
                "batch",
                "session_target",
                "session_participant",
                "session",
            ):
                assert conn.execute(
                    sa.text(f'SELECT COUNT(*) FROM "{table}"')
                ).scalar() == 0, f"{table} not cleared by 0014"
            # The seeded item survives with its counter columns intact and zeroed.
            item_row = conn.execute(
                sa.text(
                    "SELECT id, name, times_offered, times_kept, last_kept_at"
                    " FROM item WHERE id = 1"
                )
            ).one()
            assert item_row.id == 1 and item_row.name == "Seeded Meal"
            assert item_row.times_offered == 0
            assert item_row.times_kept == 0
            assert item_row.last_kept_at is None
            # Library/account structure untouched.
            assert conn.execute(sa.text('SELECT COUNT(*) FROM "account"')).scalar() == 1
            assert conn.execute(sa.text('SELECT COUNT(*) FROM "group"')).scalar() == 1
            assert conn.execute(sa.text('SELECT COUNT(*) FROM "collection"')).scalar() == 1
            assert conn.execute(sa.text('SELECT COUNT(*) FROM "item"')).scalar() == 1
    finally:
        engine.dispose()
