"""Collection-scoped item library routes (M2b, T2.1–T2.2; M2c part 2):
browse/search/filter, create/edit, admin gating, archive/unarchive, type
cycle, recipe view, the collections hub, and the legacy /library redirect.

Every test that used to hit /library now uses /collections/{id} (browse) and
/collections/{id}/items/{item_id} (detail/edit) — the multi-group dead end
found in the 2026-08-29 review, where an account in two groups could never
reach the second group's library, is what this URL scheme closes.
"""

from conftest import stamp_session
from sqlalchemy import func, select

from app.models import Account, Collection, Group, Item, ItemTag, MealDetail, Tag


def _get_or_make_account(db_session, email="admin@example.com", display_name="Admin"):
    """Get-or-create so `_make_group` and `_make_account` can be called in either
    order and still refer to the same account row (they share the same default
    email) — every library route now requires the caller to own the group whose
    collection it's touching, so tests need the logged-in account to actually be
    the group's owner, not a separate look-alike account."""
    account = db_session.scalar(select(Account).where(Account.email == email))
    if account is not None:
        return account
    account = Account(email=email, display_name=display_name)
    db_session.add(account)
    db_session.commit()
    return account


def _make_group(db_session, owner_email="admin@example.com", group_name="Test Group"):
    """Create a group owned by the (possibly just-created) account at owner_email."""
    account = _get_or_make_account(db_session, email=owner_email)
    group = Group(name=group_name, owner_account_id=account.id)
    db_session.add(group)
    db_session.commit()
    return group


def _make_collection(db_session, group_id, name="Meal Planner"):
    """Create a meal collection for a group."""
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
    archived=False,
):
    """Create an item with a meal_detail row and optional tags."""
    item = Item(
        collection_id=collection_id,
        name=name,
        normalized_name=name.casefold(),
        description=None,
    )
    db_session.add(item)
    db_session.flush()

    detail = MealDetail(
        item_id=item.id,
        type=type,
        ingredients=ingredients,
        recipe_text=recipe_text,
        source_url=source_url,
    )
    db_session.add(detail)

    for tname in tags:
        tag = db_session.scalar(select(Tag).where((Tag.group_id == group_id) & (Tag.name == tname)))
        if tag is None:
            tag = Tag(group_id=group_id, name=tname)
            db_session.add(tag)
            db_session.flush()
        db_session.add(ItemTag(item_id=item.id, tag_id=tag.id))

    if archived:
        item.archived_at = func.now()

    db_session.commit()
    return item


def _make_account(db_session, email="admin@example.com", display_name="Admin"):
    return _get_or_make_account(db_session, email=email, display_name=display_name)


def _login(client, db_session, email="admin@example.com"):
    """Authenticate the TestClient session as the account with `email`."""
    account = db_session.scalar(select(Account).where(Account.email == email))
    stamp_session(client, account)


def _tags_of(db_session, item_id):
    return set(
        db_session.scalars(
            select(Tag.name)
            .join(ItemTag, ItemTag.tag_id == Tag.id)
            .where(ItemTag.item_id == item_id)
        ).all()
    )


# ---------- Legacy /library redirect ----------


