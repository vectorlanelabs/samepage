"""Collection-scoped item library routes (M2b, T2.1–T2.2; M2c part 2):
browse/search/filter, create/edit, admin gating, archive/unarchive, type
cycle, recipe view, the collections hub, and the legacy /library redirect.

Every test that used to hit /library now uses /collections/{id} (browse) and
/collections/{id}/items/{item_id} (detail/edit) — the multi-group dead end
found in the 2026-08-29 review, where an account in two groups could never
reach the second group's library, is what this URL scheme closes.
"""

from datetime import UTC, datetime

from conftest import stamp_session
from sqlalchemy import func, select

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

# Legacy scalar type -> the meal-type set it maps to now ('both' = lunch+dinner).
_TYPE_TO_SET = {
    "dinner": ["dinner"],
    "lunch": ["lunch"],
    "breakfast": ["breakfast"],
    "both": ["lunch", "dinner"],
}


def _meal_types_of(db_session, item_id):
    """An item's meal-type set (unordered) as stored in meal_type rows."""
    return set(
        db_session.scalars(
            select(MealType.meal_type).where(MealType.item_id == item_id)
        ).all()
    )


def _ingredients_of(db_session, item_id):
    """An item's ingredient names in entry order."""
    return list(
        db_session.scalars(
            select(Ingredient.name)
            .join(MealIngredient, MealIngredient.ingredient_id == Ingredient.id)
            .where(MealIngredient.item_id == item_id)
            .order_by(MealIngredient.position)
        ).all()
    )


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
    """Create an item with its meal-type set, structured ingredients, an
    optional meal_detail row, and optional tags."""
    import re

    item = Item(
        collection_id=collection_id,
        name=name,
        normalized_name=name.casefold(),
        description=None,
    )
    db_session.add(item)
    db_session.flush()

    for meal_type in _TYPE_TO_SET[type]:
        db_session.add(MealType(item_id=item.id, meal_type=meal_type))

    # Structured ingredients: `ingredients` is legacy free text (one name per
    # line). Normalize (lowercase + collapse whitespace), drop blanks, dedupe,
    # then create group-scoped Ingredient rows + ordered MealIngredient links.
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

    # A meal_detail row only carries recipe_text/source_url now.
    if recipe_text is not None or source_url is not None:
        db_session.add(
            MealDetail(item_id=item.id, recipe_text=recipe_text, source_url=source_url)
        )

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
    assert "1 active item" in resp.text
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
    assert resp.text.count('class="hub-group-name">Family</span>') == 2


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
    assert "2 meals" in resp.text
    # No archived clause when nothing is archived.
    assert "archived" not in resp.text
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
    # Filtering is now by a single slot; a meal matches if that slot is in its
    # set. Quesadillas is lunch+dinner, so it shows under BOTH slot filters.
    resp = client.get(f"/collections/{collection.id}", params={"type": "dinner"})
    assert "Steak" in resp.text
    assert "Quesadillas" in resp.text
    assert "Salad bar" not in resp.text
    resp = client.get(f"/collections/{collection.id}", params={"type": "lunch"})
    assert "Salad bar" in resp.text
    assert "Quesadillas" in resp.text
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


