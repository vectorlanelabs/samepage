"""Seed loader (M2, T2.4 / D7/D11): idempotently load ``seed/meals.json``.

Run from the repo root::

    uv run python -m scripts.seed

Reads ``seed/meals.json`` READ-ONLY (never mutated) and loads it into the
database pointed at by ``DD_DB_PATH`` (default ``data/dinnerdecider.db``).
The schema must already exist — run ``uv run alembic upgrade head`` first
(the app's own startup does this, so booting once before seeding works too).
Dedupe key is ``normalized_name`` (casefold + collapsed whitespace, D11):
any meal whose normalized name already exists in the DB is skipped and
logged — one-time seed, household edits win. A second run inserts nothing.

``main(seed_path, db=session)`` is the testable entry point: tests pass a
session bound to a throwaway engine instead of touching the real DB.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Category, Meal, MealTag, Tag
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


def _load(db: Session, seed_path: Path) -> None:
    data = json.loads(seed_path.read_text(encoding="utf-8"))
    meals_data = data.get("meals", [])

    # Normalized names already in the DB *before* this run. The set is read
    # once and never grown mid-run: pre-existing rows win (household edits),
    # and the seed's own rows are all inserted (the committed JSON is the
    # single source of truth for a fresh install — 155 meals).
    existing_normalized = set(db.scalars(select(Meal.normalized_name)).all())

    created_meals = 0
    created_categories = 0
    created_tags = 0
    skipped = 0

    for item in meals_data:
        name = item["name"]
        normalized = _normalize(name)
        if normalized in existing_normalized:
            print(f"skip (exists): {name}")
            skipped += 1
            continue

        category = None
        cat_name = item.get("category")
        if cat_name:
            category = db.scalar(select(Category).where(Category.name == cat_name))
            if category is None:
                index = _category_index(cat_name)
                if index is None:
                    print(
                        f"skip (category): {name} — '{cat_name}' has no sheet index"
                    )
                else:
                    category = Category(
                        name=cat_name, sort_order=index, legacy_sheet_index=index
                    )
                    db.add(category)
                    db.flush()
                    created_categories += 1
            # else: an existing category (e.g. from a previous run or created
            # in-app) is reused as-is — never clobbered.

        tag_objects = []
        for tag_name in item.get("tags", []):
            tag = db.scalar(select(Tag).where(Tag.name == tag_name))
            if tag is None:
                tag = Tag(name=tag_name)
                db.add(tag)
                db.flush()
                created_tags += 1
            tag_objects.append(tag)

        meal = Meal(
            name=name,
            normalized_name=normalized,
            type=item.get("type", "dinner"),
            source_url=item.get("source_url") or None,
            is_active=True,
            category_id=category.id if category is not None else None,
        )
        db.add(meal)
        db.flush()
        for tag in tag_objects:
            db.add(MealTag(meal_id=meal.id, tag_id=tag.id))
        created_meals += 1

    db.commit()
    print(
        f"seeded: {created_meals} meals, {created_categories} categories, "
        f"{created_tags} tags (skipped: {skipped})"
    )


def main(seed_path: Path | str | None = None, db: Session | None = None) -> None:
    """Load the seed into the given session (tests) or the configured DB."""
    path = Path(seed_path) if seed_path is not None else DEFAULT_SEED_PATH
    if db is not None:
        _load(db, path)
    else:
        with SessionLocal() as session:
            _load(session, path)


if __name__ == "__main__":
    main()
