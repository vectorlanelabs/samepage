"""Fresh-boot migration (fix A): the app migrates a fresh DB at startup.

A fresh install must boot to a working home page — the lifespan runs
``alembic upgrade head`` before serving, so a new DB gets the full schema
instead of 500ing on every page.
"""

import os
import sqlite3

from app.main import _run_migrations

EXPECTED_TABLES = {
    "person",
    "category",
    "tag",
    "meal",
    "meal_tag",
    "session",
    "session_participant",
    "batch",
    "batch_meal",
    "vote",
    "alembic_version",
}


def test_migrations_create_schema_from_scratch(tmp_path):
    db_path = str(tmp_path / "fresh.db")
    _run_migrations(db_path)
    # Migration-created DB must be private immediately: no group/other bits.
    assert os.stat(db_path).st_mode & 0o077 == 0
    conn = sqlite3.connect(db_path)
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    finally:
        conn.close()
    assert EXPECTED_TABLES <= tables


def test_fresh_boot_home_renders(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "What's for dinner?" in resp.text
