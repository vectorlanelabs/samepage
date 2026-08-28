"""Meal library routes (M2, T2.1–T2.2): browse/search/filter, create/edit,
admin gating, archive/unarchive, type cycle, recipe view."""

from sqlalchemy import func, select

from app.models import Meal, MealTag, Person, Tag
from app.pins import hash_pin


def _make_meal(
    db_session,
    name,
    type="dinner",
    tags=(),
    ingredients=None,
    recipe_text=None,
    source_url=None,
    archived=False,
):
    meal = Meal(
        name=name,
        normalized_name=name.casefold(),
        type=type,
        ingredients=ingredients,
        recipe_text=recipe_text,
        source_url=source_url,
        is_active=True,
    )
    db_session.add(meal)
    db_session.flush()
    for tname in tags:
        tag = db_session.scalar(select(Tag).where(Tag.name == tname))
        if tag is None:
            tag = Tag(name=tname)
            db_session.add(tag)
            db_session.flush()
        db_session.add(MealTag(meal_id=meal.id, tag_id=tag.id))
    if archived:
        meal.archived_at = func.now()
    db_session.commit()
    return meal


def _make_person(db_session, name="Admin", is_admin=True):
    person = Person(name=name, pin_hash=hash_pin("1234"), is_admin=is_admin, is_active=True)
    db_session.add(person)
    db_session.commit()
    return person


def _login(post, name="Admin", pin="1234"):
    post("/login", data={"name": name, "pin": pin})


def _tags_of(db_session, meal_id):
    return set(
        db_session.scalars(
            select(Tag.name)
            .join(MealTag, MealTag.tag_id == Tag.id)
            .where(MealTag.meal_id == meal_id)
        ).all()
    )


# ---------- Browse / search / filter (public) ----------


def test_library_page_lists_meals(client, db_session):
    _make_meal(db_session, "Taco Tuesday", tags=["takeout"])
    _make_meal(db_session, "Pancakes", type="both")
    resp = client.get("/library")
    assert resp.status_code == 200
    assert "Meal Library" in resp.text
    assert "Taco Tuesday" in resp.text
    assert "Pancakes" in resp.text
    assert "2 active · 0 archived." in resp.text


def test_library_search_filters(client, db_session):
    _make_meal(db_session, "taco soup", type="both")
    _make_meal(db_session, "bacon and eggs", type="both")
    resp = client.get("/library", params={"q": "taco"})
    assert "taco soup" in resp.text
    assert "bacon and eggs" not in resp.text
    # Case-insensitive on name and normalized_name.
    resp = client.get("/library", params={"q": "BACON"})
    assert "bacon and eggs" in resp.text
    assert "taco soup" not in resp.text


def test_library_type_filter(client, db_session):
    _make_meal(db_session, "Steak", type="dinner")
    _make_meal(db_session, "Quesadillas", type="both")
    _make_meal(db_session, "Salad bar", type="lunch")
    resp = client.get("/library", params={"type": "both"})
    assert "Quesadillas" in resp.text
    assert "Steak" not in resp.text
    assert "Salad bar" not in resp.text
    resp = client.get("/library", params={"type": "lunch"})
    assert "Salad bar" in resp.text
    assert "Steak" not in resp.text


def test_library_tag_filter_or_semantics(client, db_session):
    _make_meal(db_session, "Whataburger", tags=["takeout"])
    _make_meal(db_session, "Pizza Rolls", tags=["takeout", "snack"])
    _make_meal(db_session, "Homemade bread", tags=["snack"])
    resp = client.get("/library", params={"tags": "takeout"})
    assert "Whataburger" in resp.text
    assert "Pizza Rolls" in resp.text
    assert "Homemade bread" not in resp.text
    # OR: either tag matches.
    resp = client.get("/library", params={"tags": "takeout,snack"})
    assert "Whataburger" in resp.text
    assert "Pizza Rolls" in resp.text
    assert "Homemade bread" in resp.text


def test_archived_hidden_by_default_visible_with_status(client, db_session):
    _make_meal(db_session, "Old pasta", archived=True)
    _make_meal(db_session, "Fresh tacos")
    resp = client.get("/library")
    assert "Fresh tacos" in resp.text
    assert "Old pasta" not in resp.text
    assert "1 active · 1 archived." in resp.text
    resp = client.get("/library", params={"status": "all"})
    assert "Old pasta" in resp.text
    resp = client.get("/library", params={"status": "archived"})
    assert "Old pasta" in resp.text
    assert "Fresh tacos" not in resp.text


