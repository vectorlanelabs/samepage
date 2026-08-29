"""Token-authenticated JSON API (M6a, plan §8 M6): external AI tools read and
write a group's library items and read its aggregate reports.

Verb scope (locked): NO session, voting, or participant endpoints — a token
can never create, drive, or vote in a session. Report responses are
aggregate-only; per-person data never leaves the app.

Auth model: every request carries ``Authorization: Bearer <token>``.
``require_api_group`` resolves the token to exactly ONE group up front — the
single scoping choke point (plan §8 M6d) — and every query below starts from
the guarded group. A collection/item id that doesn't exist or belongs to
another group is a 404 (never 403, no existence oracle), so a token can
never reach another group's data. These routes live under ``/api/v1``, which
the origin middleware already exempts (Bearer auth makes CSRF irrelevant).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ApiToken, Collection, Group, Item, ItemTag, MealDetail, Tag
from app.routes.library import (
    VALID_TYPES,
    _item_meal_detail,
    _item_tags,
    _normalize_name,
    _resolve_tags,
    _safe_source_url,
)
from app.routes.reports import NOT_OFFERED_LATELY_COUNT, _rate_row
from app.tokens import hash_token

router = APIRouter(prefix="/api/v1", tags=["api"])


def require_api_group(
    db: Annotated[Session, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
) -> Group:
    """Resolve the Bearer token to exactly one Group — the API's single
    scoping choke point. 401 when the header is absent/malformed or the token
    doesn't match a stored hash; the matched token's ``last_used_at`` is
    refreshed and the token's group returned."""
    if authorization is None:
        raise HTTPException(401, "API token required")
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(401, "API token required")
    api_token = db.scalar(
        select(ApiToken).where(ApiToken.token_hash == hash_token(parts[1].strip()))
    )
    if api_token is None:
        raise HTTPException(401, "Invalid API token")
    group = db.get(Group, api_token.group_id)
    if group is None:
        raise HTTPException(401, "Invalid API token")
    api_token.last_used_at = func.now()
    db.commit()
    return group


def _get_group_collection_or_404(db: Session, group: Group, collection_id: int) -> Collection:
    """A collection, but only if it belongs to the token's group — 404 (never
    403) for a collection that doesn't exist or belongs to another group, so a
    token can't probe for other groups' collections (no existence oracle)."""
    collection = db.get(Collection, collection_id)
    if collection is None or collection.group_id != group.id:
        raise HTTPException(404, "No such collection")
    return collection


def _get_group_item_or_404(db: Session, group: Group, item_id: int) -> Item:
    """An item, but only if its collection belongs to the token's group — 404
    for an item that doesn't exist or lives under another group (no existence
    oracle, no cross-group reach)."""
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(404, "No such item")
    collection = db.get(Collection, item.collection_id)
    if collection is None or collection.group_id != group.id:
        raise HTTPException(404, "No such item")
    return item


def _item_json(db: Session, item: Item) -> dict:
    """The API's item shape: name/type/tags/detail fields plus the favorites
    counters and archived flag — same fields the library page joins together."""
    detail = _item_meal_detail(db, item.id)
    return {
        "id": item.id,
        "name": item.name,
        "type": detail.type if detail is not None else "dinner",
        "tags": _item_tags(db, item.id),
        "ingredients": detail.ingredients if detail is not None else None,
        "recipe_text": detail.recipe_text if detail is not None else None,
        "source_url": detail.source_url if detail is not None else None,
        "times_offered": item.times_offered,
        "times_kept": item.times_kept,
        "last_kept_at": item.last_kept_at,
        "archived": item.archived_at is not None,
    }


def _require_valid_source_url(source_url: str) -> str | None:
    """Trim + sanitize a source_url; 400 when it isn't an absolute http(s) URL
    (same rule as the library form)."""
    url = source_url.strip()
    if url and _safe_source_url(url) is None:
        raise HTTPException(400, "Source URL must start with http:// or https://.")
    return _safe_source_url(url) or None