def test_library_time_filter_and_dropdown_split(client, post, db_session):
    r"""Time tags (names matching ^\d+\s?min$, like "40 min") are split out of
    the Tags dropdown into their own Time dropdown (route-side), and the time
    filter is AND-ed with every other filter."""
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _make_item(db_session, collection.id, group.id, "Sheet pan chicken", tags=["40 min"])
    _make_item(db_session, collection.id, group.id, "Slow ribs", tags=["90 min"])
    _make_item(db_session, collection.id, group.id, "Brisket", tags=["3 hours"])
    _make_item(db_session, collection.id, group.id, "Takeout night", tags=["takeout"])
    _login(client, db_session)
    resp = client.get(f"/collections/{collection.id}")
    assert resp.status_code == 200
    # The Time dropdown lists only duration tags; the Tags dropdown the rest
    # (including "3 hours", which does not match the time-tag pattern).
    time_select = resp.text.split('name="time"')[1].split("</select>")[0]
    assert "40 min" in time_select
    assert "90 min" in time_select
    assert "3 hours" not in time_select
    assert "takeout" not in time_select
    tags_select = resp.text.split('name="tags"')[1].split("</select>")[0]
    assert "takeout" in tags_select
    assert "3 hours" in tags_select
    assert "40 min" not in tags_select
    # Filtering by a time tag keeps only items carrying it.
    resp = client.get(f"/collections/{collection.id}", params={"time": "40 min"})
    assert "Sheet pan chicken" in resp.text
    assert "Slow ribs" not in resp.text
    assert "Takeout night" not in resp.text
    # Time ANDs with the Tags select (an item must carry both).
    resp = client.get(
        f"/collections/{collection.id}", params={"time": "40 min", "tags": "takeout"}
    )
    assert "Sheet pan chicken" not in resp.text
    assert "Takeout night" not in resp.text


