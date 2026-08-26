"""Model round-trip + integrity constraints for every table in plan §6."""

import sqlite3

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError

from app.db import Base
from app.models import (
    Batch,
    BatchMeal,
    Category,
    Meal,
    MealTag,
    Person,
    Session,
    SessionParticipant,
    Tag,
    Vote,
)


def test_full_round_trip(db_session):
    person = Person(name="Ada", pin_hash="pbkdf2-hash")
    category = Category(name="Tab 1", sort_order=1, legacy_sheet_index=1)
    tag = Tag(name="takeout")
    db_session.add_all([person, category, tag])
    db_session.flush()

    meal = Meal(name="Tacos", normalized_name="tacos", type="dinner", category_id=category.id)
    db_session.add(meal)
    db_session.flush()
    db_session.add(MealTag(meal_id=meal.id, tag_id=tag.id))

    session = Session(
        code="TACO-1234",
        status="lobby",
        created_by_person_id=person.id,
        lunch_target=0,
        dinner_target=2,
    )
    db_session.add(session)
    db_session.flush()

    batch = Batch(session_id=session.id, seq=1, track="dinner")
    db_session.add(batch)
    db_session.flush()

    db_session.add(BatchMeal(batch_id=batch.id, meal_id=meal.id, sort_order=1))
    vote = Vote(batch_id=batch.id, person_id=person.id, meal_id=meal.id, choice="yes")
    db_session.add(vote)
    db_session.commit()

    # Prove persistence by expiring and re-reading from the database.
    db_session.expire_all()

    assert db_session.get(Person, person.id).name == "Ada"
    assert db_session.get(Category, category.id).name == "Tab 1"
    assert db_session.get(Tag, tag.id).name == "takeout"
    meal_q = db_session.get(Meal, meal.id)
    assert meal_q.name == "Tacos"
    assert meal_q.type == "dinner"
    assert meal_q.normalized_name == "tacos"
    assert db_session.get(MealTag, (meal.id, tag.id)) is not None
    session_q = db_session.get(Session, session.id)
    assert session_q.code == "TACO-1234"
    assert session_q.status == "lobby"
    assert session_q.dinner_target == 2
    assert db_session.get(SessionParticipant, (session.id, person.id)) is None  # not joined
    batch_q = db_session.get(Batch, batch.id)
    assert batch_q.track == "dinner"
    assert batch_q.status == "open"
    batch_meal_q = db_session.get(BatchMeal, (batch.id, meal.id))
    assert batch_meal_q.sort_order == 1
    vote_q = db_session.get(Vote, vote.id)
    assert vote_q.choice == "yes"
    assert vote_q.batch_id == batch.id


def test_duplicate_vote_raises_integrity_error(db_session):
    person = Person(name="Bob", pin_hash="pbkdf2-hash")
    meal = Meal(name="Pasta", normalized_name="pasta", type="dinner")
    db_session.add_all([person, meal])
    db_session.flush()

    session = Session(
        code="PAST-0001",
        status="voting",
        created_by_person_id=person.id,
        lunch_target=0,
        dinner_target=1,
    )
    db_session.add(session)
    db_session.flush()

    batch = Batch(session_id=session.id, seq=1, track="dinner")
    db_session.add(batch)
    db_session.flush()

    db_session.add(Vote(batch_id=batch.id, person_id=person.id, meal_id=meal.id, choice="yes"))
    db_session.commit()

    with pytest.raises(IntegrityError):
        db_session.add(Vote(batch_id=batch.id, person_id=person.id, meal_id=meal.id, choice="no"))
        db_session.commit()
    db_session.rollback()


def test_delete_referenced_person_raises_integrity_error(db_session):
    """No cascade deletes: a person referenced by a session cannot be deleted."""
    person = Person(name="Cara", pin_hash="pbkdf2-hash")
    db_session.add(person)
    db_session.flush()
    db_session.add(
        Session(
            code="CARA-0002",
            status="lobby",
            created_by_person_id=person.id,
            lunch_target=1,
            dinner_target=1,
        )
    )
    db_session.commit()

    with pytest.raises(IntegrityError):
        db_session.delete(person)
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
