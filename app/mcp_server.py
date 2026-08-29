"""MCP server (M6b, plan §8 M6): the external AI-tool surface, mounted at /mcp.

Wraps the SAME per-group operations as the M6a JSON API (app/routes/api.py)
with the same scoping rules — it does not re-implement business logic. Auth
is the same per-group Bearer token: every tool resolves the caller's group
via ``_group_for_request`` BEFORE any tool logic runs (plan §8 M6d — a token
resolves to exactly one group at auth time), and every query filters by that
group. A collection/item id that doesn't exist or belongs to another group is
a raised ToolError, mirroring api.py's 404 behavior (no existence oracle).

Verb scope (locked): NO session, voting, or participant tools — a token can
never create, drive, or vote in a session. Reports are aggregate/outcome
only; per-person data never leaves the app. No tool deletes anything.

The header is read inside each tool from the streamable-HTTP request via
``get_http_headers`` (FastMCP dependency). ``authorization`` is stripped by
default, so it is explicitly included. Tests call the tools through
``fastmcp.Client(mcp)`` in-memory and monkeypatch this module's
``get_http_headers`` to return a crafted Bearer header — see tests/test_mcp.py.
"""

from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_http_headers
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db import SessionLocal
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

mcp = FastMCP("Same Page")


# ---------- auth + scoping choke points ----------


def _group_for_request(db: Session) -> Group:
    """Resolve the caller's group from the request's Bearer token.

    The single scoping choke point for every tool (plan §8 M6d): a token
    resolves to exactly one group before any tool logic runs. Missing or
    invalid tokens raise ToolError. The matched token's ``last_used_at`` is
    refreshed, exactly like api.py's ``require_api_group``.
    """
    headers = get_http_headers(include={"authorization"})
    authorization = headers.get("authorization") or headers.get("Authorization")
    if authorization is None:
        raise ToolError("Invalid or missing API token")
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise ToolError("Invalid or missing API token")
    api_token = db.scalar(
        select(ApiToken).where(ApiToken.token_hash == hash_token(parts[1].strip()))
    )
    if api_token is None:
        raise ToolError("Invalid or missing API token")
    group = db.get(Group, api_token.group_id)
    if group is None:
        raise ToolError("Invalid or missing API token")
    api_token.last_used_at = func.now()
    db.commit()
    return group


def _get_group_collection(db: Session, group: Group, collection_id: int) -> Collection:
    """A collection, but only if it belongs to the token's group — ToolError
    for a collection that doesn't exist or belongs to another group (mirrors
    api.py's ``_get_group_collection_or_404`` as a raised ToolError)."""
    collection = db.get(Collection, collection_id)
    if collection is None or collection.group_id != group.id:
        raise ToolError("No such collection")
    return collection


def _get_group_item(db: Session, group: Group, item_id: int) -> Item:
    """An item, but only if its collection belongs to the token's group —
    ToolError for an item that doesn't exist or lives under another group
    (mirrors api.py's ``_get_group_item_or_404``)."""
    item = db.get(Item, item_id)
    if item is None:
        raise ToolError("No such item")
    collection = db.get(Collection, item.collection_id)
    if collection is None or collection.group_id != group.id:
        raise ToolError("No such item")
    return item


def _item_json(db: Session, item: Item) -> dict:
    """The API's item shape: name/type/tags/detail fields plus the favorites
    counters and archived flag (same fields as api.py's ``_item_json``)."""
    detail = _item_meal_detail(db, item.id)
    return {
        "id": item.id,
        "name": item.name,
        "type": detail.type if detail is not None else "dinner",
        "tags": _item_tags(db, item.id),
        "ingredients": detail.ingredients if detail is not None else None,
        "recipe_text": detail.recipe_text if detail is not None else None,
        "source_url": detail.source_url if detail is not None else None,
        "times_kept": item.times_kept,
        "last_kept_at": item.last_kept_at,
        "archived": item.archived_at is not None,
    }


def _require_valid_source_url(source_url: str) -> str | None:
    """Trim + sanitize a source_url; ToolError when it isn't an absolute
    http(s) URL (same rule as api.py)."""
    url = source_url.strip()
    if url and _safe_source_url(url) is None:
        raise ToolError("Source URL must start with http:// or https://.")
    return _safe_source_url(url) or None


