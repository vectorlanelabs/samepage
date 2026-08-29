"""M4 reporting & discovery tests (plan §6): the per-collection report
(reject rates by item and by tag), the no-history empty state, and the
tenant-scoping invariants — a cross-tenant request is 404 (never 403, no
existence oracle), one group's report never contains another group's item
names or numbers, the by-tag join is collection-scoped not group-scoped,
and the "not offered lately" list surfaces the lowest-offered non-archived
items.
"""

from datetime import UTC, datetime

from conftest import stamp_session
from sqlalchemy import func, select

from app.models import Account, Collection, Group, Item, ItemTag, MealDetail, Tag


def _make_account(db_session, email, display_name=None):
    account = Account(email=email, display_name=display_name or email.split("@")[0])
    db_session.add(account)
    db_session.commit()
    return account


def _make_group(db_session, owner_email, name="Test Group"):
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


def _make_item(db_session, collection_id, group_id, name, tags=(), archived=False):
    """Item with a meal_detail row and optional group-scoped tags."""
    item = Item(collection_id=collection_id, name=name, normalized_name=name.casefold())
    db_session.add(item)
    db_session.flush()
    db_session.add(MealDetail(item_id=item.id, type="dinner"))
    for tname in tags:
        tag = db_session.scalar(
            select(Tag).where((Tag.group_id == group_id) & (Tag.name == tname))
        )
        if tag is None:
            tag = Tag(group_id=group_id, name=tname)
            db_session.add(tag)
            db_session.flush()
        db_session.add(ItemTag(item_id=item.id, tag_id=tag.id))
    if archived:
        item.archived_at = func.now()
    db_session.commit()
    return item


def _login(client, db_session, email):
    account = db_session.scalar(select(Account).where(Account.email == email))
    stamp_session(client, account)


# ---------- Report renders (by item + by tag, correct numbers) ----------


def test_report_renders_by_item_and_by_tag(client, post, db_session):
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

    _login(client, db_session, "owner@example.com")
    resp = client.get(f"/collections/{collection.id}/report")
    assert resp.status_code == 200

    # By item: Tuna rejected 7/10 → 70%; Pizza rejected 0/2 → 0%.
    assert "Tuna Night" in resp.text
    assert "70% rejected" in resp.text
    assert "Kept 3 of 10 offered" in resp.text
    assert "last kept Aug 01, 2026" in resp.text
    assert "Pizza" in resp.text
    assert "0% rejected" in resp.text
    assert "Kept 2 of 2 offered" in resp.text
    assert "never kept" in resp.text
    # Higher reject rate first.
    assert resp.text.index("Tuna Night") < resp.text.index("Pizza")

    # By tag: fish = Tuna only → 7/10 → 70%; quick = Tuna + Pizza → 7/12 → 58%.
    assert "Kept 5 of 12 offered" in resp.text
    assert resp.text.index(">fish<") < resp.text.index(">quick<")


# ---------- Empty state ----------


def test_report_empty_state_when_nothing_offered(client, post, db_session):
    group = _make_group(db_session, owner_email="owner@example.com")
    collection = _make_collection(db_session, group.id)
    _make_item(db_session, collection.id, group.id, "Unoffered Meal")
    _login(client, db_session, "owner@example.com")
    resp = client.get(f"/collections/{collection.id}/report")
    assert resp.status_code == 200
    assert "No voting history yet — run a session to see which meals land." in resp.text


# ---------- Cross-tenant (the §6 requirement) ----------


def test_report_another_groups_collection_404_and_no_leak(client, post, db_session):
    """An account requesting another group's collection report gets 404, and
    each group's report shows only its own item names and numbers — plus a
    nonexistent collection id is 404, indistinguishable."""
    group_a = _make_group(db_session, owner_email="a@example.com", name="Group A")
    collection_a = _make_collection(db_session, group_a.id, name="Collection A")
    a_item = _make_item(db_session, collection_a.id, group_a.id, "A Secret Tacos", tags=["secret"])
    a_item.times_offered = 8
    a_item.times_kept = 1

    group_b = _make_group(db_session, owner_email="b@example.com", name="Group B")
    collection_b = _make_collection(db_session, group_b.id, name="Collection B")
    b_item = _make_item(db_session, collection_b.id, group_b.id, "B Burgers", tags=["secret"])
    b_item.times_offered = 4
    b_item.times_kept = 2
    db_session.commit()

    # B's account requesting A's report → 404, never 403 (no existence oracle).
    _login(client, db_session, "b@example.com")
    assert client.get(f"/collections/{collection_a.id}/report").status_code == 404

    # B's own report: B's data only — A's item names and numbers absent.
    resp = client.get(f"/collections/{collection_b.id}/report")
    assert resp.status_code == 200
    assert "B Burgers" in resp.text
    assert "Kept 2 of 4 offered" in resp.text
    assert "A Secret Tacos" not in resp.text
    assert "Kept 1 of 8 offered" not in resp.text

    # A's account requesting B's report → 404; A's report never has B's data.
    _login(client, db_session, "a@example.com")
    assert client.get(f"/collections/{collection_b.id}/report").status_code == 404
    resp = client.get(f"/collections/{collection_a.id}/report")
    assert resp.status_code == 200
    assert "A Secret Tacos" in resp.text
    assert "Kept 1 of 8 offered" in resp.text
    assert "B Burgers" not in resp.text
    assert "Kept 2 of 4 offered" not in resp.text

    # A nonexistent collection id → 404.
    assert client.get("/collections/999999/report").status_code == 404