def _check_name_collision(
    db: Session, collection_id: int, normalized: str, exclude_item_id: int | None
) -> None:
    """409 when another item in the collection already has this normalized
    name (the same D11 dedupe key the library form uses)."""
    stmt = select(Item.id).where(
        (Item.collection_id == collection_id) & (Item.normalized_name == normalized)
    )
    if exclude_item_id is not None:
        stmt = stmt.where(Item.id != exclude_item_id)
    if db.scalar(stmt) is not None:
        raise HTTPException(409, "An item with that name already exists")


class ItemCreate(BaseModel):
    name: str
    type: str = "dinner"
    tags: list[str] = []
    ingredients: str | None = None
    recipe_text: str | None = None
    source_url: str | None = None


class ItemUpdate(BaseModel):
    name: str | None = None
    type: str | None = None
    tags: list[str] | None = None
    ingredients: str | None = None
    recipe_text: str | None = None
    source_url: str | None = None


@router.get("/collections")
def list_collections(
    db: Annotated[Session, Depends(get_db)],
    group: Annotated[Group, Depends(require_api_group)],
):
    """The token's group's collections only — never another group's."""
    collections = db.scalars(
        select(Collection).where(Collection.group_id == group.id).order_by(Collection.id)
    ).all()
    return {
        "collections": [{"id": c.id, "name": c.name, "kind": c.kind} for c in collections]
    }


@router.get("/collections/{collection_id}/items")
def list_items(
    collection_id: int,
    db: Annotated[Session, Depends(get_db)],
    group: Annotated[Group, Depends(require_api_group)],
):
    """The collection's items (active and archived — the ``archived`` flag
    lets tools filter), joined with meal_detail + tags like the library page."""
    collection = _get_group_collection_or_404(db, group, collection_id)
    items = db.scalars(
        select(Item).where(Item.collection_id == collection.id).order_by(Item.normalized_name)
    ).all()
    return {"items": [_item_json(db, item) for item in items]}


@router.post("/collections/{collection_id}/items", status_code=201)
def create_item(
    collection_id: int,
    payload: ItemCreate,
    db: Annotated[Session, Depends(get_db)],
    group: Annotated[Group, Depends(require_api_group)],
):
    """Create an item in the token's group's collection. Name is required
    (400 when blank), type must be dinner/lunch/both (400), and a normalized-
    name collision is a 409. Tags are group-scoped get-or-create, exactly like
    the library create path."""
    collection = _get_group_collection_or_404(db, group, collection_id)

    name = payload.name.strip()
    if not name:
        raise HTTPException(400, "Name is required.")
    if payload.type not in VALID_TYPES:
        raise HTTPException(400, "Type must be dinner, lunch, or both.")
    source_url = _require_valid_source_url(payload.source_url) if payload.source_url else None
    _check_name_collision(db, collection.id, _normalize_name(name), exclude_item_id=None)

    item = Item(
        collection_id=collection.id,
        name=name,
        normalized_name=_normalize_name(name),
        description=None,
    )
    db.add(item)
    db.flush()

    detail = MealDetail(
        item_id=item.id,
        type=payload.type,
        ingredients=(payload.ingredients or "").rstrip("\r\n") or None,
        recipe_text=(payload.recipe_text or "").rstrip() or None,
        source_url=source_url,
    )
    db.add(detail)
    for tag in _resolve_tags(db, collection.group_id, payload.tags):
        db.add(ItemTag(item_id=item.id, tag_id=tag.id))
    db.commit()
    return _item_json(db, item)


