"""Seed loader (M2b, T2.4 / D7/D11): idempotently load ``seed/meals.json``.

Run from the repo root::

    uv run python -m scripts.seed <group_id>

Reads ``seed/meals.json`` READ-ONLY (never mutated) and loads it into the
database pointed at by ``SP_DB_PATH`` (default ``data/samepage.db``) under
the specified group. The schema must already exist — run ``uv run alembic upgrade head``
first. The app's own startup does this, so booting once before seeding works too.

Requires a target group_id as a positional CLI argument. The group must already exist
(create via POST /groups after signup). If no group with that id exists, exits with a
clear error message.

Idempotently creates or reuses exactly one Collection(kind='meal', group_id=<given>,
name='Meal Planner') for that group. Then loads the 155 seeded meals into Items
under that collection, with a 1:1 MealDetail row for meal-specific fields (type,
ingredients, recipe_text, source_url).

Dedupe key is ``normalized_name`` (casefold + collapsed whitespace, D11):
any item whose normalized name already exists in the collection is skipped and
logged — one-time seed, household edits win. A second run inserts nothing.

``main(seed_path=None, db=None, group_id=None)`` is the testable entry point:
tests pass a session bound to a throwaway engine, a group_id, and optionally a
custom seed path.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Category, Collection, Item, ItemTag, MealDetail, Tag
from app.settings import REPO_ROOT

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

DEFAULT_SEED_PATH = REPO_ROOT / "seed" / "meals.json"


def _normalize(name: str) -> str:
    """D11 dedupe key: casefold + collapsed whitespace."""
    return re.sub(r"\s+", " ", name.casefold()).strip()


def _category_index(name: str) -> int | None:
    """Trailing sheet index for a 'Tab N' category name, else None."""
    match = re.search(r"(\d+)\s*$", name)
    return int(match.group(1)) if match else None


def _load(db: Session, seed_path: Path, group_id: int) -> None:
    # Verify the group exists.
    from app.models import Group
    group = db.get(Group, group_id)
    if group is None:
        raise ValueError(f"No group with id {group_id}")

    data = json.loads(seed_path.read_text(encoding="utf-8"))
    meals_data = data.get("meals", [])

    # Get or create the meal collection for this group.
    collection = db.scalar(
        select(Collection).where(
            (Collection.group_id == group_id) & (Collection.kind == "meal")
        )
    )
    if collection is None:
        collection = Collection(group_id=group_id, kind="meal", name="Meal Planner")
        db.add(collection)
        db.flush()

    # Normalized names already in this collection.
    existing_normalized = set(
        db.scalars(
            select(Item.normalized_name).where(Item.collection_id == collection.id)
        ).all()
    )

    created_items = 0
    created_categories = 0
    created_tags = 0
    skipped = 0

    for meal_data in meals_data:
        name = meal_data["name"]
        normalized = _normalize(name)
        if normalized in existing_normalized:
            print(f"skip (exists): {name}")
            skipped += 1
            continue

        # Get or create category, scoped to this collection.
        category = None
        cat_name = meal_data.get("category")
        if cat_name:
            category = db.scalar(
                select(Category).where(
                    (Category.collection_id == collection.id) & (Category.name == cat_name)
                )
            )
            if category is None:
                index = _category_index(cat_name)
                if index is None:
                    print(
                        f"skip (category): {name} — '{cat_name}' has no sheet index"
                    )
                    skipped += 1
                    continue
                category = Category(
                    collection_id=collection.id,
                    name=cat_name,
                    sort_order=index,
                    legacy_sheet_index=index,
                )
                db.add(category)
                db.flush()
                created_categories += 1

        # Get or create tags, scoped to the group.
        tag_objects = []
        for tag_name in meal_data.get("tags", []):
            tag = db.scalar(
                select(Tag).where(
                    (Tag.group_id == group_id) & (Tag.name == tag_name)
                )
            )
            if tag is None:
                tag = Tag(group_id=group_id, name=tag_name)
                db.add(tag)
                db.flush()
                created_tags += 1
            tag_objects.append(tag)

        # Create the item.
        item = Item(
            collection_id=collection.id,
            name=name,
            normalized_name=normalized,
            description=None,
            category_id=category.id if category is not None else None,
            times_offered=0,
            times_kept=0,
        )
        db.add(item)
        db.flush()
        # Within-run dedupe: a name appearing twice in the seed file is a skip
        # on the second occurrence, not a second insert.
        existing_normalized.add(normalized)

        # Create the meal_detail row.
        meal_detail = MealDetail(
            item_id=item.id,
            type=meal_data.get("type", "dinner"),
            ingredients=None,
            recipe_text=None,
            source_url=meal_data.get("source_url") or None,
        )
        db.add(meal_detail)

        # Create item_tag links.
        for tag in tag_objects:
            db.add(ItemTag(item_id=item.id, tag_id=tag.id))

        created_items += 1

    db.commit()
    print(
        f"seeded: {created_items} items, {created_categories} categories, "
        f"{created_tags} tags (skipped: {skipped})"
    )


def main(seed_path: Path | str | None = None, db: Session | None = None, group_id: int | None = None) -> None:
    """Load the seed into the given session (tests) or the configured DB.

    Args:
        seed_path: Path to seed JSON file (default: DEFAULT_SEED_PATH)
        db: SQLAlchemy session (if None, uses SessionLocal)
        group_id: Target group ID (required)
    """
    if group_id is None:
        raise ValueError("group_id is required")

    path = Path(seed_path) if seed_path is not None else DEFAULT_SEED_PATH
    if db is not None:
        _load(db, path, group_id)
    else:
        with SessionLocal() as session:
            _load(session, path, group_id)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: uv run python -m scripts.seed <group_id>")
        print()
        print("No group with id <N> — create an account (POST /signup) and a group (POST /groups) first,")
        print("then re-run with that group's id.")
        sys.exit(1)

    try:
        group_id = int(sys.argv[1])
    except ValueError:
        print(f"Error: group_id must be an integer, got '{sys.argv[1]}'")
        sys.exit(1)

    try:
        main(group_id=group_id)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
