"""M6b tests (plan §8 M6): the MCP server at app/mcp_server.py.

Auth testing approach (documented): the MCP tools read the Bearer token from
the streamable-HTTP request via ``get_http_headers``. The in-memory
``fastmcp.Client(mcp)`` transport has no HTTP request, so header auth is
exercised by monkeypatching ``app.mcp_server.get_http_headers`` to return a
crafted ``{"authorization": "Bearer <token>"}`` — the exact dict the real
dependency returns for an HTTP call with that header (FastMCP lowercases
header names; the tool accepts both cases). This is reliable: it exercises
the full auth path (header → hash_token → ApiToken lookup → group) while
keeping the fast, dependency-free in-memory transport. The mounted HTTP app
itself is boot-tested separately (combined lifespan + mount), and the M6a
suite already proves the same token works over real HTTP.

ToolError surfaces as a raised ``fastmcp.exceptions.ToolError`` from
``client.call_tool`` (``raise_on_error=True`` default) — assertions use
``pytest.raises(ToolError)``.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app import mcp_server
from app.models import Account, ApiToken, Collection, Group, Item, ItemTag, MealDetail, Tag
from app.tokens import hash_token

# ---------- helpers ----------


def _seed_group(db_session, name, email, token, collection_name="Meal Planner"):
    """A group with one collection and a live API token (plaintext chosen by
    the test; only its hash is stored, like the owner-facing flow)."""
    account = Account(email=email, display_name=email.split("@")[0])
    db_session.add(account)
    db_session.flush()
    group = Group(name=name, owner_account_id=account.id)
    db_session.add(group)
    db_session.flush()
    collection = Collection(group_id=group.id, kind="meal", name=collection_name)
    db_session.add(collection)
    db_session.flush()
    db_session.add(ApiToken(group_id=group.id, token_hash=hash_token(token)))
    db_session.commit()
    return group, collection


def _seed_item(db_session, collection_id, group_id, name, *, type="dinner", tags=(), times_offered=0, times_kept=0):
    item = Item(collection_id=collection_id, name=name, normalized_name=name.casefold())
    db_session.add(item)
    db_session.flush()
    db_session.add(
        MealDetail(item_id=item.id, type=type, ingredients=None, recipe_text=None, source_url=None)
    )
    for tname in tags:
        tag = db_session.scalar(select(Tag).where((Tag.group_id == group_id) & (Tag.name == tname)))
        if tag is None:
            tag = Tag(group_id=group_id, name=tname)
            db_session.add(tag)
            db_session.flush()
        db_session.add(ItemTag(item_id=item.id, tag_id=tag.id))
    item.times_offered = times_offered
    item.times_kept = times_kept
    db_session.commit()
    return item


def _mcp_run(monkeypatch, db_engine, token, case):
    """Run ``case(client)`` (an async coroutine function) against the
    in-memory MCP client. Points the server's DB session factory at
    ``db_engine`` and auths every tool call as ``token`` (headers ``{}`` when
    token is None)."""
    TestingSessionLocal = sessionmaker(
        bind=db_engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    monkeypatch.setattr(mcp_server, "SessionLocal", TestingSessionLocal)
    headers = {"authorization": f"Bearer {token}"} if token else {}
    monkeypatch.setattr(mcp_server, "get_http_headers", lambda *a, **k: headers)

    async def _go():
        async with Client(mcp_server.mcp) as client:
            return await case(client)

    return asyncio.run(_go())


# ---------- happy path ----------


def test_valid_token_lists_collections_adds_lists_and_reports(engine, db_session, monkeypatch):
    _, coll_a = _seed_group(db_session, "Group A", "a@example.com", "token-a", "Dinners")

    async def case_add(client):
        result = await client.call_tool("list_collections", {})
        assert result.data == [{"id": coll_a.id, "name": "Dinners", "kind": "meal"}]

        # Add an item with tags + recipe fields; lands in the DB.
        added = await client.call_tool(
            "add_item",
            {
                "collection_id": coll_a.id,
                "name": "  Baked Salmon  ",
                "type": "dinner",
                "tags": ["fish", "quick"],
                "ingredients": "salmon\n\nlemon\n\n\n",
                "recipe_text": "Bake it.  \n",
                "source_url": "https://example.com/salmon",
            },
        )
        assert added.data["name"] == "Baked Salmon"  # trimmed
        assert added.data["type"] == "dinner"
        assert added.data["tags"] == ["fish", "quick"]
        assert added.data["ingredients"] == "salmon\n\nlemon"  # trailing blank lines stripped
        assert added.data["recipe_text"] == "Bake it."
        assert added.data["source_url"] == "https://example.com/salmon"
        assert added.data["times_kept"] == 0
        assert added.data["archived"] is False
        return added.data["id"]

    item_id = _mcp_run(monkeypatch, engine, "token-a", case_add)

    # Created in A's collection, with the D11 normalized dedupe key.
    item = db_session.get(Item, item_id)
    assert item is not None
    assert item.collection_id == coll_a.id
    assert item.normalized_name == "baked salmon"
    # Tags are group-scoped get-or-create rows.
    assert {t.name for t in db_session.scalars(select(Tag)).all()} == {"fish", "quick"}

    # The item is listed with the full shape.
    async def case_list(client):
        result = await client.call_tool("list_items", {"collection_id": coll_a.id})
        assert result.data == [
            {
                "id": item_id,
                "name": "Baked Salmon",
                "type": "dinner",
                "tags": ["fish", "quick"],
                "ingredients": "salmon\n\nlemon",
                "recipe_text": "Bake it.",
                "source_url": "https://example.com/salmon",
                "times_kept": 0,
                "last_kept_at": None,
                "archived": False,
            }
        ]

    _mcp_run(monkeypatch, engine, "token-a", case_list)

    # Report: aggregate counts only (mark the item as offered/kept first).
    item.times_offered = 10
    item.times_kept = 3
    item.last_kept_at = datetime(2026, 8, 1, 18, 30, tzinfo=UTC)
    db_session.commit()

    async def case_report(client):
        result = await client.call_tool("get_report", {"collection_id": coll_a.id})
        body = result.data
        assert set(body.keys()) == {"by_item", "by_tag", "not_offered_lately"}
        assert body["by_item"] == [
            {
                "name": "Baked Salmon",
                "offered": 10,
                "kept": 3,
                "rejected": 7,
                "reject_rate": 0.7,
                "reject_rate_pct": 70,
                "last_kept": "Aug 01, 2026",
            }
        ]
        # Both tags aggregate over the item's counters.
        by_tag = {r["name"]: r for r in body["by_tag"]}
        assert by_tag["fish"]["offered"] == 10
        assert by_tag["quick"]["offered"] == 10
        assert by_tag["fish"]["reject_rate_pct"] == 70
        assert body["not_offered_lately"][0]["name"] == "Baked Salmon"
        # Aggregate only — no per-person/per-session field anywhere.
        text = str(body).lower()
        for word in ("participant", "choice", "voter", "vote", "yes_count", "no_count"):
            assert word not in text

    _mcp_run(monkeypatch, engine, "token-a", case_report)

    # The token's last_used_at was refreshed by the calls.
    token_row = db_session.scalar(
        select(ApiToken).where(ApiToken.token_hash == hash_token("token-a"))
    )
    assert token_row.last_used_at is not None


# ---------- cross-group scoping (the core invariant) ----------


def test_token_cannot_reach_another_groups_collections_or_items(engine, db_session, monkeypatch):
    group_a, coll_a = _seed_group(db_session, "Group A", "a@example.com", "token-a", "Coll A")
    item_a = _seed_item(db_session, coll_a.id, group_a.id, "A Dish", tags=["tasty"])
    group_b, coll_b = _seed_group(db_session, "Group B", "b@example.com", "token-b", "Coll B")
    item_b = _seed_item(db_session, coll_b.id, group_b.id, "B Secret Dish")

    async def case(client):
        # A's token lists ONLY A's collections.
        result = await client.call_tool("list_collections", {})
        assert [c["id"] for c in result.data] == [coll_a.id]

        # A's token cannot read B's collection's items.
        with pytest.raises(ToolError, match="No such collection"):
            await client.call_tool("list_items", {"collection_id": coll_b.id})
        # Indistinguishable from a nonexistent collection (no existence oracle).
        with pytest.raises(ToolError, match="No such collection"):
            await client.call_tool("list_items", {"collection_id": 999999})

        # A's token cannot create in B's collection.
        with pytest.raises(ToolError, match="No such collection"):
            await client.call_tool(
                "add_item",
                {"collection_id": coll_b.id, "name": "Stowaway", "type": "dinner"},
            )

        # A's token cannot read B's report.
        with pytest.raises(ToolError, match="No such collection"):
            await client.call_tool("get_report", {"collection_id": coll_b.id})

        # A's token cannot update B's item.
        with pytest.raises(ToolError, match="No such item"):
            await client.call_tool("update_item", {"item_id": item_b.id, "name": "Hijacked"})

    _mcp_run(monkeypatch, engine, "token-a", case)

    # No DB change from any of the rejected calls.
    assert db_session.scalar(select(Item).where(Item.normalized_name == "stowaway")) is None
    db_session.refresh(item_b)
    assert item_b.name == "B Secret Dish"
    # A's own item is still reachable for a same-group sanity check.
    assert db_session.get(Item, item_a.id) is not None
    assert db_session.get(Collection, coll_b.id).group_id == group_b.id


def test_cross_group_update_via_group_b_item_untouched(engine, db_session, monkeypatch):
    group_a, coll_a = _seed_group(db_session, "Group A", "a@example.com", "token-a")
    _seed_item(db_session, coll_a.id, group_a.id, "A Item")
    group_b, coll_b = _seed_group(db_session, "Group B", "b@example.com", "token-b")
    item_b = _seed_item(db_session, coll_b.id, group_b.id, "B Item")

    async def case(client):
        with pytest.raises(ToolError, match="No such item"):
            await client.call_tool("update_item", {"item_id": item_b.id, "name": "Renamed by A"})
        with pytest.raises(ToolError, match="No such item"):
            await client.call_tool("update_item", {"item_id": 999999, "name": "Ghost"})

    _mcp_run(monkeypatch, engine, "token-a", case)
    db_session.refresh(item_b)
    assert item_b.name == "B Item"


# ---------- auth ----------


def test_missing_and_invalid_tokens_raise_tool_error(engine, db_session, monkeypatch):
    _, coll = _seed_group(db_session, "Group A", "a@example.com", "token-a")

    async def case_no_token(client):
        with pytest.raises(ToolError, match="Invalid or missing API token"):
            await client.call_tool("list_collections", {})
        with pytest.raises(ToolError, match="Invalid or missing API token"):
            await client.call_tool("list_items", {"collection_id": coll.id})

    # No Authorization header at all.
    _mcp_run(monkeypatch, engine, None, case_no_token)

    async def case_bad_token(client):
        with pytest.raises(ToolError, match="Invalid or missing API token"):
            await client.call_tool("list_collections", {})

    # Unknown token.
    _mcp_run(monkeypatch, engine, "no-such-token", case_bad_token)


# ---------- add_item validation ----------


def test_add_item_blank_name_duplicate_and_bad_type(engine, db_session, monkeypatch):
    _, coll_a = _seed_group(db_session, "Group A", "a@example.com", "token-a")
    _seed_item(db_session, coll_a.id, db_session.scalar(select(Group)).id, "Bacon and Eggs")

    async def case(client):
        with pytest.raises(ToolError, match="Name is required."):
            await client.call_tool(
                "add_item", {"collection_id": coll_a.id, "name": "   ", "type": "dinner"}
            )
        # Normalized-name collision (whitespace-collapsed casefold).
        with pytest.raises(ToolError, match="An item with that name already exists"):
            await client.call_tool(
                "add_item", {"collection_id": coll_a.id, "name": "bacon   and eggs", "type": "dinner"}
            )
        with pytest.raises(ToolError, match="Type must be dinner, lunch, or both."):
            await client.call_tool(
                "add_item", {"collection_id": coll_a.id, "name": "Weird", "type": "brunch"}
            )
        with pytest.raises(ToolError, match="Source URL must start with http:// or https://."):
            await client.call_tool(
                "add_item",
                {
                    "collection_id": coll_a.id,
                    "name": "Fishy",
                    "type": "dinner",
                    "source_url": "javascript:alert(1)",
                },
            )

    _mcp_run(monkeypatch, engine, "token-a", case)

    # Nothing was created by the failed calls.
    names = db_session.scalars(select(Item.name)).all()
    assert names == ["Bacon and Eggs"]


# ---------- update_item ----------


def test_update_item_partial_and_rename_collision(engine, db_session, monkeypatch):
    group_a, coll_a = _seed_group(db_session, "Group A", "a@example.com", "token-a")
    _seed_item(db_session, coll_a.id, group_a.id, "Tacos")
    item = _seed_item(db_session, coll_a.id, group_a.id, "Other", tags=["old"])

    async def case(client):
        # Partial update: rename + type + tags in one call.
        result = await client.call_tool(
            "update_item",
            {"item_id": item.id, "name": "  New Name  ", "type": "both", "tags": ["newtag"]},
        )
        assert result.data["name"] == "New Name"
        assert result.data["type"] == "both"
        assert result.data["tags"] == ["newtag"]
        # Rename collision with an existing item in the same collection.
        with pytest.raises(ToolError, match="An item with that name already exists"):
            await client.call_tool("update_item", {"item_id": item.id, "name": "tacos"})
        # Renaming to its own name is fine (self excluded).
        result = await client.call_tool("update_item", {"item_id": item.id, "name": "New Name"})
        assert result.data["name"] == "New Name"
        # Blank name rejected.
        with pytest.raises(ToolError, match="Name is required."):
            await client.call_tool("update_item", {"item_id": item.id, "name": "   "})

    _mcp_run(monkeypatch, engine, "token-a", case)
    db_session.refresh(item)
    assert item.name == "New Name"
    assert item.normalized_name == "new name"  # recomputed on rename


# ---------- mount + combined lifespan ----------


def test_app_boots_with_mcp_mounted(client):
    """The combined lifespan (migrations + mcp_app.lifespan) runs cleanly
    under the TestClient, and /mcp is mounted and reachable."""
    from starlette.routing import Mount

    from app.main import app

    assert any(isinstance(r, Mount) and r.path == "/mcp" for r in app.routes)
    # The mount is live (not a 404) — the endpoint itself requires Bearer auth,
    # which this plain GET doesn't carry; any non-404 proves routing reaches it.
    resp = client.get("/mcp/")
    assert resp.status_code != 404
    # The rest of the app still serves fine under the combined lifespan.
    assert client.get("/health").status_code == 200