def test_library_kept_label_and_recipe_link(client, db_session):
    meal = _make_meal(db_session, "Brisket", recipe_text="Slow cook it.")
    meal.times_kept = 3
    db_session.commit()
    resp = client.get("/library")
    assert "Kept 3×" in resp.text
    assert "Recipe →" in resp.text


# ---------- Recipe view (public) ----------


def test_recipe_view_renders(client, db_session):
    meal = _make_meal(
        db_session,
        "Chili",
        type="both",
        tags=["spicy"],
        ingredients="1 lb beef\n2 cans beans\n\n1 onion",
        recipe_text="Brown the beef. Simmer an hour.",
        source_url="https://example.com/chili",
    )
    resp = client.get(f"/library/{meal.id}")
    assert resp.status_code == 200
    assert "Chili" in resp.text
    assert "1 lb beef" in resp.text
    assert "2 cans beans" in resp.text
    assert "1 onion" in resp.text
    assert "Brown the beef. Simmer an hour." in resp.text
    assert "Originally sourced from this recipe ↗" in resp.text
    assert "Kept 0×" not in resp.text  # no kept line when times_kept == 0


def test_recipe_view_empty_state(client, db_session):
    meal = _make_meal(db_session, "Mystery night")
    resp = client.get(f"/library/{meal.id}")
    assert resp.status_code == 200
    assert "No recipe saved yet" in resp.text
    assert "A clean full-page cooking view" in resp.text


def test_recipe_view_unknown_404(client, db_session):
    assert client.get("/library/999999").status_code == 404


# ---------- Admin gating ----------


def test_admin_gating(client, post, db_session):
    _make_meal(db_session, "Steak")
    # No session at all.
    assert post("/library", data={"name": "X", "type": "dinner"}).status_code == 403
    assert client.get("/library/new").status_code == 403
    assert client.get("/library/1/edit").status_code == 403
    # Signed in as a non-admin.
    _make_person(db_session, "User", is_admin=False)
    _login(post, "User")
    assert post("/library", data={"name": "X", "type": "dinner"}).status_code == 403
    assert post("/library/1/archive").status_code == 403
    assert post("/library/1/cycle-type").status_code == 403
    assert client.get("/library/1/edit").status_code == 403
    assert client.get("/library/new").status_code == 403
    # Non-admins still see the public pages.
    assert client.get("/library").status_code == 200


# ---------- Create ----------


def test_create_meal(client, post, db_session):
    _make_person(db_session, "Admin")
    _login(post, "Admin")
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
    meal = db_session.scalar(select(Meal).where(Meal.normalized_name == "test meal"))
    assert meal is not None
    assert meal.type == "dinner"
    assert meal.ingredients == "a\n\nb"  # internal blank line kept
    assert meal.recipe_text == "Do the thing."  # trailing whitespace stripped
    assert meal.source_url == "https://example.com/test"
    assert resp.headers["location"] == f"/library/{meal.id}/edit"
    # Tags incl. the brand-new "weeknight" were created and linked.
    assert _tags_of(db_session, meal.id) == {"takeout", "weeknight"}