def _check_name_collision(
    db: Session, collection_id: int, normalized: str, exclude_item_id: int | None
) -> None:
    """ToolError when another item in the collection already has this
    normalized name (the same D11 dedupe key api.py uses)."""
    stmt = select(Item.id).where(
        (Item.collection_id == collection_id) & (Item.normalized_name == normalized)
    )
    if exclude_item_id is not None:
        stmt = stmt.where(Item.id != exclude_item_id)
    if db.scalar(stmt) is not None:
        raise ToolError("An item with that name already exists")


# ---------- tools ----------


@mcp.tool()
def list_collections() -> list[dict]:
    """List the collections of the group that owns the request's API token."""
    db = SessionLocal()
    try:
        group = _group_for_request(db)
        collections = db.scalars(
            select(Collection).where(Collection.group_id == group.id).order_by(Collection.id)
        ).all()
        return [{"id": c.id, "name": c.name, "kind": c.kind} for c in collections]
    finally:
        db.close()


@mcp.tool()
def list_items(collection_id: int) -> list[dict]:
    """List the items in one of the group's collections, including recipe details and tags."""
    db = SessionLocal()
    try:
        group = _group_for_request(db)
        collection = _get_group_collection(db, group, collection_id)
        items = db.scalars(
            select(Item).where(Item.collection_id == collection.id).order_by(Item.normalized_name)
        ).all()
        return [_item_json(db, item) for item in items]
    finally:
        db.close()


@mcp.tool()
def add_item(
    collection_id: int,
    name: str,
    type: str = "dinner",
    tags: list[str] | None = None,
    ingredients: str = "",
    recipe_text: str = "",
    source_url: str = "",
) -> dict:
    """Add a meal (or other item) to one of the group's collections."""
    db = SessionLocal()
    try:
        group = _group_for_request(db)
        collection = _get_group_collection(db, group, collection_id)

        name = name.strip()
        if not name:
            raise ToolError("Name is required.")
        if type not in VALID_TYPES:
            raise ToolError("Type must be dinner, lunch, or both.")
        source_url = _require_valid_source_url(source_url)
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
            type=type,
            ingredients=ingredients.rstrip("\r\n") or None,
            recipe_text=recipe_text.rstrip() or None,
            source_url=source_url,
        )
        db.add(detail)
        for tag in _resolve_tags(db, collection.group_id, tags or []):
            db.add(ItemTag(item_id=item.id, tag_id=tag.id))
        db.commit()
        return _item_json(db, item)
    finally:
        db.close()


@mcp.tool()
def update_item(
    item_id: int,
    name: str | None = None,
    type: str | None = None,
    tags: list[str] | None = None,
    ingredients: str | None = None,
    recipe_text: str | None = None,
    source_url: str | None = None,
) -> dict:
    """Update an item in one of the group's collections; only the fields provided change."""
    db = SessionLocal()
    try:
        group = _group_for_request(db)
        item = _get_group_item(db, group, item_id)
        collection = db.get(Collection, item.collection_id)
        if collection is None:
            raise ToolError("No such item")

        if name is not None:
            name = name.strip()
            if not name:
                raise ToolError("Name is required.")
            _check_name_collision(db, collection.id, _normalize_name(name), exclude_item_id=item.id)
        if type is not None and type not in VALID_TYPES:
            raise ToolError("Type must be dinner, lunch, or both.")
        source_url = None
        if source_url is not None and source_url:
            source_url = _require_valid_source_url(source_url)

        detail = _item_meal_detail(db, item.id)
        if detail is None:
            detail = MealDetail(item_id=item.id)
            db.add(detail)

        if name is not None:
            item.name = name
            item.normalized_name = _normalize_name(name)
        if type is not None:
            detail.type = type
        if tags is not None:
            db.execute(delete(ItemTag).where(ItemTag.item_id == item.id))
            for tag in _resolve_tags(db, collection.group_id, tags):
                db.add(ItemTag(item_id=item.id, tag_id=tag.id))
        if ingredients is not None:
            detail.ingredients = ingredients.rstrip("\r\n") or None
        if recipe_text is not None:
            detail.recipe_text = recipe_text.rstrip() or None
        if source_url is not None:
            detail.source_url = source_url if source_url else None

        db.commit()
        return _item_json(db, item)
    finally:
        db.close()


@mcp.tool()
def get_report(collection_id: int) -> dict:
    """Get the reject-rate report for one of the group's collections (aggregate counts only)."""
    db = SessionLocal()
    try:
        group = _group_for_request(db)
        collection = _get_group_collection(db, group, collection_id)

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

        return {"by_item": item_rows, "by_tag": tag_rows, "not_offered_lately": not_offered_rows}
    finally:
        db.close()


mcp_app = mcp.http_app(path="/")
