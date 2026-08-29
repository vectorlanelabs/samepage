"""Meal library routes (M2b, T2.1–T2.2): browse/search/filter, create/edit,
admin gating, archive/unarchive, type cycle, recipe view."""

from sqlalchemy import func, select

from app.credentials import hash_password
from app.models import Account, Collection, Group, Item, ItemTag, MealDetail, Tag


def _get_or_make_account(db_session, email="admin@example.com", password="testpass123", display_name="Admin"):
    """Get-or-create so `_make_group` and `_make_account` can be called in either
    order and still refer to the same account row (they share the same default
    email) — every library route now requires the caller to own the group whose
    collection it's touching, so tests need the logged-in account to actually be
    the group's owner, not a separate look-alike account."""
    account = db_session.scalar(select(Account).where(Account.email == email))
    if account is not None:
        return account
    account = Account(email=email, password_hash=hash_password(password), display_name=display_name)
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
        is_active=True,
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


def _make_account(db_session, email="admin@example.com", password="testpass123", display_name="Admin"):
    return _get_or_make_account(db_session, email=email, password=password, display_name=display_name)


def _login(post, email="admin@example.com", password="testpass123"):
    post("/login", data={"email": email, "password": password})


def _tags_of(db_session, item_id):
    return set(
        db_session.scalars(
            select(Tag.name)
            .join(ItemTag, ItemTag.tag_id == Tag.id)
            .where(ItemTag.item_id == item_id)
        ).all()
    )


# ---------- Browse / search / filter (public) ----------