# ---------- By-tag scoping ----------


def test_report_by_tag_aggregates_only_this_collection(client, post, db_session):
    """A tag shared across two collections in the SAME group aggregates only
    the requested collection's items — proving the join is collection-scoped,
    not group-scoped (the same Tag row serves both collections)."""
    group = _make_group(db_session, owner_email="owner@example.com")
    collection_a = _make_collection(db_session, group.id, name="A")
    collection_b = _make_collection(db_session, group.id, name="B")

    a1 = _make_item(db_session, collection_a.id, group.id, "A Pasta", tags=["comfort"])
    a1.times_offered = 10
    a1.times_kept = 4
    a2 = _make_item(db_session, collection_a.id, group.id, "A Soup", tags=["comfort"])
    a2.times_offered = 5
    a2.times_kept = 5
    b1 = _make_item(db_session, collection_b.id, group.id, "B Stew", tags=["comfort"])
    b1.times_offered = 2
    b1.times_kept = 0
    db_session.commit()

    _login(client, db_session, "owner@example.com")

    # A's report: comfort sums A's two items (15 offered, 9 kept) — the
    # aggregate appears nowhere as a single item row, so the text can only
    # come from the by-tag section.
    resp = client.get(f"/collections/{collection_a.id}/report")
    assert resp.status_code == 200
    assert "Kept 9 of 15 offered" in resp.text
    assert "Kept 0 of 2 offered" not in resp.text

    # B's report: the same tag row, but only B's item (2 offered, 0 kept).
    resp = client.get(f"/collections/{collection_b.id}/report")
    assert resp.status_code == 200
    assert "Kept 0 of 2 offered" in resp.text
    assert "Kept 9 of 15 offered" not in resp.text


# ---------- Not offered lately ----------


def test_report_not_offered_lately_surfaces_lowest_non_archived(client, post, db_session):
    """The top 5 non-archived items with the LOWEST times_offered surface
    (ties broken by name); higher-offered and archived items are excluded."""
    group = _make_group(db_session, owner_email="owner@example.com")
    collection = _make_collection(db_session, group.id)

    # Archived item would top the list by both sort keys if it were eligible.
    archived = _make_item(db_session, collection.id, group.id, "Aaa Archived", archived=True)
    archived.times_offered = 0
    for name, offered in [
        ("A Soup", 0),
        ("C Soup", 0),
        ("B Soup", 1),
        ("E Soup", 1),
        ("D Soup", 2),
        ("F Soup", 2),
    ]:
        item = _make_item(db_session, collection.id, group.id, name)
        item.times_offered = offered
    db_session.commit()

    _login(client, db_session, "owner@example.com")
    resp = client.get(f"/collections/{collection.id}/report")
    assert resp.status_code == 200

    # Top 5 by (times_offered, name): A Soup, C Soup, B Soup, E Soup, D Soup.
    # F Soup (offered 2, later name) and the archived item never appear in the
    # not-offered section (F Soup may appear in the By meal report — it has
    # been offered — so scope these assertions to the section).
    section = resp.text[resp.text.index('id="not-offered"') :]
    for name in ["A Soup", "C Soup", "B Soup", "E Soup", "D Soup"]:
        assert name in section
    assert "F Soup" not in section
    assert "Aaa Archived" not in section
    # Order: ascending times_offered, ties broken by name.
    assert (
        section.index("A Soup")
        < section.index("C Soup")
        < section.index("B Soup")
        < section.index("E Soup")
        < section.index("D Soup")
    )
    # Labels: never-offered items say so; offered ones show the count.
    assert section.count("never offered") == 2
    assert "offered 1×" in section
    assert "offered 2×" in section


# ---------- Sign-in gate ----------


def test_report_requires_signin(client, db_session):
    assert client.get("/collections/1/report").status_code == 401