def test_library_hides_time_dropdown_without_time_tags(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _make_item(db_session, collection.id, group.id, "Plain meal", tags=["takeout"])
    _login(client, db_session)
    resp = client.get(f"/collections/{collection.id}")
    assert 'name="time"' not in resp.text
    assert 'name="tags"' in resp.text


def test_library_time_param_ignores_non_duration_values(client, post, db_session):
    r"""A time param that does not match the time-tag shape (^\d+\s?min$) is
    ignored server-side — it filters nothing, as if absent."""
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _make_item(db_session, collection.id, group.id, "Sesame noodles", tags=["takeout"])
    _login(client, db_session)
    resp = client.get(f"/collections/{collection.id}", params={"time": "Veggie"})
    assert resp.status_code == 200
    # "Veggie" is not a duration — no time filter applies, the item stays.
    assert "Sesame noodles" in resp.text


def test_cross_group_tag_names_do_not_leak_items(client, post, db_session):
    """A tag name that exists only in another group's Tag rows — passed via
    ?tags= or ?time= (a "40 min" name for the time case) — returns zero items
    from this collection and 200: the tag filter stays collection-scoped."""
    group_a = _make_group(db_session)
    collection = _make_collection(db_session, group_a.id)
    _make_item(db_session, collection.id, group_a.id, "Sesame noodles", tags=["takeout"])
    group_b = _make_group(db_session)
    collection_b = _make_collection(db_session, group_b.id)
    _make_item(
        db_session, collection_b.id, group_b.id, "Foreign meal", tags=["secret", "40 min"]
    )
    _login(client, db_session)
    # ?tags= for a name that exists only in group B's rows.
    resp = client.get(f"/collections/{collection.id}", params={"tags": "secret"})
    assert resp.status_code == 200
    assert "Sesame noodles" not in resp.text
    assert "Foreign meal" not in resp.text
    # ?time= for a duration tag that exists only in group B's rows.
    resp = client.get(f"/collections/{collection.id}", params={"time": "40 min"})
    assert resp.status_code == 200
    assert "Sesame noodles" not in resp.text
    assert "Foreign meal" not in resp.text


def test_archived_hidden_by_default_visible_with_status(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _make_item(db_session, collection.id, group.id, "Old pasta", archived=True)
    _make_item(db_session, collection.id, group.id, "Fresh tacos")
    _login(client, db_session)
    resp = client.get(f"/collections/{collection.id}")
    assert "Fresh tacos" in resp.text
    assert "Old pasta" not in resp.text
    assert "1 meals" in resp.text
    # The archived count is a link into the archived view.
    assert "1 archived" in resp.text
    assert "?status=archived" in resp.text
    assert "Show active" not in resp.text
    resp = client.get(f"/collections/{collection.id}", params={"status": "all"})
    assert "Old pasta" in resp.text
    resp = client.get(f"/collections/{collection.id}", params={"status": "archived"})
    assert "Old pasta" in resp.text
    assert "Fresh tacos" not in resp.text
    assert "Show active" in resp.text


def test_library_kept_label_and_row_link(client, post, db_session):
    """The kept count is lowercase and rows link straight to the edit screen —
    no per-row Edit/Recipe/Archive actions on the library list itself."""
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    item = _make_item(db_session, collection.id, group.id, "Brisket", recipe_text="Slow cook it.")
    item.times_kept = 3
    db_session.commit()
    _login(client, db_session)
    resp = client.get(f"/collections/{collection.id}")
    assert "kept 3×" in resp.text
    assert f"/collections/{collection.id}/items/{item.id}/edit" in resp.text
    # The row is the only action surface; archive/recipe live on the edit screen.
    assert "Recipe →" not in resp.text
    assert "Archive" not in resp.text


# ---------- Sort (M7 S10): Name / Most kept / Recently kept ----------


def test_library_sort_kept_orders_by_times_kept_then_name(client, post, db_session):
    """?sort=kept orders by times_kept desc; equal counts fall back to
    normalized name (case-insensitive), same as the default order."""
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _make_item(db_session, collection.id, group.id, "Ziti", type="dinner")
    _make_item(db_session, collection.id, group.id, "Chili", type="dinner")
    _make_item(db_session, collection.id, group.id, "Pasta", type="dinner")
    _make_item(db_session, collection.id, group.id, "Brisket", type="dinner")
    chili = db_session.scalar(select(Item).where(Item.normalized_name == "chili"))
    pasta = db_session.scalar(select(Item).where(Item.normalized_name == "pasta"))
    brisket = db_session.scalar(select(Item).where(Item.normalized_name == "brisket"))
    chili.times_kept = 5
    pasta.times_kept = 5
    brisket.times_kept = 3
    db_session.commit()
    _login(client, db_session)
    resp = client.get(f"/collections/{collection.id}", params={"sort": "kept"})
    assert resp.status_code == 200
    # Chili and Pasta tie at 5; the tie breaks by name (Chili before Pasta).
    order = [resp.text.index(n) for n in ("Chili", "Pasta", "Brisket", "Ziti")]
    assert order == sorted(order)


def test_library_sort_recent_orders_by_last_kept_nulls_last(client, post, db_session):
    """?sort=recent orders by last_kept_at desc (newest first); never-kept
    items (last_kept_at NULL) sink to the bottom. Equal dates break by name."""
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _make_item(db_session, collection.id, group.id, "Soup", type="dinner")
    _make_item(db_session, collection.id, group.id, "Tacos", type="dinner")
    _make_item(db_session, collection.id, group.id, "Burgers", type="dinner")
    _make_item(db_session, collection.id, group.id, "Pizza", type="dinner")
    tacos = db_session.scalar(select(Item).where(Item.normalized_name == "tacos"))
    burgers = db_session.scalar(select(Item).where(Item.normalized_name == "burgers"))
    pizza = db_session.scalar(select(Item).where(Item.normalized_name == "pizza"))
    tacos.last_kept_at = datetime(2026, 8, 20, 19, 0, tzinfo=UTC)
    burgers.last_kept_at = datetime(2026, 8, 20, 19, 0, tzinfo=UTC)  # same stamp: name breaks the tie
    pizza.last_kept_at = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    # Soup.last_kept_at stays None (never kept).
    db_session.commit()
    _login(client, db_session)
    resp = client.get(f"/collections/{collection.id}", params={"sort": "recent"})
    assert resp.status_code == 200
    order = [resp.text.index(n) for n in ("Burgers", "Tacos", "Pizza", "Soup")]
    assert order == sorted(order)
    # The kept date renders as the short label in the Last kept column.
    assert ">Aug 20</span>" in resp.text
    assert ">Aug 1</span>" in resp.text
    # The never-kept item shows the empty-cell dash, not a date.
    assert 'class="lib-cell lib-cell-last lib-cell-empty">—</span>' in resp.text


def test_library_sort_invalid_value_falls_back_to_name(client, post, db_session):
    """An unknown sort value must not 500 — the route falls back to the default
    name order, as if sort were absent."""
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _make_item(db_session, collection.id, group.id, "Ziti", type="dinner")
    _make_item(db_session, collection.id, group.id, "bacon and eggs", type="both")
    _make_item(db_session, collection.id, group.id, "Apple pie", type="both")
    _login(client, db_session)
    resp = client.get(f"/collections/{collection.id}", params={"sort": "bogus"})
    assert resp.status_code == 200
    assert resp.text.index("Apple pie") < resp.text.index("bacon and eggs") < resp.text.index("Ziti")


def test_library_sort_dropdown_round_trips_with_filters(client, post, db_session):
    """The sort dropdown always renders (Name / Most kept / Recently kept), the
    active sort is marked selected, and it lives in the same GET form as the
    search box — so changing sort keeps the current query."""
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _make_item(db_session, collection.id, group.id, "Taco soup", type="both")
    _login(client, db_session)
    resp = client.get(f"/collections/{collection.id}", params={"q": "taco", "sort": "kept"})
    assert resp.status_code == 200
    # Sort sits inside the one toolbar form, after the search input.
    sort_pos = resp.text.index('name="sort"')
    assert resp.text.index('class="lib-toolbar"') < sort_pos
    assert sort_pos < resp.text.index("</form>", sort_pos)
    assert 'value="kept" selected' in resp.text
    assert 'value="name">Name</option>' in resp.text
    assert 'value="recent">Recently kept</option>' in resp.text
    # The search term survives in the same form.
    assert 'value="taco"' in resp.text


def test_library_desktop_table_columns_render(client, post, db_session):
    """Desktop (>=900px) renders a table-style grid: a header row
    (Name/Type/Tags/Kept/Last kept) and per-item cells. Empty cells show an em
    dash; the phone kept chip still renders for items that were kept."""
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    kept = _make_item(
        db_session,
        collection.id,
        group.id,
        "Sheet pan chicken",
        type="both",
        tags=["weeknight", "40 min"],
    )
    kept.times_kept = 3
    kept.last_kept_at = datetime(2026, 8, 20, 19, 0, tzinfo=UTC)
    db_session.commit()
    _make_item(db_session, collection.id, group.id, "Bare meal", type="dinner")
    _login(client, db_session)
    resp = client.get(f"/collections/{collection.id}")
    assert resp.status_code == 200
    # Header row.
    assert "lib-table-head" in resp.text
    for head in (">Name</span>", ">Type</span>", ">Tags</span>", ">Kept</span>", ">Last kept</span>"):
        assert head in resp.text
    # Kept item: type label, sorted tag label, kept count, short kept date.
    assert ">Lunch · Dinner</span>" in resp.text
    assert ">40 min · weeknight</span>" in resp.text
    assert ">3×</span>" in resp.text
    assert ">Aug 20</span>" in resp.text
    # Phone chip still renders for the kept item.
    assert ">kept 3×</span>" in resp.text
    # Bare item: its own type, and em dashes in the tag/last-kept cells.
    assert ">Dinner</span>" in resp.text
    assert 'class="lib-cell lib-cell-tags lib-cell-empty">—</span>' in resp.text
    assert 'class="lib-cell lib-cell-last lib-cell-empty">—</span>' in resp.text
    assert ">0×</span>" in resp.text


# ---------- Sidebar collections nav (M7 S10) ----------


def test_library_sidebar_lists_own_collections_and_hides_foreign(client, post, db_session):
    """Collection pages render a sidebar 'Collections' section with every
    collection the account owns or admins — the current one flagged is-active —
    and never another group's collections (cross-tenant isolation on the nav)."""
    group_a = _make_group(db_session, group_name="House A")
    collection_a = _make_collection(db_session, group_a.id, name="Meal Planner A")
    collection_b = _make_collection(db_session, group_a.id, name="Zucchini Nights")
    _make_item(db_session, collection_a.id, group_a.id, "A Tacos")

    other_group = _make_group(
        db_session, owner_email="other-owner@example.com", group_name="Other Household"
    )
    other_collection = _make_collection(db_session, other_group.id, name="Their Secret Eats")
    _make_item(db_session, other_collection.id, other_group.id, "Secret Casserole")

    _login(client, db_session)
    resp = client.get(f"/collections/{collection_a.id}")
    assert resp.status_code == 200
    assert 'class="sidebar-section-title">Collections</span>' in resp.text
    # The current collection is flagged active; the other own one is a plain link.
    assert f'class="nav-link is-active" href="/collections/{collection_a.id}"' in resp.text
    assert f'class="nav-link" href="/collections/{collection_b.id}"' in resp.text
    # Another tenant's collection never shows up in the nav.
    assert "Their Secret Eats" not in resp.text
    assert f"/collections/{other_collection.id}" not in resp.text


def test_library_sidebar_includes_admined_groups_collections(client, post, db_session):
    """A collection in a group the account only admins (not owns) also lists
    in the sidebar — same owns-or-admins scoping as the hub."""
    group = _make_group(db_session, group_name="Shared", owner_email="owner@example.com")
    collection = _make_collection(db_session, group.id, name="Shared Meals")
    _make_item(db_session, collection.id, group.id, "Shared Tacos")
    admin = _make_account(db_session, email="admin@example.com", display_name="Admin")
    db_session.add(GroupAdmin(group_id=group.id, account_id=admin.id))
    db_session.commit()
    _login(client, db_session)
    resp = client.get(f"/collections/{collection.id}")
    assert resp.status_code == 200
    assert f'class="nav-link is-active" href="/collections/{collection.id}"' in resp.text


def test_library_sidebar_keeps_same_named_collections_separate(client, post, db_session):
    """Two collections with the same name render as TWO sidebar rows — the nav
    keys on collection id (ordered by name then id), so same-named collections
    never merge into a single link."""
    group = _make_group(db_session)
    first = _make_collection(db_session, group.id, name="Dinners")
    second = _make_collection(db_session, group.id, name="Dinners")
    _make_item(db_session, first.id, group.id, "Pasta Night")
    _login(client, db_session)
    resp = client.get(f"/collections/{first.id}")
    assert resp.status_code == 200
    assert f'class="nav-link is-active" href="/collections/{first.id}"' in resp.text
    assert f'class="nav-link" href="/collections/{second.id}"' in resp.text


def test_library_area_pages_share_sidebar_collections(client, post, db_session):
    """Every library-area page — browse, add/edit meal, recipe view, report —
    renders the same sidebar 'Collections' section (current collection flagged
    is-active), not just the browse page. The section markup is one shared
    include, so each page's HTML contains it."""
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id, name="Dinners")
    other = _make_collection(db_session, group.id, name="Zucchini Nights")
    item = _make_item(db_session, collection.id, group.id, "Pasta Night")
    _login(client, db_session)

    pages = [
        f"/collections/{collection.id}",  # browse
        f"/collections/{collection.id}/items/new",  # add meal (blank edit form)
        f"/collections/{collection.id}/items/{item.id}/edit",  # edit meal
        f"/collections/{collection.id}/items/{item.id}",  # recipe view
        f"/collections/{collection.id}/report",  # report
    ]
    for path in pages:
        resp = client.get(path)
        assert resp.status_code == 200
        assert 'class="sidebar-section-title">Collections</span>' in resp.text
        assert f'class="nav-link is-active" href="/collections/{collection.id}"' in resp.text
        assert f'class="nav-link" href="/collections/{other.id}"' in resp.text


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
    assert "Full recipe at example.com ↗" in resp.text
    assert "← Meal Planner" in resp.text  # back link goes to the collection
    assert "Back to library" not in resp.text
    assert "Kept 0×" not in resp.text  # no kept line when times_kept == 0


def test_recipe_view_empty_state(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    item = _make_item(db_session, collection.id, group.id, "Mystery night")
    _login(client, db_session)
    resp = client.get(f"/collections/{collection.id}/items/{item.id}")
    assert resp.status_code == 200
    assert "No recipe saved yet" in resp.text


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
    assert post(f"/collections/{collection.id}/items", data={"name": "X", "types": ["dinner"]}).status_code == 401
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
            "types": ["dinner"],
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
    assert _meal_types_of(db_session, item.id) == {"dinner"}
    detail = db_session.get(MealDetail, item.id)
    assert _ingredients_of(db_session, item.id) == ["a", "b"]  # blank lines dropped
    assert detail.recipe_text == "Do the thing."  # trailing whitespace stripped
    assert detail.source_url == "https://example.com/test"
    assert resp.headers["location"] == f"/collections/{collection.id}?added=1"
    # Tags incl. the brand-new "weeknight" were created and linked.
    assert _tags_of(db_session, item.id) == {"takeout", "weeknight"}


def test_create_item_without_tags_or_recipe(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _make_account(db_session)
    _login(client, db_session)
    resp = post(
        f"/collections/{collection.id}/items",
        data={"name": "Bare meal", "types": ["lunch"]},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    item = db_session.scalar(select(Item).where(Item.normalized_name == "bare meal"))
    assert item is not None
    detail = db_session.get(MealDetail, item.id)
    assert _ingredients_of(db_session, item.id) == []
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
        data={"name": "B Item", "types": ["dinner"]},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    item = db_session.scalar(select(Item).where(Item.normalized_name == "b item"))
    assert item is not None
    assert item.collection_id == collection_b.id  # landed in B, not A
    assert resp.headers["location"] == f"/collections/{collection_b.id}?added=1"


def test_create_duplicate_normalized_name_400(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _make_account(db_session)
    _login(client, db_session)
    _make_item(db_session, collection.id, group.id, "Bacon and Eggs")
    resp = post(
        f"/collections/{collection.id}/items",
        data={"name": "bacon   and eggs", "types": ["dinner"]},
    )  # whitespace-collapsed collision
    assert resp.status_code == 400
    assert "An item with that name already exists" in resp.text


def test_create_invalid_type_400(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _make_account(db_session)
    _login(client, db_session)
    resp = post(f"/collections/{collection.id}/items", data={"name": "Weird", "types": ["brunch"]})
    assert resp.status_code == 400


def test_create_empty_name_400(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _make_account(db_session)
    _login(client, db_session)
    resp = post(f"/collections/{collection.id}/items", data={"name": "   ", "types": ["dinner"]})
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
        data={"name": "Stowaway", "types": ["dinner"]},
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
        data={"name": "New Name", "types": ["lunch", "dinner"], "tags": ["takeout", "newtag"]},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/collections/{collection.id}/items/{item.id}/edit?saved=1"
    db_session.refresh(item)
    assert item.name == "New Name"
    assert item.normalized_name == "new name"  # recomputed on rename
    assert _meal_types_of(db_session, item.id) == {"lunch", "dinner"}
    assert _tags_of(db_session, item.id) == {"takeout", "newtag"}


def test_edit_page_tag_chips_applied_and_adder(client, post, db_session):
    """Applied tags render as checked chips; the rest sit unchecked behind the
    '+ tag' adder — pure HTML, no JS toggling."""
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _make_item(db_session, collection.id, group.id, "Chili", tags=["spicy", "40 min"])
    _make_item(db_session, collection.id, group.id, "Other meal", tags=["weeknight"])
    item = db_session.scalar(select(Item).where(Item.normalized_name == "chili"))
    _login(client, db_session)
    resp = client.get(f"/collections/{collection.id}/items/{item.id}/edit")
    assert resp.status_code == 200
    # Applied tags are checked chips.
    assert 'value="spicy" checked' in resp.text
    assert 'value="40 min" checked' in resp.text
    # Remaining tags live unchecked behind the adder.
    assert '<details class="tag-adder">' in resp.text
    assert 'value="weeknight">' in resp.text
    # No JS toggle script and no per-chip ✕ span (the ✕ is CSS-on-checked now).
    assert "document.querySelectorAll('.tag-chip')" not in resp.text
    assert "tag-chip-x" not in resp.text


def test_edit_page_recipe_link_only_with_recipe_content(client, post, db_session):
    """'View recipe →' renders only when the item actually has recipe content
    (structured ingredients, instructions, or a source URL) — the same
    definition the old library row used."""
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    plain = _make_item(db_session, collection.id, group.id, "Plain meal", tags=["takeout"])
    with_ingredients = _make_item(
        db_session, collection.id, group.id, "With ingredients", ingredients="chicken\nrice"
    )
    with_instructions = _make_item(
        db_session, collection.id, group.id, "With instructions", recipe_text="Bake it."
    )
    with_source = _make_item(
        db_session,
        collection.id,
        group.id,
        "With source",
        source_url="https://example.com/recipe",
    )
    _login(client, db_session)
    resp = client.get(f"/collections/{collection.id}/items/{plain.id}/edit")
    assert resp.status_code == 200
    assert "View recipe →" not in resp.text
    for item in (with_ingredients, with_instructions, with_source):
        resp = client.get(f"/collections/{collection.id}/items/{item.id}/edit")
        assert resp.status_code == 200
        assert "View recipe →" in resp.text


def test_update_unchecking_a_tag_removes_it(client, post, db_session):
    """The update POST replaces the tag set: a tag unchecked on the edit form
    disappears (delete-all + re-add, never merged)."""
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    item = _make_item(db_session, collection.id, group.id, "Burger night", tags=["takeout", "snack"])
    _login(client, db_session)
    resp = post(
        f"/collections/{collection.id}/items/{item.id}",
        data={"name": "Burger night", "types": ["dinner"], "tags": ["snack"]},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert _tags_of(db_session, item.id) == {"snack"}


def test_update_rename_collision_400(client, post, db_session):
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _make_account(db_session)
    _login(client, db_session)
    _make_item(db_session, collection.id, group.id, "Tacos")
    item = _make_item(db_session, collection.id, group.id, "Other")
    resp = post(
        f"/collections/{collection.id}/items/{item.id}",
        data={"name": "Tacos", "types": ["dinner"]},
    )
    assert resp.status_code == 400
    assert "An item with that name already exists" in resp.text
    # Renaming an item to its own name is fine (self excluded).
    resp = post(
        f"/collections/{collection.id}/items/{item.id}",
        data={"name": "Other", "types": ["dinner"]},
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
        data={"name": "Hijacked", "types": ["dinner"]},
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
        data={"name": "Hijacked", "types": ["dinner"]},
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
        data={"name": "Renamed", "types": ["dinner"]},
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


def test_empty_states_distinguish_empty_collection_from_filtered(client, db_session):
    """Regression (Oscar M2e): a collection with items but zero filter matches
    must say 'No items match these filters', NOT 'has no items yet' (which
    implies the collection needs setting up)."""
    group = _make_group(db_session)
    collection = _make_collection(db_session, group.id)
    _login(client, db_session)

    # Truly empty collection → "no items yet".
    resp = client.get(f"/collections/{collection.id}")
    assert "has no items yet" in resp.text
    assert "No items match these filters" not in resp.text

    # Add an item, then filter to zero matches → "no items match".
    _make_item(db_session, collection.id, group.id, "Real Meal")
    resp = client.get(f"/collections/{collection.id}?q=zzz-no-such-meal")
    assert "No items match these filters" in resp.text
    assert "has no items yet" not in resp.text
