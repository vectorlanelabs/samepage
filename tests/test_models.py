"""Model round-trip + integrity constraints for every table in PLAN-v2-samepage.md §5."""

import sqlite3

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError

from app.db import Base
from app.models import Account, Group, GroupAdmin


def test_account_round_trip(db_session):
    account = Account(
        email="test@example.com",
        password_hash="pbkdf2-hash",
        display_name="Test User",
    )
    db_session.add(account)
    db_session.commit()

    # Prove persistence by expiring and re-reading from the database.
    db_session.expire_all()

    account_q = db_session.get(Account, account.id)
    assert account_q.email == "test@example.com"
    assert account_q.password_hash == "pbkdf2-hash"
    assert account_q.display_name == "Test User"


def test_group_and_admin_round_trip(db_session):
    owner = Account(email="owner@example.com", password_hash="hash1", display_name="Owner")
    admin = Account(email="admin@example.com", password_hash="hash2", display_name="Admin")
    db_session.add_all([owner, admin])
    db_session.flush()

    group = Group(name="Test Group", owner_account_id=owner.id)
    db_session.add(group)
    db_session.flush()

    group_admin = GroupAdmin(group_id=group.id, account_id=admin.id)
    db_session.add(group_admin)
    db_session.commit()

    # Prove persistence by expiring and re-reading from the database.
    db_session.expire_all()

    group_q = db_session.get(Group, group.id)
    assert group_q.name == "Test Group"
    assert group_q.owner_account_id == owner.id

    group_admin_q = db_session.get(GroupAdmin, (group.id, admin.id))
    assert group_admin_q is not None
    assert group_admin_q.group_id == group.id
    assert group_admin_q.account_id == admin.id


def test_duplicate_account_email_raises_integrity_error(db_session):
    """Duplicate email constraint."""
    account1 = Account(email="test@example.com", password_hash="hash1", display_name="User 1")
    db_session.add(account1)
    db_session.commit()

    with pytest.raises(IntegrityError):
        account2 = Account(email="test@example.com", password_hash="hash2", display_name="User 2")
        db_session.add(account2)
        db_session.commit()
    db_session.rollback()


def test_delete_referenced_account_raises_integrity_error(db_session):
    """No cascade deletes: an account referenced by a group cannot be deleted."""
    account = Account(email="owner@example.com", password_hash="hash", display_name="Owner")
    db_session.add(account)
    db_session.flush()
    db_session.add(Group(name="Test Group", owner_account_id=account.id))
    db_session.commit()

    with pytest.raises(IntegrityError):
        db_session.delete(account)
        db_session.commit()
    db_session.rollback()


def test_invalid_meal_type_rejected_by_check_constraint(tmp_path):
    """DB-level guard: an out-of-domain meal.type violates the CHECK constraint.

    Raw sqlite3 on purpose — there is no SQLAlchemy app-layer validation yet,
    so the CHECK constraint is the guard (fix D).
    """
    db_path = str(tmp_path / "check.db")
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)
    engine.dispose()

    conn = sqlite3.connect(db_path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO meal (name, normalized_name, type, is_active,"
                " times_kept, created_at, updated_at)"
                " VALUES ('Pancakes', 'pancakes', 'breakfast', 1, 0,"
                " '2026-08-26 12:00:00', '2026-08-26 12:00:00')"
            )
    finally:
        conn.close()
