from conftest import stamp_session
from sqlalchemy import select

from app.models import Account, Collection, Group, Item


def _make_account(db_session, email="admin@example.com", display_name="Admin"):
    account = Account(email=email, display_name=display_name)
    db_session.add(account)
    db_session.commit()
    return account


def _login(client, db_session, email="admin@example.com"):
    """Authenticate the TestClient session as the account with `email`."""
    account = db_session.scalar(select(Account).where(Account.email == email))
    stamp_session(client, account)


def test_home_signed_out_shows_no_data(client):
    """Anonymous visitors get a landing state — no counts, no data, just
    sign-in/sign-up links. Earlier versions showed platform-wide item/group
    counts to anyone; that leaked cross-tenant data on a multi-tenant deployment."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Same Page" in resp.text
    assert "Sign in" in resp.text
    # Signed-out is a landing: value prop + join-by-code as the co-star, no
    # app data. (Google SSO — there's no separate password sign-up screen.)
    assert "Decide together" in resp.text
    assert "Joining someone's session?" in resp.text
    assert "stat-count" not in resp.text  # no count data rendered at all


def test_home_hero_has_single_host_cta(client):
    """M8 R4: the hero has exactly one CTA — Host a session → /sessions/new.
    The old secondary hero "Sign in" button is gone (signed-out visitors keep
    the topbar Sign in; /sessions/new 401s to /login?next=… for them)."""
    body = client.get("/").text
    assert body.count('href="/sessions/new"') == 1
    hero = body.split('class="hero-cta"')[1].split("</div>")[0]
    assert 'href="/sessions/new"' in hero
    assert "Sign in" not in hero


def test_home_signed_in_redirects_to_hub(client, db_session):
    """The collections hub is the post-login home: a signed-in visitor to "/"
    is 303'd to /collections — the landing page never renders app data to
    anyone (the redirect also closes the old signed-in-dashboard leak)."""
    _make_account(db_session)
    _login(client, db_session)
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/collections"


def test_hub_shows_own_collections(client, post, db_session):
    account = _make_account(db_session)
    group = Group(name="Test Group", owner_account_id=account.id)
    db_session.add(group)
    db_session.commit()
    collection = Collection(group_id=group.id, kind="meal", name="Meal Planner")
    db_session.add(collection)
    db_session.commit()
    db_session.add(Item(collection_id=collection.id, name="Tacos", normalized_name="tacos"))
    db_session.commit()

    _login(client, db_session)
    resp = client.get("/collections")
    assert resp.status_code == 200
    # The hub lists the account's own collections with their active counts.
    assert "Test Group" in resp.text
    assert "Meal Planner" in resp.text
    assert "1 active item" in resp.text
    assert "Meal Library" not in resp.text  # meal framing stays inside the collection


def test_hub_never_shows_another_groups_collections(client, post, db_session):
    """Regression: the post-login hub must be scoped to the signed-in account's
    own groups — never another group's collections on the same deployment."""
    other_account = _make_account(db_session, email="other@example.com", display_name="Other")
    other_group = Group(name="Other Household", owner_account_id=other_account.id)
    db_session.add(other_group)
    db_session.commit()
    other_collection = Collection(group_id=other_group.id, kind="meal", name="Meal Planner")
    db_session.add(other_collection)
    db_session.commit()
    for name in ("A", "B", "C"):
        db_session.add(
            Item(collection_id=other_collection.id, name=name, normalized_name=name.lower())
        )
    db_session.commit()

    # A second account with no groups of its own.
    _make_account(db_session)
    _login(client, db_session)
    resp = client.get("/collections")
    assert resp.status_code == 200
    assert "Other Household" not in resp.text
    assert "Meal Planner" not in resp.text
    assert "No collections yet" in resp.text


def test_signed_out_nav_hides_app_links(client):
    """A signed-out visitor sees no app nav they can't use — the Collections
    and Groups links (both 401-gated) only render when signed in."""
    body = client.get("/").text
    assert 'href="/collections"' not in body
    assert 'href="/groups"' not in body


def test_signed_in_nav_shows_app_links(client, db_session):
    """The signed-in app shell (on the hub, the post-login home) carries the
    sidebar nav — Collections and Groups — plus the sign-out form."""
    _make_account(db_session)
    _login(client, db_session)
    body = client.get("/collections").text
    assert 'href="/collections"' in body
    assert 'href="/groups"' in body
    assert '<form method="post" action="/logout">' in body
