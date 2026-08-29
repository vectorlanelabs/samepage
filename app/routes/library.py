"""Item library routes (M2b, T2.1–T2.2): browse/search/filter, create, edit,
archive/unarchive, type cycle, and the recipe view.

Every route requires a signed-in account, and every item lookup is scoped to
a meal collection owned by a group the signed-in account owns or admins —
this is a shared multi-tenant deployment, so an account must never be able to
browse, view, or mutate another group's library by guessing an item id or
just visiting the page while logged out. A nonexistent-or-not-yours item
returns 404, never 403, so browsing doesn't reveal that another group's item
exists.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Annotated
from urllib.parse import urlencode, urlparse

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.auth import require_account
from app.db import get_db
from app.models import Account, Collection, Group, GroupAdmin, Item, ItemTag, MealDetail, Tag
from app.templating import templates

router = APIRouter()

TYPE_LABELS = {"dinner": "Dinner", "lunch": "Lunch", "both": "Both"}
TYPE_HUES = {"dinner": 25, "lunch": 140, "both": 300}
TYPE_CYCLE = {"dinner": "lunch", "lunch": "both", "both": "dinner"}
VALID_TYPES = frozenset(TYPE_LABELS)


def _normalize_name(name: str) -> str:
    """D11 dedupe key, shared with scripts/seed.py: casefold + collapse."""
    return re.sub(r"\s+", " ", name.casefold()).strip()


def _type_pill_style(meal_type: str, interactive: bool = False) -> str:
    hue = TYPE_HUES[meal_type]
    cursor = "cursor:pointer;" if interactive else ""
    return (
        f"flex:none;border:none;border-radius:999px;padding:6px 10px;"
        f"font:700 10.5px var(--dd-font-body);{cursor}"
        f"background:oklch(0.92 0.05 {hue});color:oklch(0.4 0.1 {hue});"
    )


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


def _get_meal_collection(db: Session, account: Account) -> Collection | None:
    """The signed-in account's own meal-kind collection — a collection owned by
    a group `account` owns or admins. Never another group's collection, even
    if one exists first in the table."""
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


def _get_owned_item_or_404(db: Session, account: Account, item_id: int) -> Item:
    """An item, but only if it belongs to a collection `account` owns or
    admins — 404 (not 403) for anything else, so browsing never reveals that
    another group's item exists."""
    item = db.get(Item, item_id)
    if item is None or not _account_owns_collection(db, account, item.collection_id):
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


def _has_recipe(detail: MealDetail | None) -> bool:
    if detail is None:
        return False
    return bool(detail.source_url or detail.recipe_text or (detail.ingredients or "").strip())


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
    group_id: int,
    item: Item | None,
    detail: MealDetail | None,
    form: dict,
    selected_tags: list[str],
    error: str | None,
    status_code: int = 200,
):
    """Render meal_edit.html for a new (item=None) or existing item.

    ``form`` holds the current field values (name/type/ingredients/
    instructions/source_url) — from the item/detail for GETs, from the submitted
    POST body for 400 re-renders so nothing the user typed is lost.
    """
    meal_type = form["type"] if form["type"] in VALID_TYPES else "dinner"
    hue = TYPE_HUES[meal_type]
    return templates.TemplateResponse(
        request,
        "meal_edit.html",
        {
            "meal": item,  # keep template var name for compatibility
            "form": form,
            "selected_tags": selected_tags,
            "all_tags": _all_tags(db, group_id),
            "error": error,
            "track_label": TYPE_LABELS[meal_type],
            "track_style": (
                f"border:none;border-radius:999px;padding:9px 16px;margin-top:6px;"
                f"font:700 12px var(--dd-font-body);cursor:pointer;"
                f"background:oklch(0.92 0.05 {hue});color:oklch(0.4 0.1 {hue});"
            ),
        },
        status_code=status_code,
    )


def _empty_form(type: str = "dinner") -> dict:
    return {
        "name": "",
        "type": type if type in VALID_TYPES else "dinner",
        "ingredients": "",
        "instructions": "",
        "source_url": "",
    }


