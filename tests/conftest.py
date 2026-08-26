"""Shared fixtures: a per-test tmp SQLite engine and a TestClient whose DB
dependency is overridden to that engine (tests never touch the real DB).
"""

from __future__ import annotations

import os
import tempfile

# Point the app's boot-time migration and secret-key creation at a throwaway
# DB and a fixed test secret — never the real data/ dir or dev DB. Must run
# BEFORE app.main is imported: the lifespan migrates at TestClient startup.
os.environ["DD_DB_PATH"] = str(tempfile.mkdtemp(prefix="dd-test-") + "/conftest.db")
os.environ["DD_SECRET"] = "test-secret-for-tests"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.main import app


def make_engine(path):
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


@pytest.fixture()
def engine(tmp_path):
    """Fresh SQLite engine (WAL + foreign keys on) backed by a tmp file."""
    return make_engine(tmp_path / "test.db")


@pytest.fixture()
def db_session(engine):
    """A session bound to the tmp engine with the schema created."""
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    with TestingSessionLocal() as session:
        yield session


@pytest.fixture()
def client(engine):
    """TestClient with app.db.get_db overridden to the tmp engine."""
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def post(client):
    """POST helper: client.post with a same-origin Origin header by default.

    The origin-check middleware is fail-closed (absent Origin → 403), so
    every mutating test request goes through here. ``**kwargs`` (e.g.
    ``follow_redirects=False``) are forwarded to client.post.
    """

    def _post(url, data=None, headers=None, **kwargs):
        h = {"Origin": "http://testserver"}
        if headers:
            h.update(headers)
        return client.post(url, data=data, headers=h, **kwargs)

    return _post