def test_legacy_library_redirects_to_first_meal_collection(client, post, db_session):
    """GET /library is a legacy redirect (plan §9): 303 to /collections/{id}
    of the account's FIRST meal collection (smallest id), not a page of its
    own."""
    group = _make_group(db_session)
    first = _make_collection(db_session, group.id, name="First")
    _make_collection(db_session, group.id, name="Second")
    _login(client, db_session)
    resp = client.get("/library", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/collections/{first.id}"


def test_legacy_library_redirects_to_hub_without_collection(client, post, db_session):
    """An account with no meal collection is 303'd to the collections hub
    instead of an empty library page."""
    _make_group(db_session)  # creates the admin@example.com account, no collection
    _login(client, db_session)
    resp = client.get("/library", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/collections"


# ---------- Collections hub ----------


def test_collections_hub_shows_both_groups_collections(client, post, db_session):
    """Regression (2026-08-29 review, multi-group dead end): an account owning
    two groups, each with a meal collection, sees BOTH on /collections — the
    old /library page could only ever reach the account's first collection."""
    group_a = _make_group(db_session, group_name="House A")
    collection_a = _make_collection(db_session, group_a.id, name="Meal Planner A")
    _make_item(db_session, collection_a.id, group_a.id, "A Tacos")
    _make_item(db_session, collection_a.id, group_a.id, "A Pizza", archived=True)

    group_b = _make_group(db_session, group_name="House B")
    collection_b = _make_collection(db_session, group_b.id, name="Meal Planner B")
    _make_item(db_session, collection_b.id, group_b.id, "B Burgers")
    _make_item(db_session, collection_b.id, group_b.id, "B Salad")

    _login(client, db_session)
    resp = client.get("/collections")
    assert resp.status_code == 200
    assert "House A" in resp.text
    assert "House B" in resp.text
    assert f"/collections/{collection_a.id}" in resp.text
    assert f"/collections/{collection_b.id}" in resp.text
    # Per-collection active-item counts; archived items don't count.
    assert "1 active items" in resp.text
    assert "2 active items" in resp.text


def test_collections_hub_keeps_same_named_groups_separate(client, post, db_session):
    """Regression (review finding): two distinct groups with the same name must
    render as TWO separate group sections on /collections — the grouping key is
    group id, not the display name, so the same-named groups don't merge under
    one header."""
    group_1 = _make_group(db_session, group_name="Family")
    collection_1 = _make_collection(db_session, group_1.id, name="Dinners")
    _make_item(db_session, collection_1.id, group_1.id, "Pasta Night")

    # Group 1 gets a second collection whose name sorts AFTER group 2's
    # collection — without group id in the ORDER BY, the rows interleave
    # (Dinners, Weeknight Eats, Zucchini Nights) and id-keyed grouping would
    # split group 1 into two sections around group 2's.
    _make_collection(db_session, group_1.id, name="Zucchini Nights")

    group_2 = _make_group(db_session, group_name="Family")
    collection_2 = _make_collection(db_session, group_2.id, name="Weeknight Eats")
    _make_item(db_session, collection_2.id, group_2.id, "Curry Night")

    assert group_1.id != group_2.id  # sanity: genuinely distinct groups

    _login(client, db_session)
    resp = client.get("/collections")
    assert resp.status_code == 200
    # Both collections listed distinctly (each links to its own collection).
    assert f"/collections/{collection_1.id}" in resp.text
    assert f"/collections/{collection_2.id}" in resp.text
    assert "Dinners" in resp.text
    assert "Weeknight Eats" in resp.text
    # Two separate "Family" section headers — not one merged group.
    assert resp.text.count(">Family</div>") == 2


def test_collection_page_shows_only_that_collections_items(client, post, db_session):
    """Each /collections/{id} page shows only that collection's items — the
    second group's library is reachable (the multi-group dead end from the
    2026-08-29 review) and never mixes the two collections."""
    group_a = _make_group(db_session, group_name="House A")
    collection_a = _make_collection(db_session, group_a.id)
    _make_item(db_session, collection_a.id, group_a.id, "A Tacos")

    group_b = _make_group(db_session, group_name="House B")
    collection_b = _make_collection(db_session, group_b.id)
    _make_item(db_session, collection_b.id, group_b.id, "B Burgers")

    _login(client, db_session)
    resp = client.get(f"/collections/{collection_a.id}")
    assert resp.status_code == 200
    assert "A Tacos" in resp.text
    assert "B Burgers" not in resp.text

    resp = client.get(f"/collections/{collection_b.id}")
    assert resp.status_code == 200
    assert "B Burgers" in resp.text
    assert "A Tacos" not in resp.text


def test_collections_hub_requires_signin(client):
    """The hub goes through require_account: a signed-out visitor gets the
    standard 401 → /login redirect, same as other account pages."""
    resp = client.get("/collections", headers={"accept": "text/html"}, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login?next=%2Fcollections"


def test_browse_another_groups_collection_404(client, post, db_session):
    """Another group's collection id → 404 on the browse page, never 403 —
    indistinguishable from a collection that doesn't exist."""
    other_group = _make_group(db_session, owner_email="other-owner@example.com", group_name="Other Household")
    other_collection = _make_collection(db_session, other_group.id)
    _make_item(db_session, other_collection.id, other_group.id, "Their Secret Casserole")

    _make_group(db_session)  # the admin@example.com account/group under test
    _login(client, db_session)
    assert client.get(f"/collections/{other_collection.id}").status_code == 404
    # And a collection id that doesn't exist at all.
    assert client.get("/collections/999999").status_code == 404


# ---------- Browse / search / filter (signed-in, own collection) ----------


def test_library_page_lists_items(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _make_item(db_session, collection.id, group.id, "Taco Tuesday", tags=["takeout"])
    _make_item(db_session, collection.id, group.id, "Pancakes", type="both")
    _login(client, db_session)
    resp = client.get(f"/collections/{collection.id}")
    assert resp.status_code == 200
    assert "Meal Library" in resp.text
    assert "Taco Tuesday" in resp.text
    assert "Pancakes" in resp.text
    assert "2 active · 0 archived." in resp.text
    # Links/forms are collection-scoped, not /library.
    assert f"/collections/{collection.id}/items/new" in resp.text
    assert f"/collections/{collection.id}/items/" in resp.text


def test_library_orders_by_normalized_name_case_insensitively(client, post, db_session):
    """SQLite's BINARY collation would sort "Ziti" before "bacon and eggs"
    when ordering by the raw name; the library orders by the casefolded
    normalized_name so the list reads naturally regardless of original
    capitalization (OSCAR review fix)."""
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _make_item(db_session, collection.id, group.id, "Ziti", type="dinner")
    _make_item(db_session, collection.id, group.id, "bacon and eggs", type="both")
    _make_item(db_session, collection.id, group.id, "Apple pie", type="both")
    _login(client, db_session)
    resp = client.get(f"/collections/{collection.id}")
    assert resp.status_code == 200
    assert resp.text.index("Apple pie") < resp.text.index("bacon and eggs") < resp.text.index("Ziti")


def test_library_search_filters(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _make_item(db_session, collection.id, group.id, "taco soup", type="both")
    _make_item(db_session, collection.id, group.id, "bacon and eggs", type="both")
    _login(client, db_session)
    resp = client.get(f"/collections/{collection.id}", params={"q": "taco"})
    assert "taco soup" in resp.text
    assert "bacon and eggs" not in resp.text
    # Case-insensitive on name and normalized_name.
    resp = client.get(f"/collections/{collection.id}", params={"q": "BACON"})
    assert "bacon and eggs" in resp.text
    assert "taco soup" not in resp.text


def test_library_type_filter(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _make_item(db_session, collection.id, group.id, "Steak", type="dinner")
    _make_item(db_session, collection.id, group.id, "Quesadillas", type="both")
    _make_item(db_session, collection.id, group.id, "Salad bar", type="lunch")
    _login(client, db_session)
    resp = client.get(f"/collections/{collection.id}", params={"type": "both"})
    assert "Quesadillas" in resp.text
    assert "Steak" not in resp.text
    assert "Salad bar" not in resp.text
    resp = client.get(f"/collections/{collection.id}", params={"type": "lunch"})
    assert "Salad bar" in resp.text
    assert "Steak" not in resp.text


def test_library_tag_filter_or_semantics(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _make_item(db_session, collection.id, group.id, "Whataburger", tags=["takeout"])
    _make_item(db_session, collection.id, group.id, "Pizza Rolls", tags=["takeout", "snack"])
    _make_item(db_session, collection.id, group.id, "Homemade bread", tags=["snack"])
    _login(client, db_session)
    resp = client.get(f"/collections/{collection.id}", params={"tags": "takeout"})
    assert "Whataburger" in resp.text
    assert "Pizza Rolls" in resp.text
    assert "Homemade bread" not in resp.text
    # OR: either tag matches.
    resp = client.get(f"/collections/{collection.id}", params={"tags": "takeout,snack"})
    assert "Whataburger" in resp.text
    assert "Pizza Rolls" in resp.text
    assert "Homemade bread" in resp.text


def test_archived_hidden_by_default_visible_with_status(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _make_item(db_session, collection.id, group.id, "Old pasta", archived=True)
    _make_item(db_session, collection.id, group.id, "Fresh tacos")
    _login(client, db_session)
    resp = client.get(f"/collections/{collection.id}")
    assert "Fresh tacos" in resp.text
    assert "Old pasta" not in resp.text
    assert "1 active · 1 archived." in resp.text
    resp = client.get(f"/collections/{collection.id}", params={"status": "all"})
    assert "Old pasta" in resp.text
    resp = client.get(f"/collections/{collection.id}", params={"status": "archived"})
    assert "Old pasta" in resp.text
    assert "Fresh tacos" not in resp.text


def test_library_kept_label_and_recipe_link(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    item = _make_item(db_session, collection.id, group.id, "Brisket", recipe_text="Slow cook it.")
    item.times_kept = 3
    db_session.commit()
    _login(client, db_session)
    resp = client.get(f"/collections/{collection.id}")
    assert "Kept 3×" in resp.text
    assert "Recipe →" in resp.text


def test_library_page_renders_item_with_no_meal_detail(client, post, db_session):
    """Regression: an Item with no meal_detail row (the schema allows it --
    meal_detail is an optional 1:1 extension) must not 500 the whole library
    page. Previously `item_details.get(item.id, MealDetail())` returned None
    (dict.get's default never fires when the key IS present with value None),
    so `.type` raised AttributeError for every viewer of the collection."""
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    detail_less = Item(
        collection_id=collection.id, name="No Detail Yet", normalized_name="no detail yet"
    )
    db_session.add(detail_less)
    db_session.commit()
    _login(client, db_session)
    resp = client.get(f"/collections/{collection.id}")
    assert resp.status_code == 200
    assert "No Detail Yet" in resp.text


# ---------- Recipe view (signed-in accounts, own collection only) ----------


def test_recipe_view_renders(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    item = _make_item(
        db_session,
        collection.id,
        group.id,
        "Chili",
        type="both",
        tags=["spicy"],
        ingredients="1 lb beef\n2 cans beans\n\n1 onion",
        recipe_text="Brown the beef. Simmer an hour.",
        source_url="https://example.com/chili",
    )
    _login(client, db_session)
    resp = client.get(f"/collections/{collection.id}/items/{item.id}")
    assert resp.status_code == 200
    assert "Chili" in resp.text
    assert "1 lb beef" in resp.text
    assert "2 cans beans" in resp.text
    assert "1 onion" in resp.text
    assert "Brown the beef. Simmer an hour." in resp.text
    assert "Originally sourced from this recipe ↗" in resp.text
    assert "Kept 0×" not in resp.text  # no kept line when times_kept == 0


def test_recipe_view_empty_state(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    item = _make_item(db_session, collection.id, group.id, "Mystery night")
    _login(client, db_session)
    resp = client.get(f"/collections/{collection.id}/items/{item.id}")
    assert resp.status_code == 200
    assert "No recipe saved yet" in resp.text
    assert "A clean full-page cooking view" in resp.text


def test_recipe_view_unknown_404(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _login(client, db_session)
    assert client.get(f"/collections/{collection.id}/items/999999").status_code == 404


def test_recipe_view_another_groups_collection_404(client, post, db_session):
    """Another group's collection id → 404 on the recipe route — the
    collection guard fires before the item is ever looked up."""
    other_group = _make_group(db_session, owner_email="other-owner@example.com")
    other_collection = _make_collection(db_session, other_group.id)
    other_item = _make_item(db_session, other_collection.id, other_group.id, "Their secret recipe")
    _make_group(db_session)  # the admin@example.com account/group under test
    _login(client, db_session)
    resp = client.get(f"/collections/{other_collection.id}/items/{other_item.id}")
    assert resp.status_code == 404


def test_recipe_view_another_groups_item_404(client, post, db_session):
    """Another group's item id under one's OWN collection URL is 404, not 403
    — the item must belong to the collection in the URL, so it is
    indistinguishable from an item that doesn't exist at all."""
    other_item = _other_groups_item(db_session)
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _login(client, db_session)
    assert client.get(f"/collections/{collection.id}/items/{other_item.id}").status_code == 404


def test_recipe_view_mismatched_collection_404(client, post, db_session):
    """An account's own item requested under a DIFFERENT collection it also
    owns → 404: the item must belong to the exact collection in the URL."""
    group = _make_group(db_session)
    collection_a = _make_collection(db_session, group.id, name="A")
    collection_b = _make_collection(db_session, group.id, name="B")
    item_a = _make_item(db_session, collection_a.id, group.id, "A Tacos")
    _login(client, db_session)
    resp = client.get(f"/collections/{collection_b.id}/items/{item_a.id}")
    assert resp.status_code == 404


# ---------- Admin gating ----------


def test_admin_gating(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _make_item(db_session, collection.id, group.id, "Steak")
    # No session at all: 401 (not signed in) on every route, including plain browsing.
    assert post(f"/collections/{collection.id}/items", data={"name": "X", "type": "dinner"}).status_code == 401
    assert client.get(f"/collections/{collection.id}/items/new").status_code == 401
    assert client.get(f"/collections/{collection.id}/items/1/edit").status_code == 401
    assert client.get(f"/collections/{collection.id}").status_code == 401
    assert client.get("/library").status_code == 401
    assert client.get("/collections").status_code == 401


# ---------- Create ----------


def test_create_item(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _make_account(db_session)
    _login(client, db_session)
    resp = post(
        f"/collections/{collection.id}/items",
        data={
            "name": "Test Meal",
            "type": "dinner",
            "tags": ["takeout", "weeknight"],
            "ingredients": "a\n\nb\n\n\n",  # trailing blank lines stripped
            "instructions": "Do the thing.  \n",
            "source_url": "https://example.com/test",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    item = db_session.scalar(select(Item).where(Item.normalized_name == "test meal"))
    assert item is not None
    assert item.collection_id == collection.id
    detail = db_session.get(MealDetail, item.id)
    assert detail.type == "dinner"
    assert detail.ingredients == "a\n\nb"  # internal blank line kept
    assert detail.recipe_text == "Do the thing."  # trailing whitespace stripped
    assert detail.source_url == "https://example.com/test"
    assert resp.headers["location"] == f"/collections/{collection.id}/items/{item.id}/edit"
    # Tags incl. the brand-new "weeknight" were created and linked.
    assert _tags_of(db_session, item.id) == {"takeout", "weeknight"}


def test_create_item_without_tags_or_recipe(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _make_account(db_session)
    _login(client, db_session)
    resp = post(
        f"/collections/{collection.id}/items",
        data={"name": "Bare meal", "type": "lunch"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    item = db_session.scalar(select(Item).where(Item.normalized_name == "bare meal"))
    assert item is not None
    detail = db_session.get(MealDetail, item.id)
    assert detail.ingredients is None
    assert detail.recipe_text is None
    assert _tags_of(db_session, item.id) == set()


def test_create_lands_in_url_collection(client, post, db_session):
    """Regression (2026-08-29 review, multi-group dead end): a create POST to
    collection B's URL must land the item in B. The old create path bound new
    items to the account's first meal collection no matter which library page
    the form came from — an account in two groups could add to group A but
    never to group B."""
    group_a = _make_group(db_session, group_name="House A")
    collection_a = _make_collection(db_session, group_a.id, name="Meal Planner A")
    _make_item(db_session, collection_a.id, group_a.id, "A Item")

    group_b = _make_group(db_session, group_name="House B")
    collection_b = _make_collection(db_session, group_b.id, name="Meal Planner B")
    _login(client, db_session)

    resp = post(
        f"/collections/{collection_b.id}/items",
        data={"name": "B Item", "type": "dinner"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    item = db_session.scalar(select(Item).where(Item.normalized_name == "b item"))
    assert item is not None
    assert item.collection_id == collection_b.id  # landed in B, not A
    assert resp.headers["location"] == f"/collections/{collection_b.id}/items/{item.id}/edit"


def test_create_duplicate_normalized_name_400(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _make_account(db_session)
    _login(client, db_session)
    _make_item(db_session, collection.id, group.id, "Bacon and Eggs")
    resp = post(
        f"/collections/{collection.id}/items",
        data={"name": "bacon   and eggs", "type": "dinner"},
    )  # whitespace-collapsed collision
    assert resp.status_code == 400
    assert "An item with that name already exists" in resp.text


def test_create_invalid_type_400(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _make_account(db_session)
    _login(client, db_session)
    resp = post(f"/collections/{collection.id}/items", data={"name": "Weird", "type": "brunch"})
    assert resp.status_code == 400


def test_create_empty_name_400(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _make_account(db_session)
    _login(client, db_session)
    resp = post(f"/collections/{collection.id}/items", data={"name": "   ", "type": "dinner"})
    assert resp.status_code == 400


def test_create_another_groups_collection_404(client, post, db_session):
    """Creating against another group's collection URL is 404 with no DB
    change — the item can only land in a collection the account owns/admins."""
    other_group = _make_group(db_session, owner_email="other-owner@example.com", group_name="Other Household")
    other_collection = _make_collection(db_session, other_group.id)
    _make_group(db_session)  # the admin@example.com account/group under test
    _login(client, db_session)
    resp = post(
        f"/collections/{other_collection.id}/items",
        data={"name": "Stowaway", "type": "dinner"},
    )
    assert resp.status_code == 404
    assert db_session.scalar(select(Item).where(Item.normalized_name == "stowaway")) is None


# ---------- Update ----------


def test_update_item_rename_and_type(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _make_account(db_session)
    _login(client, db_session)
    item = _make_item(db_session, collection.id, group.id, "Old Name", type="dinner", tags=["takeout"])
    resp = post(
        f"/collections/{collection.id}/items/{item.id}",
        data={"name": "New Name", "type": "both", "tags": ["takeout", "newtag"]},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/collections/{collection.id}/items/{item.id}/edit"
    db_session.refresh(item)
    assert item.name == "New Name"
    assert item.normalized_name == "new name"  # recomputed on rename
    detail = db_session.get(MealDetail, item.id)
    assert detail.type == "both"
    assert _tags_of(db_session, item.id) == {"takeout", "newtag"}


def test_update_rename_collision_400(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _make_account(db_session)
    _login(client, db_session)
    _make_item(db_session, collection.id, group.id, "Tacos")
    item = _make_item(db_session, collection.id, group.id, "Other")
    resp = post(
        f"/collections/{collection.id}/items/{item.id}",
        data={"name": "Tacos", "type": "dinner"},
    )
    assert resp.status_code == 400
    assert "An item with that name already exists" in resp.text
    # Renaming an item to its own name is fine (self excluded).
    resp = post(
        f"/collections/{collection.id}/items/{item.id}",
        data={"name": "Other", "type": "dinner"},
        follow_redirects=False,
    )
    assert resp.status_code == 303


# ---------- Post-mutation redirect targets ----------


def test_archive_redirects_to_collection(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    item = _make_item(db_session, collection.id, group.id, "Old pasta")
    _login(client, db_session)
    resp = post(
        f"/collections/{collection.id}/items/{item.id}/archive",
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/collections/{collection.id}"


def test_cycle_type_redirects_to_collection(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    item = _make_item(db_session, collection.id, group.id, "Steak", type="dinner")
    _login(client, db_session)
    resp = post(
        f"/collections/{collection.id}/items/{item.id}/cycle-type",
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/collections/{collection.id}"
    detail = db_session.get(MealDetail, item.id)
    assert detail.type == "lunch"  # dinner → lunch


# ---------- Cross-tenant mutation guards ----------
# Every item-addressed mutation route must 404 (never touch the item) when
# given another group's collection id or another group's item id under one's
# own collection URL -- these pin the protection the collection guard +
# membership check provide in code, so a future refactor that drops a guard on
# one route fails a test instead of shipping a silent cross-tenant write.


def _other_groups_item(db_session):
    other_group = _make_group(db_session, owner_email="other-owner@example.com", group_name="Other Household")
    other_collection = _make_collection(db_session, other_group.id)
    return _make_item(db_session, other_collection.id, other_group.id, "Their Secret Recipe")


def test_update_another_groups_collection_404(client, post, db_session):
    """Updating under another group's collection URL is 404 and never touches
    the item — even with the item's own real id in the URL."""
    other_item = _other_groups_item(db_session)
    other_collection_id = other_item.collection_id
    _make_group(db_session)  # admin@example.com's own group, so they're a real signed-in account
    _login(client, db_session)
    resp = post(
        f"/collections/{other_collection_id}/items/{other_item.id}",
        data={"name": "Hijacked", "type": "dinner"},
    )
    assert resp.status_code == 404
    db_session.refresh(other_item)
    assert other_item.name == "Their Secret Recipe"  # untouched


def test_update_another_groups_item_404(client, post, db_session):
    """Another group's item id under one's own collection URL → 404, no write."""
    other_item = _other_groups_item(db_session)
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _login(client, db_session)
    resp = post(
        f"/collections/{collection.id}/items/{other_item.id}",
        data={"name": "Hijacked", "type": "dinner"},
    )
    assert resp.status_code == 404
    db_session.refresh(other_item)
    assert other_item.name == "Their Secret Recipe"  # untouched


def test_update_mismatched_collection_404(client, post, db_session):
    """An account's own item under a DIFFERENT collection it also owns → 404,
    no write: the item must belong to the exact collection in the URL."""
    group = _make_group(db_session)
    collection_a = _make_collection(db_session, group.id, name="A")
    collection_b = _make_collection(db_session, group.id, name="B")
    item_a = _make_item(db_session, collection_a.id, group.id, "A Tacos")
    _login(client, db_session)
    resp = post(
        f"/collections/{collection_b.id}/items/{item_a.id}",
        data={"name": "Renamed", "type": "dinner"},
    )
    assert resp.status_code == 404
    db_session.refresh(item_a)
    assert item_a.name == "A Tacos"  # untouched


def test_archive_another_groups_collection_404(client, post, db_session):
    other_item = _other_groups_item(db_session)
    _make_group(db_session)
    _login(client, db_session)
    resp = post(
        f"/collections/{other_item.collection_id}/items/{other_item.id}/archive",
        follow_redirects=False,
    )
    assert resp.status_code == 404
    db_session.refresh(other_item)
    assert other_item.archived_at is None  # untouched


def test_archive_another_groups_item_404(client, post, db_session):
    other_item = _other_groups_item(db_session)
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _login(client, db_session)
    resp = post(
        f"/collections/{collection.id}/items/{other_item.id}/archive",
        follow_redirects=False,
    )
    assert resp.status_code == 404
    db_session.refresh(other_item)
    assert other_item.archived_at is None  # untouched


def test_archive_mismatched_collection_404(client, post, db_session):
    group = _make_group(db_session)
    collection_a = _make_collection(db_session, group.id, name="A")
    collection_b = _make_collection(db_session, group.id, name="B")
    item_a = _make_item(db_session, collection_a.id, group.id, "A Tacos")
    _login(client, db_session)
    resp = post(
        f"/collections/{collection_b.id}/items/{item_a.id}/archive",
        follow_redirects=False,
    )
    assert resp.status_code == 404
    db_session.refresh(item_a)
    assert item_a.archived_at is None  # untouched


def test_unarchive_another_groups_item_404(client, post, db_session):
    other_group = _make_group(db_session, owner_email="other-owner@example.com", group_name="Other Household")
    other_collection = _make_collection(db_session, other_group.id)
    other_item = _make_item(db_session, other_collection.id, other_group.id, "Their Archived Recipe", archived=True)
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _login(client, db_session)
    resp = post(
        f"/collections/{collection.id}/items/{other_item.id}/unarchive",
        follow_redirects=False,
    )
    assert resp.status_code == 404
    db_session.refresh(other_item)
    assert other_item.archived_at is not None  # still archived, untouched


def test_cycle_type_another_groups_item_404(client, post, db_session):
    other_item = _other_groups_item(db_session)
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _login(client, db_session)
    resp = post(
        f"/collections/{collection.id}/items/{other_item.id}/cycle-type",
        follow_redirects=False,
    )
    assert resp.status_code == 404
    detail = db_session.get(MealDetail, other_item.id)
    assert detail.type == "dinner"  # unchanged (default from _make_item)