def test_library_page_lists_items(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _make_item(db_session, collection.id, group.id, "Taco Tuesday", tags=["takeout"])
    _make_item(db_session, collection.id, group.id, "Pancakes", type="both")
    _login(post)
    resp = client.get("/library")
    assert resp.status_code == 200
    assert "Meal Library" in resp.text
    assert "Taco Tuesday" in resp.text
    assert "Pancakes" in resp.text
    assert "2 active · 0 archived." in resp.text


def test_library_search_filters(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _make_item(db_session, collection.id, group.id, "taco soup", type="both")
    _make_item(db_session, collection.id, group.id, "bacon and eggs", type="both")
    _login(post)
    resp = client.get("/library", params={"q": "taco"})
    assert "taco soup" in resp.text
    assert "bacon and eggs" not in resp.text
    # Case-insensitive on name and normalized_name.
    resp = client.get("/library", params={"q": "BACON"})
    assert "bacon and eggs" in resp.text
    assert "taco soup" not in resp.text


def test_library_type_filter(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _make_item(db_session, collection.id, group.id, "Steak", type="dinner")
    _make_item(db_session, collection.id, group.id, "Quesadillas", type="both")
    _make_item(db_session, collection.id, group.id, "Salad bar", type="lunch")
    _login(post)
    resp = client.get("/library", params={"type": "both"})
    assert "Quesadillas" in resp.text
    assert "Steak" not in resp.text
    assert "Salad bar" not in resp.text
    resp = client.get("/library", params={"type": "lunch"})
    assert "Salad bar" in resp.text
    assert "Steak" not in resp.text


def test_library_tag_filter_or_semantics(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _make_item(db_session, collection.id, group.id, "Whataburger", tags=["takeout"])
    _make_item(db_session, collection.id, group.id, "Pizza Rolls", tags=["takeout", "snack"])
    _make_item(db_session, collection.id, group.id, "Homemade bread", tags=["snack"])
    _login(post)
    resp = client.get("/library", params={"tags": "takeout"})
    assert "Whataburger" in resp.text
    assert "Pizza Rolls" in resp.text
    assert "Homemade bread" not in resp.text
    # OR: either tag matches.
    resp = client.get("/library", params={"tags": "takeout,snack"})
    assert "Whataburger" in resp.text
    assert "Pizza Rolls" in resp.text
    assert "Homemade bread" in resp.text


def test_archived_hidden_by_default_visible_with_status(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _make_item(db_session, collection.id, group.id, "Old pasta", archived=True)
    _make_item(db_session, collection.id, group.id, "Fresh tacos")
    _login(post)
    resp = client.get("/library")
    assert "Fresh tacos" in resp.text
    assert "Old pasta" not in resp.text
    assert "1 active · 1 archived." in resp.text
    resp = client.get("/library", params={"status": "all"})
    assert "Old pasta" in resp.text
    resp = client.get("/library", params={"status": "archived"})
    assert "Old pasta" in resp.text
    assert "Fresh tacos" not in resp.text


def test_library_kept_label_and_recipe_link(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    item = _make_item(db_session, collection.id, group.id, "Brisket", recipe_text="Slow cook it.")
    item.times_kept = 3
    db_session.commit()
    _login(post)
    resp = client.get("/library")
    assert "Kept 3×" in resp.text
    assert "Recipe →" in resp.text


def test_library_never_shows_another_groups_items(client, post, db_session):
    """Regression: /library must resolve the signed-in account's OWN meal
    collection, never just 'the first meal collection in the whole table' —
    a bug that let anyone (even signed out) see every group's meal library."""
    other_group = _make_group(db_session, owner_email="other-owner@example.com", group_name="Other Household")
    other_collection = _make_collection(db_session, other_group.id)
    _make_item(db_session, other_collection.id, other_group.id, "Someone Else's Secret Casserole")

    group = _make_group(db_session)  # the admin@example.com account/group under test
    collection = _make_collection(db_session, group.id)
    _make_item(db_session, collection.id, group.id, "My Own Tacos")

    _login(post)
    resp = client.get("/library")
    assert resp.status_code == 200
    assert "My Own Tacos" in resp.text
    assert "Someone Else's Secret Casserole" not in resp.text


def test_library_empty_when_no_collection(client, post, db_session):
    """Library page shows empty state when the signed-in account has no meal
    collection yet (a group exists, but nobody has run the seed loader)."""
    _make_group(db_session)  # creates the admin@example.com account, no collection
    _login(post)
    resp = client.get("/library")
    assert resp.status_code == 200
    # Should render gracefully without collection
    assert "Meal Library" in resp.text


# ---------- Recipe view (signed-in accounts, own group only) ----------


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
    _login(post)
    resp = client.get(f"/library/{item.id}")
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
    _login(post)
    resp = client.get(f"/library/{item.id}")
    assert resp.status_code == 200
    assert "No recipe saved yet" in resp.text
    assert "A clean full-page cooking view" in resp.text


def test_recipe_view_unknown_404(client, post, db_session):
    _make_group(db_session)  # creates the admin@example.com account
    _login(post)
    assert client.get("/library/999999").status_code == 404


def test_recipe_view_another_groups_item_404(client, post, db_session):
    """An item belonging to a group you don't own/admin is 404, not 403 — it
    must not be distinguishable from an item that doesn't exist at all."""
    other_group = _make_group(db_session, owner_email="other-owner@example.com")
    other_collection = _make_collection(db_session, other_group.id)
    other_item = _make_item(db_session, other_collection.id, other_group.id, "Their secret recipe")
    _make_group(db_session)  # the admin@example.com account/group under test
    _login(post)
    assert client.get(f"/library/{other_item.id}").status_code == 404


# ---------- Admin gating ----------


def test_admin_gating(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _make_item(db_session, collection.id, group.id, "Steak")
    # No session at all: 401 (not signed in) on every route, including plain browsing.
    assert post("/library", data={"name": "X", "type": "dinner"}).status_code == 401
    assert client.get("/library/new").status_code == 401
    assert client.get("/library/1/edit").status_code == 401
    assert client.get("/library").status_code == 401


# ---------- Create ----------


def test_create_item(client, post, db_session):
    group = _make_group(db_session)
    _make_collection(db_session, group.id)
    _make_account(db_session)
    _login(post)
    resp = post(
        "/library",
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
    detail = db_session.get(MealDetail, item.id)
    assert detail.type == "dinner"
    assert detail.ingredients == "a\n\nb"  # internal blank line kept
    assert detail.recipe_text == "Do the thing."  # trailing whitespace stripped
    assert detail.source_url == "https://example.com/test"
    assert resp.headers["location"] == f"/library/{item.id}/edit"
    # Tags incl. the brand-new "weeknight" were created and linked.
    assert _tags_of(db_session, item.id) == {"takeout", "weeknight"}


def test_create_item_without_tags_or_recipe(client, post, db_session):
    group = _make_group(db_session)
    _make_collection(db_session, group.id)
    _make_account(db_session)
    _login(post)
    resp = post(
        "/library",
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


def test_create_duplicate_normalized_name_400(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _make_account(db_session)
    _login(post)
    _make_item(db_session, collection.id, group.id, "Bacon and Eggs")
    resp = post(
        "/library", data={"name": "bacon   and eggs", "type": "dinner"}
    )  # whitespace-collapsed collision
    assert resp.status_code == 400
    assert "An item with that name already exists" in resp.text


def test_create_invalid_type_400(client, post, db_session):
    group = _make_group(db_session)
    _make_collection(db_session, group.id)
    _make_account(db_session)
    _login(post)
    resp = post("/library", data={"name": "Weird", "type": "brunch"})
    assert resp.status_code == 400


def test_create_empty_name_400(client, post, db_session):
    group = _make_group(db_session)
    _make_collection(db_session, group.id)
    _make_account(db_session)
    _login(post)
    resp = post("/library", data={"name": "   ", "type": "dinner"})
    assert resp.status_code == 400


def test_create_without_collection_400(client, post, db_session):
    """Creating without a meal collection returns 400."""
    _make_account(db_session)
    _login(post)
    resp = post("/library", data={"name": "Test", "type": "dinner"})
    assert resp.status_code == 400
    assert "No meal collection exists" in resp.text


# ---------- Update ----------


def test_update_item_rename_and_type(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _make_account(db_session)
    _login(post)
    item = _make_item(db_session, collection.id, group.id, "Old Name", type="dinner", tags=["takeout"])
    resp = post(
        f"/library/{item.id}",
        data={"name": "New Name", "type": "both", "tags": ["takeout", "newtag"]},
        follow_redirects=False,
    )
    assert resp.status_code == 303
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
    _login(post)
    _make_item(db_session, collection.id, group.id, "Tacos")
    item = _make_item(db_session, collection.id, group.id, "Other")
    resp = post(f"/library/{item.id}", data={"name": "Tacos", "type": "dinner"})
    assert resp.status_code == 400
    assert "An item with that name already exists" in resp.text
    # Renaming an item to its own name is fine (self excluded).
    resp = post(
        f"/library/{item.id}", data={"name": "Other", "type": "dinner"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
