"""Create-collection flow (M2e): GET /collections/new + POST /collections.

A blank production DB has no seed pipeline anymore — collections are created
in-app by an account that owns/admins a group. Cover the happy path (lands on
the new collection's empty page with the new empty-state copy), the blank-name
400 re-render with the group picker still listed, the no-oracle 404 for a
group id that isn't the account's (no Collection row created), the no-groups
landing state, admins creating into admined groups, and the hub's "+ New
collection" button.
"""

from conftest import stamp_session
from sqlalchemy import func, select

from app.models import Account, Collection, Group, GroupAdmin


def _get_or_make_account(db_session, email="admin@example.com", display_name="Admin"):
    """Get-or-create so helpers can be called in any order and still refer to
    the same account row."""
    account = db_session.scalar(select(Account).where(Account.email == email))
    if account is not None:
        return account
    account = Account(email=email, display_name=display_name)
    db_session.add(account)
    db_session.commit()
    return account


def _make_account(db_session, email="admin@example.com", display_name="Admin"):
    return _get_or_make_account(db_session, email=email, display_name=display_name)


def _make_group(db_session, name="Test Group", owner_email="admin@example.com"):
    """Create a group owned by the (possibly just-created) account at owner_email."""
    account = _get_or_make_account(db_session, email=owner_email)
    group = Group(name=name, owner_account_id=account.id)
    db_session.add(group)
    db_session.commit()
    return group


def _login(client, db_session, email="admin@example.com"):
    """Authenticate the TestClient session as the account with `email`."""
    account = db_session.scalar(select(Account).where(Account.email == email))
    stamp_session(client, account)


def _collection_count(db_session):
    return db_session.scalar(select(func.count()).select_from(Collection)) or 0


# ---------- GET /collections/new ----------


def test_new_collection_requires_signin(client):
    resp = client.get(
        "/collections/new", headers={"accept": "text/html"}, follow_redirects=False
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login?next=%2Fcollections%2Fnew"


def test_new_collection_page_lists_owned_groups(client, db_session):
    group = _make_group(db_session, name="Household")
    _login(client, db_session)
    resp = client.get("/collections/new")
    assert resp.status_code == 200
    assert "New collection" in resp.text
    assert "Household" in resp.text
    assert 'name="group_id"' in resp.text  # the group picker
    assert "Meal Planner collection" in resp.text  # kind is fixed, rendered as text
    assert 'name="kind" value="meal"' in resp.text  # hidden kind input
    assert f'value="{group.id}"' in resp.text


def test_new_collection_page_no_groups(client, db_session):
    """An account with no groups gets the 'Create a group first.' landing
    state and no form at all."""
    _make_account(db_session)
    _login(client, db_session)
    resp = client.get("/collections/new")
    assert resp.status_code == 200
    assert "Create a group first." in resp.text
    assert "/groups" in resp.text  # the link out
    assert 'name="group_id"' not in resp.text  # no form without groups


# ---------- POST /collections ----------


def test_create_collection_requires_signin(client, post):
    resp = post("/collections", data={"name": "X", "group_id": "1"})
    assert resp.status_code == 401


def test_create_collection_happy_path(client, post, db_session):
    group = _make_group(db_session, name="Household")
    _login(client, db_session)
    resp = post(
        "/collections",
        data={"name": "Weeknight dinners", "group_id": str(group.id)},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    collection = db_session.scalar(
        select(Collection).where(Collection.name == "Weeknight dinners")
    )
    assert collection is not None
    assert collection.group_id == group.id
    assert collection.kind == "meal"
    assert resp.headers["location"] == f"/collections/{collection.id}"

    # The redirect lands on the new collection's empty page: new empty-state
    # copy, and the "+ Add a meal" affordance still visible.
    resp = client.get(f"/collections/{collection.id}")
    assert resp.status_code == 200
    assert "This collection has no items yet." in resp.text
    assert "+ Add a meal" in resp.text


def test_create_collection_blank_name_400_keeps_groups(client, post, db_session):
    """A blank name is a 400 re-render of the form with the error shown and
    the group picker still populated (nothing created)."""
    group = _make_group(db_session, name="Household")
    _login(client, db_session)
    resp = post("/collections", data={"name": "   ", "group_id": str(group.id)})
    assert resp.status_code == 400
    assert "Name is required." in resp.text
    assert "Household" in resp.text  # group picker survives the 400
    assert 'name="group_id"' in resp.text
    assert _collection_count(db_session) == 0


def test_create_collection_another_groups_group_404(client, post, db_session):
    """Another account's group id → 404 with no Collection row — the status
    code must not double as an oracle for which group ids exist (same
    no-existence-oracle rule as the library routes)."""
    other_group = _make_group(db_session, name="Other Household", owner_email="other-owner@example.com")
    _make_group(db_session)  # admin@example.com's own group, so they're a real signed-in account
    _login(client, db_session)
    resp = post(
        "/collections",
        data={"name": "Stowaway", "group_id": str(other_group.id)},
    )
    assert resp.status_code == 404
    assert db_session.scalar(select(Collection).where(Collection.name == "Stowaway")) is None
    assert _collection_count(db_session) == 0


def test_create_collection_nonexistent_group_404(client, post, db_session):
    """A group id that doesn't exist at all is also 404 — indistinguishable
    from another account's group."""
    _make_account(db_session)
    _login(client, db_session)
    resp = post("/collections", data={"name": "Ghost", "group_id": "999999"})
    assert resp.status_code == 404
    assert _collection_count(db_session) == 0


def test_admin_can_create_collection_in_admined_group(client, post, db_session):
    """Group admins (not just owners) can create collections in groups they
    admin — the picker lists owned OR admined groups, and POST accepts them."""
    group = _make_group(db_session, name="Shared", owner_email="owner@example.com")
    admin = _make_account(db_session, email="admin@example.com", display_name="Admin")
    db_session.add(GroupAdmin(group_id=group.id, account_id=admin.id))
    db_session.commit()

    _login(client, db_session, "admin@example.com")
    resp = post(
        "/collections",
        data={"name": "Shared meals", "group_id": str(group.id)},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    collection = db_session.scalar(
        select(Collection).where(Collection.name == "Shared meals")
    )
    assert collection is not None
    assert collection.group_id == group.id
    assert collection.kind == "meal"


# ---------- Hub ----------


def test_collections_hub_shows_new_collection_button(client, db_session):
    """The hub always offers the create flow — button in the header, and the
    new empty-state copy when there are no collections yet."""
    _make_group(db_session, name="Household")
    _login(client, db_session)
    resp = client.get("/collections")
    assert resp.status_code == 200
    assert 'href="/collections/new"' in resp.text
    assert "+ New collection" in resp.text
    assert "No collections yet — create one to get started." in resp.text
