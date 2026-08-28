"""Seed loader tests (M2, T2.4 / D7/D11): counts, dedupe, idempotency,
household-edits-win. Each test runs against a fresh tmp DB via the
``db_session`` fixture and passes it to ``scripts.seed.main`` explicitly —
the real DB is never touched."""

from sqlalchemy import func, select

from app.models import Category, Meal, MealTag, Tag
from scripts import seed as seed_module

SEED_PATH = seed_module.DEFAULT_SEED_PATH


def _run(db):
    seed_module.main(SEED_PATH, db=db)


def _count(db, model):
    return db.scalar(select(func.count()).select_from(model)) or 0


def test_seed_loads_full_library(db_session):
    _run(db_session)
    assert _count(db_session, Meal) == 155
    assert _count(db_session, Category) == 8
    assert _count(db_session, Tag) >= 1
    assert _count(db_session, MealTag) >= 1

    # Categories are "Tab 1".."Tab 8" with the sheet index recorded (D8).
    categories = db_session.scalars(select(Category).order_by(Category.name)).all()
    assert [c.name for c in categories] == [f"Tab {i}" for i in range(1, 9)]
    assert all(c.legacy_sheet_index == int(c.name.split()[-1]) for c in categories)

    # D10: the curated lunch-capable subset is seeded as "both".
    both = db_session.scalar(
        select(func.count()).select_from(Meal).where(Meal.type == "both")
    )
    assert both == 27

    # The 4 spreadsheet recipe links land in source_url.
    url_meals = db_session.scalars(
        select(Meal).where(Meal.source_url.is_not(None))
    ).all()
    assert len(url_meals) == 4
    assert {m.name for m in url_meals} == {
        "Garlic bread French bread pizza",
        "Rosemary lemon pork chops",
        "Tatertot Hotdish",
        "Lettuce wraps",
    }

    # D8: the 10 known takeout meals are auto-tagged.
    takeout = db_session.scalar(select(Tag).where(Tag.name == "takeout"))
    assert takeout is not None
    takeout_links = db_session.scalar(
        select(func.count()).select_from(MealTag).where(MealTag.tag_id == takeout.id)
    )
    assert takeout_links == 10


def test_seed_is_idempotent(db_session):
    _run(db_session)
    assert _count(db_session, Meal) == 155
    _run(db_session)
    assert _count(db_session, Meal) == 155
    assert _count(db_session, Category) == 8
    assert _count(db_session, Tag) == 1  # takeout only, no re-creation


def test_seed_skips_existing_household_edit(db_session):
    """A meal the household already added (or edited) wins over the seed.

    "bacon and eggs" is in the seed as type "both"; the household's version
    is "dinner" — after seeding, its type is unchanged and no second row
    appears (155 = 1 pre-existing + 154 seeded).
    """
    db_session.add(
        Meal(
            name="Bacon and Eggs (house style)",
            normalized_name="bacon and eggs",
            type="dinner",
            is_active=True,
        )
    )
    db_session.commit()

    _run(db_session)

    assert _count(db_session, Meal) == 155
    meal = db_session.scalar(select(Meal).where(Meal.normalized_name == "bacon and eggs"))
    assert meal is not None
    assert meal.name == "Bacon and Eggs (house style)"
    assert meal.type == "dinner"  # household edit wins over the seed's "both"


def test_seed_orders_categories_by_sheet_index(db_session):
    _run(db_session)
    categories = db_session.scalars(
        select(Category).order_by(Category.sort_order)
    ).all()
    assert [c.name for c in categories] == [f"Tab {i}" for i in range(1, 9)]
