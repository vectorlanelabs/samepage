"""Item library routes (M2b, T2.1–T2.2; M2c part 2, collection-scoped routing):
browse/search/filter, create, edit, archive/unarchive, type cycle, the recipe
view, and the legacy /library redirect.

Every route requires a signed-in account, and every lookup is scoped to the
collection in the URL: the collection must belong to a group the signed-in
account owns or admins, and an item must belong to that exact collection —
this is a shared multi-tenant deployment, so an account must never be able to
browse, view, or mutate another group's library by guessing a collection or
item id, or by mixing ids across collections. A nonexistent-or-not-yours
resource returns 404, never 403, so browsing doesn't reveal that another
group's collection or item exists.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Annotated
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.auth import require_account
from app.db import get_db
from app.models import (
    Account,
    Collection,
    Group,
    GroupAdmin,
    Ingredient,
    Item,
    ItemTag,
    MealDetail,
    MealIngredient,
    MealType,
    Tag,
)
from app.templating import templates

router = APIRouter()

# Meal slots are a set now (a meal can be breakfast *and* dinner). MEAL_TYPES is
# the canonical display order; a meal has any non-empty subset.
MEAL_TYPES = ("breakfast", "lunch", "dinner")
MEAL_TYPE_LABELS = {"breakfast": "Breakfast", "lunch": "Lunch", "dinner": "Dinner"}
VALID_MEAL_TYPES = frozenset(MEAL_TYPES)

# A "time tag" is a group tag whose name looks like a duration ("40 min",
# "40min") — the library splits these into their own Time dropdown.
TIME_TAG_RE = re.compile(r"^\d+\s?min$", re.IGNORECASE)


def _parse_meal_types(raw: list[str] | None) -> list[str]:
    """Validated, deduped meal types in canonical order (breakfast, lunch,
    dinner). Unknown values are dropped."""
    selected = set(raw or [])
    return [t for t in MEAL_TYPES if t in selected]


def _types_label(types: list[str]) -> str:
    """Human label for a set of slots, e.g. 'Breakfast · Dinner'. Empty when the
    meal has no slots (shouldn't happen for valid meals, but degrade gracefully)."""
    return " · ".join(MEAL_TYPE_LABELS[t] for t in types)


def _item_meal_types(db: Session, item_id: int) -> list[str]:
    rows = db.scalars(
        select(MealType.meal_type).where(MealType.item_id == item_id)
    ).all()
    return _parse_meal_types(list(rows))


def _set_meal_types(db: Session, item_id: int, types: list[str]) -> None:
    """Replace an item's meal-type set with `types` (already validated)."""
    db.execute(delete(MealType).where(MealType.item_id == item_id))
    for t in types:
        db.add(MealType(item_id=item_id, meal_type=t))


def _normalize_ingredient(name: str) -> str:
    """Canonical ingredient key: casefold + collapse whitespace. Lowercasing is
    intentional — 'Onion' and 'onion' are one ingredient for metrics."""
    return re.sub(r"\s+", " ", name.casefold()).strip()


def _clean_ingredient_names(raw_names: list[str]) -> list[str]:
    """Normalize + dedupe a list of ingredient names (from a block textarea's
    lines or an API list), dropping blanks, preserving first-seen order."""
    names: list[str] = []
    seen: set[str] = set()
    for raw in raw_names:
        name = _normalize_ingredient(raw)
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


def _resolve_ingredients(db: Session, group_id: int, names: list[str]) -> list[Ingredient]:
    """Get-or-create group-scoped ingredients (like tags), returned in order."""
    resolved: list[Ingredient] = []
    for name in names:
        ing = db.scalar(
            select(Ingredient).where(
                (Ingredient.group_id == group_id) & (Ingredient.name == name)
            )
        )
        if ing is None:
            ing = Ingredient(group_id=group_id, name=name)
            db.add(ing)
            db.flush()
        resolved.append(ing)
    return resolved


def _set_meal_ingredients(
    db: Session, group_id: int, item_id: int, raw_names: list[str]
) -> None:
    """Replace an item's ingredient set. `raw_names` are un-normalized lines
    (textarea) or list entries (API); they're cleaned/deduped here."""
    names = _clean_ingredient_names(raw_names)
    db.execute(delete(MealIngredient).where(MealIngredient.item_id == item_id))
    for position, ing in enumerate(_resolve_ingredients(db, group_id, names)):
        db.add(
            MealIngredient(item_id=item_id, ingredient_id=ing.id, position=position)
        )


def _item_ingredients(db: Session, item_id: int) -> list[str]:
    """An item's ingredient names in entry order."""
    return list(
        db.scalars(
            select(Ingredient.name)
            .join(MealIngredient, MealIngredient.ingredient_id == Ingredient.id)
            .where(MealIngredient.item_id == item_id)
            .order_by(MealIngredient.position)
        ).all()
    )


def _normalize_name(name: str) -> str:
    """D11 dedupe key: casefold + collapse whitespace."""
    return re.sub(r"\s+", " ", name.casefold()).strip()


def _account_owns_collection(db: Session, account: Account, collection_id: int) -> bool:
    """True iff `collection_id` belongs to a group `account` owns or admins."""
    collection = db.get(Collection, collection_id)
    if collection is None:
        return False
    group = db.get(Group, collection.group_id)
    if group is None:
        return False
    if group.owner_account_id == account.id:
        return True
    return (
        db.scalar(
            select(GroupAdmin).where(
                (GroupAdmin.group_id == group.id) & (GroupAdmin.account_id == account.id)
            )
        )
        is not None
    )


def _get_owned_collection_or_404(db: Session, account: Account, collection_id: int) -> Collection:
    """A collection, but only if it belongs to a group `account` owns or
    admins — 404 (not 403) for a collection that doesn't exist or isn't
    theirs, so browsing never reveals another group's collection exists."""
    if not _account_owns_collection(db, account, collection_id):
        raise HTTPException(404, "No such collection")
    collection = db.get(Collection, collection_id)
    if collection is None:
        raise HTTPException(404, "No such collection")
    return collection


def _get_meal_collection(db: Session, account: Account) -> Collection | None:
    """The signed-in account's own meal-kind collection — a collection owned by
    a group `account` owns or admins. Never another group's collection, even
    if one exists first in the table. Only used by the legacy /library redirect."""
    return db.scalar(
        select(Collection)
        .join(Group, Group.id == Collection.group_id)
        .outerjoin(
            GroupAdmin,
            (GroupAdmin.group_id == Group.id) & (GroupAdmin.account_id == account.id),
        )
        .where(
            Collection.kind == "meal",
            (Group.owner_account_id == account.id) | (GroupAdmin.account_id == account.id),
        )
        .order_by(Collection.id)
        .limit(1)
    )


def _get_owned_item_or_404(db: Session, collection: Collection, item_id: int) -> Item:
    """An item, but only if it exists AND lives in the already-guarded
    collection from the URL — 404 (not 403) for anything else. Ownership is
    established by the collection guard; this check is existence plus
    membership in that exact collection, so item ids can't be mixed across
    collections."""
    item = db.get(Item, item_id)
    if item is None or item.collection_id != collection.id:
        raise HTTPException(404, "No such item")
    return item


def _item_tags(db: Session, item_id: int) -> list[str]:
    return list(
        db.scalars(
            select(Tag.name)
            .join(ItemTag, ItemTag.tag_id == Tag.id)
            .where(ItemTag.item_id == item_id)
            .order_by(Tag.name)
        ).all()
    )


def _item_meal_detail(db: Session, item_id: int) -> MealDetail | None:
    return db.scalar(select(MealDetail).where(MealDetail.item_id == item_id))


def _safe_source_url(url: str | None) -> str | None:
    """Return url only when it is an absolute http(s) URL with a host, else None."""
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    return url


def _all_tags(db: Session, group_id: int) -> list[Tag]:
    """All tags scoped to a group."""
    return list(db.scalars(select(Tag).where(Tag.group_id == group_id).order_by(Tag.name)).all())


def _render_edit(
    request: Request,
    db: Session,
    collection: Collection,
    item: Item | None,
    detail: MealDetail | None,
    form: dict,
    selected_tags: list[str],
    error: str | None,
    status_code: int = 200,
    flash: str | None = None,
):
    """Render meal_edit.html for a new (item=None) or existing item.

    ``form`` holds the current field values (name/types/ingredients/
    instructions/source_url) — from the item/detail for GETs, from the submitted
    POST body for 400 re-renders so nothing the user typed is lost.
    """
    all_tags = _all_tags(db, collection.group_id)
    applied = set(selected_tags)
    applied_tags = [t for t in all_tags if t.name in applied]
    other_tags = [t for t in all_tags if t.name not in applied]
    # "View recipe →" renders only when the item actually has recipe content —
    # the same definition the old library row used (ingredients, or a
    # meal_detail carrying instructions/source). Persisted state, so a 400
    # re-render doesn't flip it based on a half-submitted form.
    ingredient_names = _item_ingredients(db, item.id) if item is not None else []
    has_recipe = bool(ingredient_names) or bool(
        detail is not None and (detail.source_url or detail.recipe_text)
    )
    return templates.TemplateResponse(
        request,
        "meal_edit.html",
        {
            "meal": item,  # keep template var name for compatibility
            "collection": collection,
            "form": form,
            "selected_tags": selected_tags,
            "all_tags": all_tags,
            "applied_tags": applied_tags,
            "other_tags": other_tags,
            "has_recipe": has_recipe,
            "meal_type_options": [
                {"value": t, "label": MEAL_TYPE_LABELS[t], "checked": t in form["types"]}
                for t in MEAL_TYPES
            ],
            "error": error,
            "flash": flash,
        },
        status_code=status_code,
    )


def _empty_form(type: str = "dinner") -> dict:
    preset = type if type in VALID_MEAL_TYPES else "dinner"
    return {
        "name": "",
        "types": [preset],
        "ingredients": "",
        "instructions": "",
        "source_url": "",
    }


def _item_form(db: Session, item: Item, detail: MealDetail | None) -> dict:
    instructions = detail.recipe_text or "" if detail else ""
    source_url = detail.source_url or "" if detail else ""
    return {
        "name": item.name,
        "types": _item_meal_types(db, item.id),
        # The textarea is the editable source of truth; prefill it from the
        # structured ingredients, one per line, in entry order.
        "ingredients": "\n".join(_item_ingredients(db, item.id)),
        "instructions": instructions,
        "source_url": source_url,
    }


def _clean_form(
    name: str, types: list[str], ingredients: str, instructions: str, source_url: str
) -> dict:
    """Whitespace rules from the M2 spec: ingredients lose only trailing blank
    lines (internal blank lines are preserved); instructions lose trailing
    whitespace; name/source_url are trimmed. ``types`` is validated to the
    canonical meal-type set."""
    return {
        "name": name.strip(),
        "types": _parse_meal_types(types),
        "ingredients": ingredients.rstrip("\r\n"),
        "instructions": instructions.rstrip(),
        "source_url": source_url.strip(),
    }


def _resolve_tags(db: Session, group_id: int, raw_tags: list[str]) -> list[Tag]:
    """Create any missing tags (group-scoped tags are freely created) and return
    the Tag rows in submitted order, deduped by name."""
    tags: list[Tag] = []
    seen: set[str] = set()
    for raw in raw_tags:
        name = raw.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        tag = db.scalar(
            select(Tag).where((Tag.group_id == group_id) & (Tag.name == name))
        )
        if tag is None:
            tag = Tag(group_id=group_id, name=name)
            db.add(tag)
            db.flush()
        tags.append(tag)
    return tags


def _validate_form(
    form: dict, db: Session, collection_id: int, exclude_item_id: int | None = None
) -> str | None:
    """Return an error message, or None when the form is valid."""
    if not form["name"]:
        return "Name is required."
    if not form["types"]:
        return "Pick at least one of breakfast, lunch, or dinner."
    if form["source_url"] and _safe_source_url(form["source_url"]) is None:
        return "Source URL must start with http:// or https://."
    normalized = _normalize_name(form["name"])
    collision = select(Item.id).where(
        (Item.collection_id == collection_id) & (Item.normalized_name == normalized)
    )
    if exclude_item_id is not None:
        collision = collision.where(Item.id != exclude_item_id)
    if db.scalar(collision) is not None:
        return "An item with that name already exists in this collection."
    return None


@router.get("/library")
def legacy_library_redirect(request: Request, db: Annotated[Session, Depends(get_db)]):
    """Legacy /library (plan §9): 303 to the account's first meal collection,
    or to the collections hub when the account has none. Every other /library
    route was deleted — the library now lives at /collections/{id}."""
    account = require_account(request, db)
    collection = _get_meal_collection(db, account)
    if collection is None:
        return RedirectResponse("/collections", status_code=303)
    return RedirectResponse(f"/collections/{collection.id}", status_code=303)


@router.get("/collections/{collection_id}")
def library_page(
    request: Request,
    collection_id: int,
    db: Annotated[Session, Depends(get_db)],
    q: str = "",
    type: str = "",
    tags: str = "",
    time: str = "",
    status: str = "active",
    added: int = 0,
):
    """Collection browse (signed-in accounts only): search (q), type / tag (OR)
    / time (AND) / status filters, scoped to the collection in the URL.
    ``?added=1`` (set by the create redirect) shows a "meal added" confirmation
    banner."""
    account = require_account(request, db)
    collection = _get_owned_collection_or_404(db, account, collection_id)

    type = type if type in VALID_MEAL_TYPES else ""
    status = status if status in ("active", "archived", "all") else "active"
    tag_names = [t.strip() for t in tags.split(",") if t.strip()]
    # The Time dropdown is one more tag filter — AND-ed with the Tags select.
    # Only values shaped like a duration (^\d+\s?min$, the same regex that
    # splits the dropdown) are applied; anything else is ignored, as if absent.
    time_names: list[str] = []
    for part in time.split(","):
        name = part.strip()
        if name and TIME_TAG_RE.match(name):
            time_names.append(name)

    stmt = select(Item).where(Item.collection_id == collection.id)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(Item.name.ilike(like) | Item.normalized_name.ilike(like))
    if type:
        # Items that have this slot in their meal-type set.
        stmt = stmt.where(
            Item.id.in_(select(MealType.item_id).where(MealType.meal_type == type))
        )
    if tag_names:
        item_ids = db.scalars(
            select(ItemTag.item_id)
            .join(Tag, Tag.id == ItemTag.tag_id)
            .where(Tag.name.in_(tag_names))
            .distinct()
        ).all()
        stmt = stmt.where(Item.id.in_(item_ids))
    for time_name in time_names:
        item_ids = db.scalars(
            select(ItemTag.item_id)
            .join(Tag, Tag.id == ItemTag.tag_id)
            .where(Tag.name == time_name)
            .distinct()
        ).all()
        stmt = stmt.where(Item.id.in_(item_ids))
    if status == "active":
        stmt = stmt.where(Item.archived_at.is_(None))
    elif status == "archived":
        stmt = stmt.where(Item.archived_at.is_not(None))
    items = db.scalars(stmt.order_by(Item.normalized_name)).all()
    item_ids = [item.id for item in items]

    # Fetch tags for this collection's items in one query (not one query per
    # item, and not every item-tag link on the deployment).
    item_tags = db.execute(
        select(ItemTag.item_id, Tag.name)
        .join(Tag, Tag.id == ItemTag.tag_id)
        .where(ItemTag.item_id.in_(item_ids))
    ).all()
    tags_by_item: dict[int, list[str]] = defaultdict(list)
    for item_id, tag_name in item_tags:
        tags_by_item[item_id].append(tag_name)

    type_rows = db.execute(
        select(MealType.item_id, MealType.meal_type).where(MealType.item_id.in_(item_ids))
    ).all()
    raw_types_by_item: dict[int, list[str]] = defaultdict(list)
    for item_id, meal_type in type_rows:
        raw_types_by_item[item_id].append(meal_type)

    def _types_of(item: Item) -> list[str]:
        return _parse_meal_types(raw_types_by_item.get(item.id, []))

    rows = [
        {
            "id": item.id,
            "name": item.name,
            "type_label": _types_label(_types_of(item)),
            "tags": sorted(tags_by_item.get(item.id, [])),
            "kept_label": f"kept {item.times_kept}×" if item.times_kept > 0 else None,
            "archived": item.archived_at is not None,
        }
        for item in items
    ]
    # Row subtitle: "{type} · {tags…}" — the archived marker is a trailing
    # " · archived" suffix. Missing parts are omitted (no dangling dots).
    for row in rows:
        parts = [p for p in [row["type_label"], *row["tags"]] if p]
        if row["archived"]:
            parts.append("archived")
        row["subtitle"] = " · ".join(parts) or None

    active_count = (
        db.scalar(
            select(func.count()).select_from(Item).where(
                (Item.collection_id == collection.id) & (Item.archived_at.is_(None))
            )
        )
        or 0
    )
    archived_count = (
        db.scalar(
            select(func.count()).select_from(Item).where(
                (Item.collection_id == collection.id) & (Item.archived_at.is_not(None))
            )
        )
        or 0
    )

    # Filters render as compact dropdowns (v4): one <select> each for type,
    # tag, and time. Options carry their own selected flag; the form GETs back
    # to this same page. "Time tags" (names like "40 min") are split out of the
    # tag list into their own Time dropdown (route-side, so the template never
    # decides what counts as a duration).
    type_options = [
        {
            "label": "All" if key == "all" else MEAL_TYPE_LABELS[key],
            "value": "" if key == "all" else key,
            "selected": type == ("" if key == "all" else key),
        }
        for key in ("all", *MEAL_TYPES)
    ]
    # Tag filtering keeps its comma-separated OR-capable param, but the dropdown
    # picks one at a time; a single selected tag round-trips.
    all_group_tags = _all_tags(db, collection.group_id)
    selected_tag = tag_names[0] if tag_names else ""
    tag_options = [{"label": "Any", "value": "", "selected": not selected_tag}] + [
        {"label": tag.name, "value": tag.name, "selected": tag.name == selected_tag}
        for tag in all_group_tags
        if not TIME_TAG_RE.match(tag.name)
    ]
    # The Time dropdown posts a single time tag; the route ANDs it with the
    # Tags select (and any other filters).
    selected_time = time_names[0] if time_names else ""
    time_options = [{"label": "Any", "value": "", "selected": not selected_time}] + [
        {"label": tag.name, "value": tag.name, "selected": tag.name == selected_time}
        for tag in all_group_tags
        if TIME_TAG_RE.match(tag.name)
    ]

    any_filter_active = bool(q or type or tag_names or time_names or status != "active")

    return templates.TemplateResponse(
        request,
        "library.html",
        {
            "collection": collection,
            "meals": rows,
            "active_count": active_count,
            "archived_count": archived_count,
            "collection_empty": active_count == 0 and archived_count == 0,
            "q": q,
            "type": type,
            "tags": tags,
            "time": time,
            "status": status,
            "viewing_archived": status == "archived",
            "type_options": type_options,
            "tag_options": tag_options,
            "time_options": time_options,
            "has_tags": len(tag_options) > 1,
            "has_times": len(time_options) > 1,
            "any_filter_active": any_filter_active,
            "clear_url": f"/collections/{collection.id}",
            "flash": "Meal added." if added else None,
        },
    )


@router.get("/collections/{collection_id}/items/new")
def new_meal_page(
    request: Request,
    collection_id: int,
    db: Annotated[Session, Depends(get_db)],
    type: str = "dinner",
):
    """Blank edit page for a new item in the URL's collection (signed-in
    account, own collection). ``?type=`` presets one slot; the in-form
    checkboxes drive the set from there."""
    account = require_account(request, db)
    collection = _get_owned_collection_or_404(db, account, collection_id)
    return _render_edit(
        request, db, collection, None, None, _empty_form(type), [], error=None
    )


@router.get("/collections/{collection_id}/items/{item_id}")
def recipe_view(
    request: Request,
    collection_id: int,
    item_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """Recipe view (signed-in accounts only, own collection's items): name,
    types/tags, ingredients (bulleted), then instructions, then the optional
    original-source link."""
    account = require_account(request, db)
    collection = _get_owned_collection_or_404(db, account, collection_id)
    item = _get_owned_item_or_404(db, collection, item_id)
    detail = _item_meal_detail(db, item.id)
    ingredients = _item_ingredients(db, item.id)

    return templates.TemplateResponse(
        request,
        "recipe.html",
        {
            "meal": item,  # keep template var name for compatibility
            "collection": collection,
            "detail": detail,
            "tags": _item_tags(db, item.id),
            "type_labels": [MEAL_TYPE_LABELS[t] for t in _item_meal_types(db, item.id)],
            "ingredients": ingredients,
            "safe_source_url": _safe_source_url(detail.source_url if detail else None),
        },
    )


@router.get("/collections/{collection_id}/items/{item_id}/edit")
def edit_meal_page(
    request: Request,
    collection_id: int,
    item_id: int,
    db: Annotated[Session, Depends(get_db)],
    saved: int = 0,
):
    """Edit page for an existing item (signed-in account, own collection).
    ``?saved=1`` (set by the update redirect) shows a "changes saved" banner."""
    account = require_account(request, db)
    collection = _get_owned_collection_or_404(db, account, collection_id)
    item = _get_owned_item_or_404(db, collection, item_id)
    detail = _item_meal_detail(db, item.id)
    return _render_edit(
        request,
        db,
        collection,
        item,
        detail,
        _item_form(db, item, detail),
        _item_tags(db, item.id),
        error=None,
        flash="Changes saved." if saved else None,
    )


@router.post("/collections/{collection_id}/items")
def create_meal(
    request: Request,
    collection_id: int,
    db: Annotated[Session, Depends(get_db)],
    name: Annotated[str, Form()],
    types: Annotated[list[str] | None, Form()] = None,
    tags: Annotated[list[str] | None, Form()] = None,
    ingredients: Annotated[str, Form()] = "",
    instructions: Annotated[str, Form()] = "",
    source_url: Annotated[str, Form()] = "",
):
    """Create an item in the URL's collection (signed-in account, own
    collection — the item is inserted into the URL's collection, replacing the
    old implicit 'first meal collection' binding). 303 to the new item's edit
    page."""
    account = require_account(request, db)
    collection = _get_owned_collection_or_404(db, account, collection_id)

    tags = tags or []
    form = _clean_form(name, types or [], ingredients, instructions, source_url)
    error = _validate_form(form, db, collection.id)
    if error is not None:
        return _render_edit(
            request, db, collection, None, None, form, _tag_names(tags), error, status_code=400
        )
    item = Item(
        collection_id=collection.id,
        name=form["name"],
        normalized_name=_normalize_name(form["name"]),
        description=None,
    )
    db.add(item)
    db.flush()

    _set_meal_types(db, item.id, form["types"])
    _set_meal_ingredients(
        db, collection.group_id, item.id, form["ingredients"].splitlines()
    )
    # Create meal_detail row.
    detail = MealDetail(
        item_id=item.id,
        recipe_text=form["instructions"] or None,
        source_url=_safe_source_url(form["source_url"]) or None,
    )
    db.add(detail)

    for tag in _resolve_tags(db, collection.group_id, tags):
        db.add(ItemTag(item_id=item.id, tag_id=tag.id))
    db.commit()
    # Land back in the library so the new meal is visibly there — a redirect to
    # the edit page looked identical to the add form and read as "nothing saved".
    return RedirectResponse(f"/collections/{collection.id}?added=1", status_code=303)


@router.post("/collections/{collection_id}/items/{item_id}")
def update_meal(
    request: Request,
    collection_id: int,
    item_id: int,
    db: Annotated[Session, Depends(get_db)],
    name: Annotated[str, Form()],
    types: Annotated[list[str] | None, Form()] = None,
    tags: Annotated[list[str] | None, Form()] = None,
    ingredients: Annotated[str, Form()] = "",
    instructions: Annotated[str, Form()] = "",
    source_url: Annotated[str, Form()] = "",
):
    """Update an item (signed-in account, own collection): rename recomputes
    normalized_name; the collision check excludes this item itself."""
    account = require_account(request, db)
    tags = tags or []
    collection = _get_owned_collection_or_404(db, account, collection_id)
    item = _get_owned_item_or_404(db, collection, item_id)
    detail = _item_meal_detail(db, item.id)

    form = _clean_form(name, types or [], ingredients, instructions, source_url)
    error = _validate_form(form, db, collection.id, exclude_item_id=item.id)
    if error is not None:
        return _render_edit(
            request,
            db,
            collection,
            item,
            detail,
            form,
            _tag_names(tags),
            error,
            status_code=400,
        )
    item.name = form["name"]
    item.normalized_name = _normalize_name(form["name"])
    db.execute(delete(ItemTag).where(ItemTag.item_id == item.id))
    for tag in _resolve_tags(db, collection.group_id, tags):
        db.add(ItemTag(item_id=item.id, tag_id=tag.id))

    _set_meal_types(db, item.id, form["types"])
    _set_meal_ingredients(
        db, collection.group_id, item.id, form["ingredients"].splitlines()
    )
    # Update meal_detail.
    if detail is None:
        detail = MealDetail(item_id=item.id)
        db.add(detail)
    detail.recipe_text = form["instructions"] or None
    detail.source_url = _safe_source_url(form["source_url"]) or None

    db.commit()
    # Stay on the edit page (you may keep editing) but confirm the save.
    return RedirectResponse(
        f"/collections/{collection.id}/items/{item.id}/edit?saved=1", status_code=303
    )


@router.post("/collections/{collection_id}/items/{item_id}/archive")
def archive_meal(
    request: Request,
    collection_id: int,
    item_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """Archive (signed-in account, own collection, reversible — never deleted,
    D16)."""
    account = require_account(request, db)
    collection = _get_owned_collection_or_404(db, account, collection_id)
    item = _get_owned_item_or_404(db, collection, item_id)
    item.archived_at = func.now()
    db.commit()
    return RedirectResponse(f"/collections/{collection.id}", status_code=303)


@router.post("/collections/{collection_id}/items/{item_id}/unarchive")
def unarchive_meal(
    request: Request,
    collection_id: int,
    item_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """Restore an archived item (signed-in account, own collection)."""
    account = require_account(request, db)
    collection = _get_owned_collection_or_404(db, account, collection_id)
    item = _get_owned_item_or_404(db, collection, item_id)
    item.archived_at = None
    db.commit()
    return RedirectResponse(f"/collections/{collection.id}", status_code=303)


def _tag_names(raw_tags: list[str]) -> list[str]:
    """Dedupe + strip submitted tag names for re-render (create/update 400s)."""
    seen: set[str] = set()
    names: list[str] = []
    for raw in raw_tags:
        name = raw.strip()
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names