@router.patch("/items/{item_id}")
def update_item(
    item_id: int,
    payload: ItemUpdate,
    db: Annotated[Session, Depends(get_db)],
    group: Annotated[Group, Depends(require_api_group)],
):
    """Partial update of an item in the token's group. Any of
    name/type/tags/ingredients/recipe_text/source_url may be provided; a
    rename recomputes normalized_name and a collision is a 409. Validation
    runs before anything is mutated, so a failed request changes nothing."""
    item = _get_group_item_or_404(db, group, item_id)
    collection = db.get(Collection, item.collection_id)
    if collection is None:
        raise HTTPException(404, "No such item")

    fields = payload.model_fields_set
    name = payload.name
    if "name" in fields:
        name = payload.name.strip() if payload.name else ""
        if not name:
            raise HTTPException(400, "Name is required.")
    if "type" in fields and payload.type is not None and payload.type not in VALID_TYPES:
        raise HTTPException(400, "Type must be dinner, lunch, or both.")
    if "name" in fields:
        _check_name_collision(db, collection.id, _normalize_name(name), exclude_item_id=item.id)
    source_url = None
    if "source_url" in fields and payload.source_url:
        source_url = _require_valid_source_url(payload.source_url)

    detail = _item_meal_detail(db, item.id)
    if detail is None:
        detail = MealDetail(item_id=item.id)
        db.add(detail)

    if "name" in fields:
        item.name = name
        item.normalized_name = _normalize_name(name)
    if "type" in fields and payload.type is not None:
        detail.type = payload.type
    if "tags" in fields:
        db.execute(delete(ItemTag).where(ItemTag.item_id == item.id))
        for tag in _resolve_tags(db, collection.group_id, payload.tags or []):
            db.add(ItemTag(item_id=item.id, tag_id=tag.id))
    if "ingredients" in fields:
        detail.ingredients = (payload.ingredients or "").rstrip("\r\n") or None
    if "recipe_text" in fields:
        detail.recipe_text = (payload.recipe_text or "").rstrip() or None
    if "source_url" in fields:
        detail.source_url = source_url if payload.source_url else None

    db.commit()
    return _item_json(db, item)


@router.get("/collections/{collection_id}/report")
def collection_report(
    collection_id: int,
    db: Annotated[Session, Depends(get_db)],
    group: Annotated[Group, Depends(require_api_group)],
):
    """The same reject-rate data reports.py computes (by_item, by_tag,
    not_offered_lately) for the token's group's collection — aggregate
    counters only, never per-person data. Every query starts from the guarded
    collection id."""
    collection = _get_group_collection_or_404(db, group, collection_id)

    item_rows = [
        {
            **_rate_row(item.name, item.times_offered, item.times_kept),
            "last_kept": (
                item.last_kept_at.strftime("%b %d, %Y") if item.last_kept_at else None
            ),
        }
        for item in db.scalars(
            select(Item).where(
                (Item.collection_id == collection.id) & (Item.times_offered > 0)
            )
        ).all()
    ]
    item_rows.sort(key=lambda r: (-r["reject_rate"], r["name"].casefold()))

    tag_rows = [
        _rate_row(tag_name, offered, kept)
        for tag_name, offered, kept in db.execute(
            select(Tag.name, func.sum(Item.times_offered), func.sum(Item.times_kept))
            .select_from(Item)
            .join(ItemTag, ItemTag.item_id == Item.id)
            .join(Tag, Tag.id == ItemTag.tag_id)
            .where(Item.collection_id == collection.id)
            .group_by(Tag.id, Tag.name)
        ).all()
        if offered > 0
    ]
    tag_rows.sort(key=lambda r: (-r["reject_rate"], r["name"].casefold()))

    not_offered_rows = [
        {"name": item.name, "times_offered": item.times_offered}
        for item in db.scalars(
            select(Item)
            .where((Item.collection_id == collection.id) & (Item.archived_at.is_(None)))
            .order_by(Item.times_offered, Item.normalized_name)
            .limit(NOT_OFFERED_LATELY_COUNT)
        ).all()
    ]

    return {
        "by_item": item_rows,
        "by_tag": tag_rows,
        "not_offered_lately": not_offered_rows,
    }
