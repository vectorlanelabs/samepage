"""Seed loader tests (M2b, T2.4 / D7/D11): counts, dedupe, idempotency,
household-edits-win. Each test runs against a fresh tmp DB via the
``db_session`` fixture and passes it to ``scripts.seed.main`` explicitly —
the real DB is never touched."""

from sqlalchemy import func, select

from app.models import Account, Category, Collection, Group, Item, ItemTag, MealDetail, Tag
from scripts import seed as seed_module

SEED_PATH = seed_module.DEFAULT_SEED_PATH


def _make_group(db):
    """Create an account and group for seed loading."""
    account = Account(email="owner@example.com", display_name="Owner")
    db.add(account)
    db.flush()

    group = Group(name="Test Group", owner_account_id=account.id)
    db.add(group)
    db.commit()
    return group


def _run(db, group_id):
    seed_module.main(SEED_PATH, db=db, group_id=group_id)


def _count(db, model):
    return db.scalar(select(func.count()).select_from(model)) or 0


def test_seed_loads_full_library(db_session):
    group = _make_group(db_session)
    _run(db_session, group.id)

    assert _count(db_session, Item) == 154
    assert _count(db_session, Category) == 8
    assert _count(db_session, Tag) >= 1
    assert _count(db_session, ItemTag) >= 1
    assert _count(db_session, MealDetail) == 154

    # Categories are "Tab 1".."Tab 8" with the sheet index recorded (D8).
    categories = db_session.scalars(select(Category).order_by(Category.name)).all()
    assert [c.name for c in categories] == [f"Tab {i}" for i in range(1, 9)]
    assert all(c.legacy_sheet_index == int(c.name.split()[-1]) for c in categories)

    # D10: the curated lunch-capable subset is seeded as "both".
    both = db_session.scalar(
        select(func.count()).select_from(MealDetail).where(MealDetail.type == "both")
    )
    assert both == 27

    # The 4 spreadsheet recipe links land in source_url.
    url_meals = db_session.scalars(
        select(Item).join(MealDetail).where(MealDetail.source_url.is_not(None))
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
        select(func.count()).select_from(ItemTag).where(ItemTag.tag_id == takeout.id)
    )
    assert takeout_links == 10


def test_seed_is_idempotent(db_session):
    group = _make_group(db_session)
    _run(db_session, group.id)
    assert _count(db_session, Item) == 154
    _run(db_session, group.id)
    assert _count(db_session, Item) == 154
    assert _count(db_session, Category) == 8
    assert _count(db_session, Tag) == 1  # takeout only, no re-creation


def test_seed_skips_existing_household_edit(db_session):
    """An item the household already added (or edited) wins over the seed.

    "bacon and eggs" is in the seed as type "both"; the household's version
    is "dinner" — after seeding, its type is unchanged and no second row
    appears (154 = 1 pre-existing + 153 seeded — the seed file itself carries a
    real duplicate, "chicken parm", whose second occurrence is skipped).
    """
    group = _make_group(db_session)
    collection = Collection(group_id=group.id, kind="meal", name="Meal Planner")
    db_session.add(collection)
    db_session.flush()

    item = Item(
        collection_id=collection.id,
        name="Bacon and Eggs (house style)",
        normalized_name="bacon and eggs",
    )
    db_session.add(item)
    db_session.flush()

    # Add meal detail for the pre-existing item.
    detail = MealDetail(item_id=item.id, type="dinner")
    db_session.add(detail)
    db_session.commit()

    _run(db_session, group.id)

    assert _count(db_session, Item) == 154
    meal = db_session.scalar(select(Item).where(Item.normalized_name == "bacon and eggs"))
    assert meal is not None
    assert meal.name == "Bacon and Eggs (house style)"
    meal_detail = db_session.get(MealDetail, meal.id)
    assert meal_detail.type == "dinner"  # household edit wins over the seed's "both"


def test_seed_orders_categories_by_sheet_index(db_session):
    group = _make_group(db_session)
    _run(db_session, group.id)
    categories = db_session.scalars(
        select(Category).order_by(Category.sort_order)
    ).all()
    assert [c.name for c in categories] == [f"Tab {i}" for i in range(1, 9)]


def test_seed_within_run_duplicate_name_skipped(tmp_path, db_session):
    """A name appearing twice inside one seed file inserts exactly once — the
    second occurrence is a skip (its normalized name was added to the seen set
    on the first insert), never a second row. Regression for the within-run
    dedupe gap: the seen set was only loaded once up front, so in-file
    duplicates both inserted despite the docstring promising a skip."""
    import json

    seed_path = tmp_path / "dupes.json"
    seed_path.write_text(
        json.dumps(
            {
                "meals": [
                    {"name": "Tacos", "type": "dinner"},
                    {"name": "tacos", "type": "lunch"},  # same normalized name
                    {"name": "Burgers", "type": "dinner"},
                ]
            }
        ),
        encoding="utf-8",
    )
    group = _make_group(db_session)
    seed_module.main(seed_path, db=db_session, group_id=group.id)

    assert _count(db_session, Item) == 2
    # First occurrence wins; the duplicate was skipped, not merged.
    meals = db_session.scalars(select(Item).order_by(Item.normalized_name)).all()
    assert [m.name for m in meals] == ["Burgers", "Tacos"]
    tacos = db_session.scalar(select(Item).where(Item.normalized_name == "tacos"))
    assert tacos is not None
    assert db_session.get(MealDetail, tacos.id).type == "dinner"


def test_seed_requires_group_id(db_session):
    """Seed fails with clear error when group_id is not provided."""
    import pytest
    with pytest.raises(ValueError, match="group_id is required"):
        seed_module.main(SEED_PATH, db=db_session, group_id=None)


def test_seed_fails_on_missing_group(db_session):
    """Seed fails with clear error when group doesn't exist."""
    import pytest
    with pytest.raises(ValueError, match="No group with id"):
        seed_module.main(SEED_PATH, db=db_session, group_id=999)
