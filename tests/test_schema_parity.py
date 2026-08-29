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
