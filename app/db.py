"""Database engine, session factory, and the Base for SQLAlchemy models.

The real schema is Alembic-managed (D15): ``create_all`` exists for tests and
local development only. SQLite runs in WAL mode with foreign keys enforced.
"""

from __future__ import annotations

import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.settings import settings

engine = create_engine(settings.db_url, connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
    # The DB file holds private household data — tighten it on every connect
    # (idempotent; tolerate a file that vanished between connect and chmod).
    try:
        os.chmod(settings.db_path, 0o600)
    except FileNotFoundError:
        pass


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Declarative base for all Dinner Decider models (plan §6)."""


def get_db():
    """FastAPI dependency: yield a session, always close it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all() -> None:
    """Create every table. Dev/tests only — production schema comes from Alembic."""
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