def test_create_meal_without_tags_or_recipe(client, post, db_session):
    _make_person(db_session, "Admin")
    _login(post, "Admin")
    resp = post(
        "/library",
        data={"name": "Bare meal", "type": "lunch"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    meal = db_session.scalar(select(Meal).where(Meal.normalized_name == "bare meal"))
    assert meal is not None
    assert meal.ingredients is None
    assert meal.recipe_text is None
    assert _tags_of(db_session, meal.id) == set()


def test_create_duplicate_normalized_name_400(client, post, db_session):
    _make_person(db_session, "Admin")
    _login(post, "Admin")
    _make_meal(db_session, "Bacon and Eggs")
    resp = post(
        "/library", data={"name": "bacon   and eggs", "type": "dinner"}
    )  # whitespace-collapsed collision
    assert resp.status_code == 400
    assert "A meal with that name already exists." in resp.text


def test_create_invalid_type_400(client, post, db_session):
    _make_person(db_session, "Admin")
    _login(post, "Admin")
    resp = post("/library", data={"name": "Weird", "type": "brunch"})
    assert resp.status_code == 400


def test_create_empty_name_400(client, post, db_session):
    _make_person(db_session, "Admin")
    _login(post, "Admin")
    resp = post("/library", data={"name": "   ", "type": "dinner"})
    assert resp.status_code == 400


# ---------- Update ----------


def test_update_meal_rename_and_type(client, post, db_session):
    _make_person(db_session, "Admin")
    _login(post, "Admin")
    meal = _make_meal(db_session, "Old Name", type="dinner", tags=["takeout"])
    resp = post(
        f"/library/{meal.id}",
        data={"name": "New Name", "type": "both", "tags": ["takeout", "newtag"]},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    db_session.refresh(meal)
    assert meal.name == "New Name"
    assert meal.normalized_name == "new name"  # recomputed on rename
    assert meal.type == "both"
    assert _tags_of(db_session, meal.id) == {"takeout", "newtag"}


def test_update_rename_collision_400(client, post, db_session):
    _make_person(db_session, "Admin")
    _login(post, "Admin")
    _make_meal(db_session, "Tacos")
    meal = _make_meal(db_session, "Other")
    resp = post(f"/library/{meal.id}", data={"name": "Tacos", "type": "dinner"})
    assert resp.status_code == 400
    assert "A meal with that name already exists." in resp.text
    # Renaming a meal to its own name is fine (self excluded).
    resp = post(
        f"/library/{meal.id}", data={"name": "Other", "type": "dinner"},
        follow_redirects=False,
    )
    assert resp.status_code == 303


# ---------- Cycle type / archive ----------


def test_cycle_type_round_trip(client, post, db_session):
    _make_person(db_session, "Admin")
    _login(post, "Admin")
    meal = _make_meal(db_session, "Cycler", type="dinner")
    for expected in ("lunch", "both", "dinner"):
        resp = post(f"/library/{meal.id}/cycle-type", follow_redirects=False)
        assert resp.status_code == 303
        db_session.refresh(meal)
        assert meal.type == expected


def test_archive_unarchive(client, post, db_session):
    _make_person(db_session, "Admin")
    _login(post, "Admin")
    meal = _make_meal(db_session, "Archivable")
    post(f"/library/{meal.id}/archive")
    db_session.refresh(meal)
    assert meal.archived_at is not None
    assert "Archivable" not in client.get("/library").text
    assert "Archivable" in client.get("/library", params={"status": "archived"}).text
    post(f"/library/{meal.id}/unarchive")
    db_session.refresh(meal)
    assert meal.archived_at is None
    assert "Archivable" in client.get("/library").text


# ---------- Source URL safety (stored XSS) ----------


def test_create_rejects_unsafe_source_url(client, post, db_session):
    _make_person(db_session, "Admin")
    _login(post, "Admin")
    unsafe_urls = [
        "javascript:alert(1)",
        "JaVaScRiPt:alert(1)",
        "ftp://example.com/x",
        "data:text/html,<script>alert(1)</script>",
        "//evil.example/x",
    ]
    for i, unsafe in enumerate(unsafe_urls):
        resp = post(
            "/library",
            data={"name": f"Unsafe {i}", "type": "dinner", "source_url": unsafe},
        )
        assert resp.status_code == 400, unsafe
        assert "Source URL must start with http:// or https://." in resp.text, unsafe
    # None of the rejected submissions were persisted.
    assert (
        db_session.scalar(select(Meal).where(Meal.normalized_name.like("unsafe %")))
        is None
    )


def test_create_stores_valid_https_source_url(client, post, db_session):
    _make_person(db_session, "Admin")
    _login(post, "Admin")
    resp = post(
        "/library",
        data={
            "name": "Sourced Meal",
            "type": "dinner",
            "source_url": "https://example.com/recipe",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    meal = db_session.scalar(select(Meal).where(Meal.normalized_name == "sourced meal"))
    assert meal is not None
    assert meal.source_url == "https://example.com/recipe"
    # Recipe page renders the link with the stored URL.
    page = client.get(f"/library/{meal.id}")
    assert page.status_code == 200
    assert 'href="https://example.com/recipe"' in page.text
    assert "Originally sourced from this recipe" in page.text


def test_update_rejects_unsafe_source_url_keeps_previous(client, post, db_session):
    _make_person(db_session, "Admin")
    _login(post, "Admin")
    meal = _make_meal(db_session, "Sourced", source_url="https://example.com/ok")
    resp = post(
        f"/library/{meal.id}",
        data={"name": "Sourced", "type": "dinner", "source_url": "javascript:alert(1)"},
    )
    assert resp.status_code == 400
    assert "Source URL must start with http:// or https://." in resp.text
    db_session.refresh(meal)
    assert meal.source_url == "https://example.com/ok"


def test_recipe_view_omits_unsafe_source_link(client, db_session):
    # Planted directly in the DB, bypassing form validation (legacy/bad data).
    meal = _make_meal(db_session, "Legacy Bad", source_url="javascript:alert(1)")
    resp = client.get(f"/library/{meal.id}")
    assert resp.status_code == 200
    assert "javascript:" not in resp.text
    assert 'href="javascript:' not in resp.text
    assert "Originally sourced from this recipe" not in resp.text
