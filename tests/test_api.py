"""M6a tests (plan §8 M6): per-group API tokens + the /api/v1 JSON API.

Covers the security invariants in order of importance:
1. Token lifecycle — owner mints (plaintext shown once), only the SHA-256 hash
   is stored, regenerate replaces (old token dies), revoke removes, admins get
   403, foreign groups get 404 (no existence oracle).
2. Auth — absent/malformed/bad Bearer → 401; a valid token resolves to exactly
   one group; last_used_at refreshes on use.
3. Cross-group scoping (the core invariant) — a token for group A can never
   read, write, or report on group B's collections/items (404 everywhere).
4. CRUD — create 201 + listed, normalized-name collision 409, blank name 400,
   bad type 400, PATCH partial updates + rename collision 409.
5. Report JSON — same reject-rate numbers as the UI report, aggregate only.
6. Origin — a Bearer-authed POST under /api/v1 with NO Origin header succeeds
   (the API is origin-exempt, unlike browser forms).
"""

import re
from datetime import UTC, datetime

import pytest
from conftest import stamp_session
from sqlalchemy import select

from app.models import (
    Account,
    ApiToken,
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
from app.tokens import hash_token

# Legacy scalar type -> the meal-type set it maps to now ('both' = lunch+dinner).
_TYPE_TO_SET = {
    "dinner": ["dinner"],
    "lunch": ["lunch"],
    "breakfast": ["breakfast"],
    "both": ["lunch", "dinner"],
}

# ---------- helpers ----------


def _make_account(db_session, email, display_name=None):
    account = Account(email=email, display_name=display_name or email.split("@")[0])
    db_session.add(account)
    db_session.commit()
    return account


def _make_group(db_session, owner_email="owner@example.com", name="Test Group"):
    account = _make_account(db_session, owner_email)
    group = Group(name=name, owner_account_id=account.id)
    db_session.add(group)
    db_session.commit()
    return group


def _make_collection(db_session, group_id, name="Meal Planner"):
    collection = Collection(group_id=group_id, kind="meal", name=name)
    db_session.add(collection)
    db_session.commit()
    return collection


def _make_item(
    db_session,
    collection_id,
    group_id,
    name,
    type="dinner",
    tags=(),
    ingredients=None,
    recipe_text=None,
    source_url=None,
):
    """Item with its meal-type set, structured ingredients, an optional
    meal_detail row, and optional group-scoped tags."""
    item = Item(collection_id=collection_id, name=name, normalized_name=name.casefold())
    db_session.add(item)
    db_session.flush()

    for meal_type in _TYPE_TO_SET[type]:
        db_session.add(MealType(item_id=item.id, meal_type=meal_type))

    # Structured ingredients: `ingredients` is legacy free text (one name per
    # line) or None. Normalize + dedupe into group-scoped Ingredient rows.
    if ingredients:
        seen: set[str] = set()
        position = 0
        for raw in ingredients.splitlines():
            iname = re.sub(r"\s+", " ", raw.casefold()).strip()
            if not iname or iname in seen:
                continue
            seen.add(iname)
            ing = db_session.scalar(
                select(Ingredient).where(
                    (Ingredient.group_id == group_id) & (Ingredient.name == iname)
                )
            )
            if ing is None:
                ing = Ingredient(group_id=group_id, name=iname)
                db_session.add(ing)
                db_session.flush()
            db_session.add(
                MealIngredient(item_id=item.id, ingredient_id=ing.id, position=position)
            )
            position += 1

    if recipe_text is not None or source_url is not None:
        db_session.add(
            MealDetail(item_id=item.id, recipe_text=recipe_text, source_url=source_url)
        )

    for tname in tags:
        tag = db_session.scalar(
            select(Tag).where((Tag.group_id == group_id) & (Tag.name == tname))
        )
        if tag is None:
            tag = Tag(group_id=group_id, name=tname)
            db_session.add(tag)
            db_session.flush()
        db_session.add(ItemTag(item_id=item.id, tag_id=tag.id))
    db_session.commit()
    return item


def _login(client, db_session, email):
    account = db_session.scalar(select(Account).where(Account.email == email))
    stamp_session(client, account)


def _generate_token(client, post, db_session, group, owner_email="owner@example.com"):
    """Mint the group's API token via the owner-only UI route and return the
    plaintext (parsed from the one-time reveal box)."""
    _login(client, db_session, owner_email)
    resp = post(f"/groups/{group.id}/api-token")
    assert resp.status_code == 200
    # The one-time reveal renders the token in the first .copy-value element.
    match = re.search(r'class="copy-value">([^<]+)</code>', resp.text)
    assert match is not None, "plaintext reveal box not found in generate response"
    return match.group(1)


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


# ---------- Token lifecycle (owner-only UI) ----------


def test_owner_generates_token_plaintext_shown_once_hash_stored(client, post, db_session, monkeypatch):
    group = _make_group(db_session)
    fixed = "fixed-token-0123456789abcdefghijklmnopqrstuv"
    monkeypatch.setattr("app.routes.groups.generate_token", lambda: fixed)
    _login(client, db_session, "owner@example.com")

    resp = post(f"/groups/{group.id}/api-token")
    assert resp.status_code == 200
    assert fixed in resp.text  # plaintext shown once, in the response

    # DB stores ONLY the SHA-256 hash, never the plaintext.
    row = db_session.scalar(select(ApiToken).where(ApiToken.group_id == group.id))
    assert row is not None
    assert row.token_hash == hash_token(fixed)
    assert row.token_hash != fixed
    stored_hashes = list(db_session.scalars(select(ApiToken.token_hash)).all())
    assert fixed not in stored_hashes

    # The plaintext is NOT re-shown on the next page view.
    resp2 = client.get(f"/groups/{group.id}")
    assert resp2.status_code == 200
    assert fixed not in resp2.text


def test_regenerate_replaces_token_old_token_dies(client, post, db_session, monkeypatch):
    group = _make_group(db_session)
    _login(client, db_session, "owner@example.com")

    monkeypatch.setattr("app.routes.groups.generate_token", lambda: "first-token-aaaa")
    resp = post(f"/groups/{group.id}/api-token")
    assert "first-token-aaaa" in resp.text
    assert client.get("/api/v1/collections", headers=_bearer("first-token-aaaa")).status_code == 200

    monkeypatch.setattr("app.routes.groups.generate_token", lambda: "second-token-bbbb")
    resp = post(f"/groups/{group.id}/api-token")
    assert "second-token-bbbb" in resp.text
    assert "first-token-aaaa" not in resp.text

    # Old token stops working; new token works; exactly one row per group.
    assert client.get("/api/v1/collections", headers=_bearer("first-token-aaaa")).status_code == 401
    assert client.get("/api/v1/collections", headers=_bearer("second-token-bbbb")).status_code == 200
    rows = db_session.scalars(select(ApiToken).where(ApiToken.group_id == group.id)).all()
    assert len(rows) == 1
    assert rows[0].token_hash == hash_token("second-token-bbbb")


def test_revoke_removes_token_and_is_idempotent(client, post, db_session, monkeypatch):
    group = _make_group(db_session)
    monkeypatch.setattr("app.routes.groups.generate_token", lambda: "revoke-me-token")
    _login(client, db_session, "owner@example.com")
    post(f"/groups/{group.id}/api-token")
    assert client.get("/api/v1/collections", headers=_bearer("revoke-me-token")).status_code == 200

    resp = post(f"/groups/{group.id}/api-token/revoke", follow_redirects=False)
    assert resp.status_code == 303
    assert db_session.scalar(select(ApiToken).where(ApiToken.group_id == group.id)) is None
    assert client.get("/api/v1/collections", headers=_bearer("revoke-me-token")).status_code == 401

    # Revoking again with no token present is a no-op redirect.
    assert post(f"/groups/{group.id}/api-token/revoke", follow_redirects=False).status_code == 303


def test_admin_cannot_generate_or_revoke_token(client, post, db_session):
    admin = _make_account(db_session, "admin@example.com")
    group = _make_group(db_session, owner_email="owner@example.com")
    db_session.add(GroupAdmin(group_id=group.id, account_id=admin.id))
    db_session.commit()

    _login(client, db_session, "admin@example.com")
    assert post(f"/groups/{group.id}/api-token").status_code == 403
    assert post(f"/groups/{group.id}/api-token/revoke").status_code == 403
    assert db_session.scalar(select(ApiToken).where(ApiToken.group_id == group.id)) is None


def test_foreign_group_token_routes_404(client, post, db_session):
    """A signed-in account that isn't a member of the group gets 404 — never
    403 — on both token routes (no existence oracle)."""
    _make_group(db_session, owner_email="other@example.com", name="Other Group")
    _make_account(db_session, "owner@example.com")
    _login(client, db_session, "owner@example.com")
    other_group = db_session.scalar(select(Group).where(Group.name == "Other Group"))
    assert post(f"/groups/{other_group.id}/api-token").status_code == 404
    assert post(f"/groups/{other_group.id}/api-token/revoke").status_code == 404
    assert post("/groups/999999/api-token").status_code == 404


# ---------- API auth ----------


def test_api_auth_missing_and_malformed_401(client, db_session):
    _make_group(db_session)
    _make_collection(db_session, db_session.scalar(select(Group)).id)

    resp = client.get("/api/v1/collections")
    assert resp.status_code == 401
    assert resp.json() == {"detail": "API token required"}

    resp = client.get("/api/v1/collections", headers={"Authorization": "Token not-bearer"})
    assert resp.status_code == 401
    assert resp.json() == {"detail": "API token required"}

    resp = client.get("/api/v1/collections", headers={"Authorization": "Bearer"})
    assert resp.status_code == 401
    assert resp.json() == {"detail": "API token required"}


def test_api_auth_bad_token_401(client, db_session):
    _make_group(db_session)
    resp = client.get("/api/v1/collections", headers=_bearer("no-such-token"))
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Invalid API token"}


def test_api_valid_token_resolves_to_its_group_and_last_used_updates(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    token = _generate_token(client, post, db_session, group)

    row = db_session.scalar(select(ApiToken).where(ApiToken.group_id == group.id))
    assert row.last_used_at is None

    resp = client.get("/api/v1/collections", headers=_bearer(token))
    assert resp.status_code == 200
    assert [c["id"] for c in resp.json()["collections"]] == [collection.id]

    db_session.expire_all()
    row = db_session.scalar(select(ApiToken).where(ApiToken.group_id == group.id))
    assert row.last_used_at is not None


# ---------- Cross-group scoping (the core invariant) ----------


def test_token_cannot_reach_another_groups_data(client, post, db_session):
    group_a = _make_group(db_session, owner_email="a@example.com", name="Group A")
    collection_a = _make_collection(db_session, group_a.id, name="Collection A")
    _make_item(db_session, collection_a.id, group_a.id, "A Dish", tags=["tasty"])

    group_b = _make_group(db_session, owner_email="b@example.com", name="Group B")
    collection_b = _make_collection(db_session, group_b.id, name="Collection B")
    item_b = _make_item(db_session, collection_b.id, group_b.id, "B Secret Dish")

    token_a = _generate_token(client, post, db_session, group_a, "a@example.com")
    headers = _bearer(token_a)

    # A's token lists ONLY A's collections.
    resp = client.get("/api/v1/collections", headers=headers)
    ids = [c["id"] for c in resp.json()["collections"]]
    assert ids == [collection_a.id]
    assert collection_b.id not in ids

    # A's token 404s on B's collection items/report (no existence oracle).
    assert client.get(f"/api/v1/collections/{collection_b.id}/items", headers=headers).status_code == 404
    assert client.get(f"/api/v1/collections/{collection_b.id}/report", headers=headers).status_code == 404
    # And on a nonexistent collection id — indistinguishable.
    assert client.get("/api/v1/collections/999999/items", headers=headers).status_code == 404

    # A's token cannot create in B's collection, and nothing lands in the DB.
    resp = client.post(
        f"/api/v1/collections/{collection_b.id}/items",
        json={"name": "Stowaway", "types": ["dinner"]},
        headers=headers,
    )
    assert resp.status_code == 404
    assert db_session.scalar(select(Item).where(Item.normalized_name == "stowaway")) is None

    # A's token cannot PATCH B's item — no change.
    resp = client.patch(f"/api/v1/items/{item_b.id}", json={"name": "Hijacked"}, headers=headers)
    assert resp.status_code == 404
    db_session.refresh(item_b)
    assert item_b.name == "B Secret Dish"

    # A's create with A's token lands in A's collection.
    resp = client.post(
        f"/api/v1/collections/{collection_a.id}/items",
        json={"name": "A New Dish", "types": ["lunch"]},
        headers=headers,
    )
    assert resp.status_code == 201
    created = db_session.scalar(select(Item).where(Item.normalized_name == "a new dish"))
    assert created is not None
    assert created.collection_id == collection_a.id

    # A's token can read A's items; B's names never appear.
    resp = client.get(f"/api/v1/collections/{collection_a.id}/items", headers=headers)
    names = [i["name"] for i in resp.json()["items"]]
    assert "A Dish" in names
    assert "A New Dish" in names
    assert "B Secret Dish" not in names


def test_cross_group_patch_404_leaves_item_untouched_via_own_collection(client, post, db_session):
    """The item-id PATCH route has no collection in the URL, so the guard is
    the item's owning collection must belong to the token's group — an item in
    another group is 404 and never mutated."""
    group_a = _make_group(db_session, owner_email="a@example.com", name="Group A")
    collection_a = _make_collection(db_session, group_a.id)
    group_b = _make_group(db_session, owner_email="b@example.com", name="Group B")
    collection_b = _make_collection(db_session, group_b.id)
    item_b = _make_item(db_session, collection_b.id, group_b.id, "B Item")

    token_a = _generate_token(client, post, db_session, group_a, "a@example.com")
    resp = client.patch(
        f"/api/v1/items/{item_b.id}",
        json={"name": "Renamed by A"},
        headers=_bearer(token_a),
    )
    assert resp.status_code == 404
    db_session.refresh(item_b)
    assert item_b.name == "B Item"
    # A's own item is reachable for a same-group sanity check.
    item_a = _make_item(db_session, collection_a.id, group_a.id, "A Item")
    resp = client.patch(f"/api/v1/items/{item_a.id}", json={"types": ["lunch", "dinner"]}, headers=_bearer(token_a))
    assert resp.status_code == 200
    assert resp.json()["types"] == ["lunch", "dinner"]


# ---------- CRUD ----------


def test_api_create_item_201_and_listed(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    token = _generate_token(client, post, db_session, group)
    headers = _bearer(token)

    resp = client.post(
        f"/api/v1/collections/{collection.id}/items",
        json={
            "name": "  Test Meal  ",
            "types": ["dinner"],
            "tags": ["takeout", "weeknight"],
            "ingredients": ["a", "", "b"],  # blanks dropped, order kept
            "recipe_text": "Do the thing.  \n",
            "source_url": "https://example.com/test",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Test Meal"  # trimmed
    assert body["types"] == ["dinner"]
    assert body["tags"] == ["takeout", "weeknight"]
    assert body["ingredients"] == ["a", "b"]  # blanks dropped, order kept
    assert body["recipe_text"] == "Do the thing."  # trailing whitespace stripped
    assert body["source_url"] == "https://example.com/test"
    assert body["times_offered"] == 0
    assert body["times_kept"] == 0
    assert body["last_kept_at"] is None
    assert body["archived"] is False

    # Appears in the collection listing with the full item shape.
    resp = client.get(f"/api/v1/collections/{collection.id}/items", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert set(items[0].keys()) == {
        "id", "name", "types", "tags", "ingredients", "recipe_text", "source_url",
        "times_offered", "times_kept", "last_kept_at", "archived",
    }
    assert items[0]["id"] == body["id"]

    # Tags are group-scoped get-or-create (a second item reuses the tag rows).
    resp = client.post(
        f"/api/v1/collections/{collection.id}/items",
        json={"name": "Second Meal", "types": ["lunch", "dinner"], "tags": ["takeout"]},
        headers=headers,
    )
    assert resp.status_code == 201
    tag_rows = db_session.scalars(select(Tag).where(Tag.group_id == group.id)).all()
    assert {t.name for t in tag_rows} == {"takeout", "weeknight"}


def test_api_create_name_collision_409(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _make_item(db_session, collection.id, group.id, "Bacon and Eggs")
    token = _generate_token(client, post, db_session, group)

    resp = client.post(
        f"/api/v1/collections/{collection.id}/items",
        json={"name": "bacon   and eggs", "types": ["dinner"]},  # whitespace-collapsed collision
        headers=_bearer(token),
    )
    assert resp.status_code == 409
    assert resp.json() == {"detail": "An item with that name already exists"}


def test_api_create_blank_name_400(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    token = _generate_token(client, post, db_session, group)

    resp = client.post(
        f"/api/v1/collections/{collection.id}/items",
        json={"name": "   ", "types": ["dinner"]},
        headers=_bearer(token),
    )
    assert resp.status_code == 400
    assert resp.json() == {"detail": "Name is required."}


def test_api_create_bad_type_400(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    token = _generate_token(client, post, db_session, group)

    resp = client.post(
        f"/api/v1/collections/{collection.id}/items",
        json={"name": "Weird", "types": ["brunch"]},
        headers=_bearer(token),
    )
    assert resp.status_code == 400
    assert resp.json() == {"detail": "Pick at least one of breakfast, lunch, or dinner."}


def test_api_create_bad_source_url_400(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    token = _generate_token(client, post, db_session, group)

    resp = client.post(
        f"/api/v1/collections/{collection.id}/items",
        json={"name": "Fishy Link", "types": ["dinner"], "source_url": "javascript:alert(1)"},
        headers=_bearer(token),
    )
    assert resp.status_code == 400
    assert resp.json() == {"detail": "Source URL must start with http:// or https://."}


def test_api_patch_partial_updates(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    item = _make_item(
        db_session, collection.id, group.id, "Old Name", type="dinner",
        tags=["takeout"], ingredients="old", recipe_text="old steps",
        source_url="https://example.com/old",
    )
    token = _generate_token(client, post, db_session, group)
    headers = _bearer(token)

    # Rename + type + tags in one PATCH.
    resp = client.patch(
        f"/api/v1/items/{item.id}",
        json={"name": "  New Name  ", "types": ["lunch", "dinner"], "tags": ["newtag"]},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "New Name"
    assert body["types"] == ["lunch", "dinner"]
    assert body["tags"] == ["newtag"]
    db_session.refresh(item)
    assert item.normalized_name == "new name"  # recomputed on rename

    # A second PATCH touches only the detail fields given.
    resp = client.patch(
        f"/api/v1/items/{item.id}",
        json={"ingredients": ["fresh"], "source_url": "https://example.com/new"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["ingredients"] == ["fresh"]
    assert resp.json()["source_url"] == "https://example.com/new"
    assert resp.json()["name"] == "New Name"  # untouched
    db_session.refresh(item)
    assert item.normalized_name == "new name"


def test_api_patch_rename_collision_409_no_change(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _make_item(db_session, collection.id, group.id, "Tacos")
    item = _make_item(db_session, collection.id, group.id, "Other")
    token = _generate_token(client, post, db_session, group)
    headers = _bearer(token)

    resp = client.patch(f"/api/v1/items/{item.id}", json={"name": "tacos"}, headers=headers)
    assert resp.status_code == 409
    assert resp.json() == {"detail": "An item with that name already exists"}
    db_session.refresh(item)
    assert item.name == "Other"  # untouched

    # Renaming to its own name is fine (self excluded).
    resp = client.patch(f"/api/v1/items/{item.id}", json={"name": "Other"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Other"


def test_api_patch_validation_400(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    item = _make_item(db_session, collection.id, group.id, "Steady")
    token = _generate_token(client, post, db_session, group)
    headers = _bearer(token)

    assert client.patch(f"/api/v1/items/{item.id}", json={"name": "   "}, headers=headers).status_code == 400
    assert client.patch(f"/api/v1/items/{item.id}", json={"types": ["brunch"]}, headers=headers).status_code == 400
    db_session.refresh(item)
    assert item.name == "Steady"  # nothing mutated by the failed requests


def test_api_patch_unknown_item_404(client, post, db_session):
    group = _make_group(db_session)
    token = _generate_token(client, post, db_session, group)
    resp = client.patch("/api/v1/items/999999", json={"name": "Ghost"}, headers=_bearer(token))
    assert resp.status_code == 404


# ---------- Report JSON ----------


def test_api_report_matches_numbers_and_is_aggregate_only(client, post, db_session):
    group = _make_group(db_session, owner_email="owner@example.com", name="Household")
    collection = _make_collection(db_session, group.id, name="Dinners")

    tuna = _make_item(db_session, collection.id, group.id, "Tuna Night", tags=["fish", "quick"])
    tuna.times_offered = 10
    tuna.times_kept = 3
    tuna.last_kept_at = datetime(2026, 8, 1, 18, 30, tzinfo=UTC)

    pizza = _make_item(db_session, collection.id, group.id, "Pizza", tags=["quick"])
    pizza.times_offered = 2
    pizza.times_kept = 2
    db_session.commit()

    token = _generate_token(client, post, db_session, group)
    resp = client.get(f"/api/v1/collections/{collection.id}/report", headers=_bearer(token))
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"by_item", "by_tag", "not_offered_lately"}

    # By item: Tuna 7/10 rejected → 70%; Pizza 0/2 → 0%, highest rate first.
    by_item = {r["name"]: r for r in body["by_item"]}
    assert [r["name"] for r in body["by_item"]] == ["Tuna Night", "Pizza"]
    assert by_item["Tuna Night"]["offered"] == 10
    assert by_item["Tuna Night"]["kept"] == 3
    assert by_item["Tuna Night"]["rejected"] == 7
    assert by_item["Tuna Night"]["reject_rate"] == 0.7
    assert by_item["Tuna Night"]["reject_rate_pct"] == 70
    assert by_item["Tuna Night"]["last_kept"] == "Aug 01, 2026"
    assert by_item["Pizza"]["reject_rate"] == 0.0
    assert by_item["Pizza"]["reject_rate_pct"] == 0

    # By tag: fish = Tuna only → 7/10; quick = Tuna + Pizza → 7/12.
    by_tag = {r["name"]: r for r in body["by_tag"]}
    assert by_tag["fish"]["offered"] == 10
    assert by_tag["fish"]["kept"] == 3
    assert by_tag["quick"]["offered"] == 12
    assert by_tag["quick"]["kept"] == 5
    assert by_tag["quick"]["reject_rate"] == pytest.approx(7 / 12)

    # Not offered lately: non-archived, lowest times_offered first.
    assert [r["name"] for r in body["not_offered_lately"]] == ["Pizza", "Tuna Night"]
    assert body["not_offered_lately"][0]["times_offered"] == 2

    # Aggregate only — no per-person or per-session field anywhere in the JSON.
    text = resp.text.lower()
    for word in ("participant", "choice", "voter", "account", "vote", "yes_count", "no_count"):
        assert word not in text


# ---------- Origin exemption ----------


def test_api_post_without_origin_header_succeeds(client, post, db_session):
    """Bearer-authed POSTs under /api/v1 need no Origin header — unlike the
    browser forms, which the origin middleware fail-closes."""
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    token = _generate_token(client, post, db_session, group)

    resp = client.post(
        f"/api/v1/collections/{collection.id}/items",
        json={"name": "No Origin Meal", "types": ["dinner"]},
        headers=_bearer(token),
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "No Origin Meal"
    item = db_session.scalar(select(Item).where(Item.normalized_name == "no origin meal"))
    assert item is not None