def _item_form(item: Item, detail: MealDetail | None) -> dict:
    if detail is None:
        detail_type = "dinner"
        ingredients = ""
        instructions = ""
        source_url = ""
    else:
        detail_type = detail.type
        ingredients = detail.ingredients or ""
        instructions = detail.recipe_text or ""
        source_url = detail.source_url or ""

    return {
        "name": item.name,
        "type": detail_type,
        "ingredients": ingredients,
        "instructions": instructions,
        "source_url": source_url,
    }


def _clean_form(
    name: str, type: str, ingredients: str, instructions: str, source_url: str
) -> dict:
    """Whitespace rules from the M2 spec: ingredients lose only trailing blank
    lines (internal blank lines are preserved); instructions lose trailing
    whitespace; name/source_url are trimmed."""
    return {
        "name": name.strip(),
        "type": type,
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
    if form["type"] not in VALID_TYPES:
        return "Type must be dinner, lunch, or both."
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
def library_page(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    q: str = "",
    type: str = "",
    tags: str = "",
    status: str = "active",
):
    """Library browse (signed-in accounts only): search (q), type / tag (OR) /
    status filters, scoped to the account's own group's collection."""
    account = require_account(request, db)

    # Resolve the account's own meal collection; if none exists, show empty state.
    collection = _get_meal_collection(db, account)
    if collection is None:
        return templates.TemplateResponse(
            request,
            "library.html",
            {
                "meals": [],
                "active_count": 0,
                "archived_count": 0,
                "q": q,
                "type": type,
                "tags": tags,
                "status": status,
                "type_filters": [],
                "status_filters": [],
                "tag_filters": [],
                "no_collection": True,
            },
        )

    type = type if type in VALID_TYPES else ""
    status = status if status in ("active", "archived", "all") else "active"
    tag_names = [t.strip() for t in tags.split(",") if t.strip()]

    stmt = select(Item).where(Item.collection_id == collection.id)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(Item.name.ilike(like) | Item.normalized_name.ilike(like))
    if type:
        # Join to meal_detail to filter by type.
        stmt = (
            stmt.join(MealDetail, MealDetail.item_id == Item.id)
            .where(MealDetail.type == type)
        )
    if tag_names:
        item_ids = db.scalars(
            select(ItemTag.item_id)
            .join(Tag, Tag.id == ItemTag.tag_id)
            .where(Tag.name.in_(tag_names))
            .distinct()
        ).all()
        stmt = stmt.where(Item.id.in_(item_ids))
    if status == "active":
        stmt = stmt.where(Item.archived_at.is_(None))
    elif status == "archived":
        stmt = stmt.where(Item.archived_at.is_not(None))
    items = db.scalars(stmt.order_by(Item.normalized_name)).all()
    item_ids = [item.id for item in items]

    # Fetch meal details and tags for this collection's items in one query each
    # (not one query per item, and not every item-tag link on the deployment).
    item_details: dict[int, MealDetail] = {
        detail.item_id: detail
        for detail in db.scalars(select(MealDetail).where(MealDetail.item_id.in_(item_ids)))
    }
    item_tags = db.execute(
        select(ItemTag.item_id, Tag.name)
        .join(Tag, Tag.id == ItemTag.tag_id)
        .where(ItemTag.item_id.in_(item_ids))
    ).all()
    tags_by_item: dict[int, list[str]] = defaultdict(list)
    for item_id, tag_name in item_tags:
        tags_by_item[item_id].append(tag_name)

    def _type_of(item: Item) -> str:
        detail = item_details.get(item.id)
        return detail.type if detail is not None else "dinner"

    rows = [
        {
            "id": item.id,
            "name": item.name,
            "type_label": TYPE_LABELS[_type_of(item)],
            "type_style": _type_pill_style(_type_of(item), interactive=True),
            "tags": sorted(tags_by_item.get(item.id, [])),
            "kept_label": f"Kept {item.times_kept}×" if item.times_kept > 0 else None,
            "has_recipe": _has_recipe(item_details.get(item.id)),
            "archived": item.archived_at is not None,
        }
        for item in items
    ]

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

    def _filter_url(overrides: dict) -> str:
        params = {"q": q, "type": type, "tags": tags, "status": status}
        params.update({k: v for k, v in overrides.items() if v is not None})
        params = {k: v for k, v in params.items() if v}
        return f"/library?{urlencode(params)}" if params else "/library"

    def _toggle_tag_url(tag_name: str) -> str:
        if tag_name in tag_names:
            new_tags = [t for t in tag_names if t != tag_name]
        else:
            new_tags = tag_names + [tag_name]
        return _filter_url({"tags": ",".join(new_tags)})

    type_filters = [
        {
            "label": "All" if key == "all" else TYPE_LABELS[key],
            "value": "" if key == "all" else key,
            "active": type == ("" if key == "all" else key),
        }
        for key in ("all", "dinner", "lunch", "both")
    ]
    status_filters = [
        {"label": label, "value": value, "active": status == value}
        for label, value in (("Active", "active"), ("Archived", "archived"), ("All", "all"))
    ]
    tag_filters = [
        {
            "name": tag.name,
            "url": _toggle_tag_url(tag.name),
            "selected": tag.name in tag_names,
        }
        for tag in _all_tags(db, collection.group_id)
    ]

    return templates.TemplateResponse(
        request,
        "library.html",
        {
            "meals": rows,
            "active_count": active_count,
            "archived_count": archived_count,
            "q": q,
            "type": type,
            "tags": tags,
            "status": status,
            "type_filters": type_filters,
            "status_filters": status_filters,
            "tag_filters": tag_filters,
        },
    )


@router.get("/library/new")
def new_meal_page(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    type: str = "dinner",
):
    """Blank edit page for a new item (admin-only). ``?type=`` presets the
    track; the in-form cycle button drives it from there."""
    account = require_account(request, db)
    collection = _get_meal_collection(db, account)
    if collection is None:
        raise HTTPException(400, "No meal collection exists yet. An admin needs to seed the library first.")
    return _render_edit(
        request, db, collection.group_id, None, None, _empty_form(type), [], error=None
    )


@router.get("/library/{item_id}")
def recipe_view(
    request: Request, item_id: int, db: Annotated[Session, Depends(get_db)]
):
    """Recipe view (signed-in accounts only, own group's items): name,
    type/tags, ingredients (bulleted), then instructions, then the optional
    original-source link."""
    account = require_account(request, db)
    item = _get_owned_item_or_404(db, account, item_id)
    detail = _item_meal_detail(db, item.id)
    ingredients = [
        line.strip()
        for line in (detail.ingredients or "" if detail else "").splitlines()
        if line.strip()
    ]

    return templates.TemplateResponse(
        request,
        "recipe.html",
        {
            "meal": item,  # keep template var name for compatibility
            "detail": detail,
            "tags": _item_tags(db, item.id),
            "type_label": TYPE_LABELS[detail.type if detail else "dinner"],
            "type_style": _type_pill_style(detail.type if detail else "dinner"),
            "ingredients": ingredients,
            "safe_source_url": _safe_source_url(detail.source_url if detail else None),
        },
    )


@router.get("/library/{item_id}/edit")
def edit_meal_page(
    request: Request, item_id: int, db: Annotated[Session, Depends(get_db)]
):
    """Edit page for an existing item (admin-only)."""
    account = require_account(request, db)
    item = _get_owned_item_or_404(db, account, item_id)
    detail = _item_meal_detail(db, item.id)
    collection = db.get(Collection, item.collection_id)
    if collection is None:
        raise HTTPException(500, "Collection not found")
    return _render_edit(
        request,
        db,
        collection.group_id,
        item,
        detail,
        _item_form(item, detail),
        _item_tags(db, item.id),
        error=None,
    )


@router.post("/library")
def create_meal(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    name: Annotated[str, Form()],
    type: Annotated[str, Form()],
    tags: Annotated[list[str] | None, Form()] = None,
    ingredients: Annotated[str, Form()] = "",
    instructions: Annotated[str, Form()] = "",
    source_url: Annotated[str, Form()] = "",
):
    """Create an item (admin-only). 303 to the new item's edit page."""
    account = require_account(request, db)
    collection = _get_meal_collection(db, account)
    if collection is None:
        raise HTTPException(400, "No meal collection exists yet. An admin needs to seed the library first.")

    tags = tags or []
    form = _clean_form(name, type, ingredients, instructions, source_url)
    error = _validate_form(form, db, collection.id)
    if error is not None:
        return _render_edit(
            request, db, collection.group_id, None, None, form, _tag_names(tags), error, status_code=400
        )
    item = Item(
        collection_id=collection.id,
        name=form["name"],
        normalized_name=_normalize_name(form["name"]),
        description=None,
    )
    db.add(item)
    db.flush()

    # Create meal_detail row.
    detail = MealDetail(
        item_id=item.id,
        type=form["type"],
        ingredients=form["ingredients"] or None,
        recipe_text=form["instructions"] or None,
        source_url=_safe_source_url(form["source_url"]) or None,
    )
    db.add(detail)

    for tag in _resolve_tags(db, collection.group_id, tags):
        db.add(ItemTag(item_id=item.id, tag_id=tag.id))
    db.commit()
    return RedirectResponse(f"/library/{item.id}/edit", status_code=303)


@router.post("/library/{item_id}")
def update_meal(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    item_id: int,
    name: Annotated[str, Form()],
    type: Annotated[str, Form()],
    tags: Annotated[list[str] | None, Form()] = None,
    ingredients: Annotated[str, Form()] = "",
    instructions: Annotated[str, Form()] = "",
    source_url: Annotated[str, Form()] = "",
):
    """Update an item (admin-only): rename recomputes normalized_name; the
    collision check excludes this item itself."""
    account = require_account(request, db)
    tags = tags or []
    item = _get_owned_item_or_404(db, account, item_id)
    detail = _item_meal_detail(db, item.id)
    collection = db.get(Collection, item.collection_id)
    if collection is None:
        raise HTTPException(500, "Collection not found")

    form = _clean_form(name, type, ingredients, instructions, source_url)
    error = _validate_form(form, db, collection.id, exclude_item_id=item.id)
    if error is not None:
        return _render_edit(
            request,
            db,
            collection.group_id,
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

    # Update meal_detail.
    if detail is None:
        detail = MealDetail(item_id=item.id)
        db.add(detail)
    detail.type = form["type"]
    detail.ingredients = form["ingredients"] or None
    detail.recipe_text = form["instructions"] or None
    detail.source_url = _safe_source_url(form["source_url"]) or None

    db.commit()
    return RedirectResponse(f"/library/{item.id}/edit", status_code=303)


@router.post("/library/{item_id}/archive")
def archive_meal(
    request: Request, item_id: int, db: Annotated[Session, Depends(get_db)]
):
    """Archive (admin-only, reversible — never deleted, D16)."""
    account = require_account(request, db)
    item = _get_owned_item_or_404(db, account, item_id)
    item.archived_at = func.now()
    db.commit()
    return RedirectResponse("/library", status_code=303)


@router.post("/library/{item_id}/unarchive")
def unarchive_meal(
    request: Request, item_id: int, db: Annotated[Session, Depends(get_db)]
):
    """Restore an archived item (admin-only)."""
    account = require_account(request, db)
    item = _get_owned_item_or_404(db, account, item_id)
    item.archived_at = None
    db.commit()
    return RedirectResponse("/library", status_code=303)


@router.post("/library/{item_id}/cycle-type")
def cycle_type(
    request: Request, item_id: int, db: Annotated[Session, Depends(get_db)]
):
    """Type cycle dinner → lunch → both → dinner (admin-only)."""
    account = require_account(request, db)
    item = _get_owned_item_or_404(db, account, item_id)
    detail = _item_meal_detail(db, item.id)
    if detail is None:
        detail = MealDetail(item_id=item.id, type="dinner")
        db.add(detail)
    detail.type = TYPE_CYCLE[detail.type]
    db.commit()
    return RedirectResponse("/library", status_code=303)


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
