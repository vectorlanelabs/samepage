"""Slice A chrome tests: the collections hub is the post-login home and the
session/join flows run in a focused "session chrome" (no sidebar, no topbar
nav, no site footer).

Covers: signed-in "/" redirects to the hub; the hub renders greeting, per-group
collection rows with last-session labels, the kept-picks strip, the topbar
avatar, and the mobile sign-out; session pages (join/lobby/completed/429) never
render the site footer or app-shell nav; join screens carry the session-brand
wordmark.
"""

from __future__ import annotations

from datetime import UTC, datetime

from conftest import stamp_session
from sqlalchemy import select

from app.models import Account, Batch, BatchItem, Collection, Group, Item
from app.models import (
    Session as VotingSession,
)

_seq = 0


def _next_code() -> str:
    global _seq
    _seq += 1
    return f"chr-{_seq:04d}"


def _get_or_make_account(db_session, email: str, display_name: str | None = None) -> Account:
    account = db_session.scalar(select(Account).where(Account.email == email))
    if account is not None:
        return account
    account = Account(email=email, display_name=display_name or email.split("@")[0])
    db_session.add(account)
    db_session.commit()
    return account


def _make_group(db_session, name: str = "Test Group", owner_email: str = "host@example.com") -> Group:
    account = _get_or_make_account(db_session, owner_email)
    group = Group(name=name, owner_account_id=account.id)
    db_session.add(group)
    db_session.commit()
    return group


def _make_collection(db_session, group_id: int, name: str = "Meal Planner") -> Collection:
    collection = Collection(group_id=group_id, kind="meal", name=name)
    db_session.add(collection)
    db_session.commit()
    return collection


def _make_session(
    db_session,
    group_id: int,
    host_account_id: int,
    status: str = "lobby",
    collection_id: int | None = None,
) -> VotingSession:
    session = VotingSession(
        code=_next_code(),
        status=status,
        group_id=group_id,
        host_account_id=host_account_id,
        collection_id=collection_id,
    )
    db_session.add(session)
    db_session.commit()
    return session


def _login(client, db_session, email: str) -> None:
    account = db_session.scalar(select(Account).where(Account.email == email))
    stamp_session(client, account)


# --- Non-session chrome: the signed-in app shell on the hub ---------------


def test_hub_renders_app_shell_and_mobile_signout(client, db_session):
    """The hub (post-login home) uses the full app shell: sidebar nav, topbar
    avatar, site footer — plus the mobile-only .hub-signout form."""
    host = _get_or_make_account(db_session, "host@example.com", "Host")
    group = _make_group(db_session, "Household", host.email)
    _make_collection(db_session, group.id)
    _login(client, db_session, host.email)

    body = client.get("/collections").text
    assert 'class="shell"' in body  # non-session shell
    assert 'class="sidebar"' in body  # signed-in sidebar nav
    # The topbar avatar is the "always leads home" identity chip: a link to
    # the hub (mobile dead-end fix, 2026-08-29 review).
    assert '<a class="topbar-avatar" href="/collections">H</a>' in body
    assert 'href="/privacy"' in body  # site footer stays on non-session pages
    assert 'href="/terms"' in body
    assert 'class="inline-form hub-signout"' in body  # mobile sign-out
    assert "shell--session" not in body


def test_hub_shows_greeting_last_session_label_and_kept_picks(client, db_session):
    """The hub composes the post-login home: time-of-day greeting, per-group
    collection rows with a last-session label, and the most recent completed
    session's kept-picks strip."""
    host = _get_or_make_account(db_session, "host@example.com", "Host")
    group = _make_group(db_session, "Household", host.email)
    collection = _make_collection(db_session, group.id)
    apple = Item(collection_id=collection.id, name="Apple", normalized_name="apple")
    db_session.add(apple)
    db_session.commit()

    complete = _make_session(
        db_session, group.id, host.id, status="complete", collection_id=collection.id
    )
    complete.finished_at = datetime.now(UTC)
    batch = Batch(session_id=complete.id, seq=1, track_label="dinner", status="closed")
    db_session.add(batch)
    db_session.flush()
    db_session.add(
        BatchItem(
            batch_id=batch.id,
            item_id=apple.id,
            ad_hoc_label=None,
            sort_order=0,
            outcome="kept_unanimous",
            yes_count=1,
            no_count=0,
        )
    )
    db_session.commit()

    _login(client, db_session, host.email)
    body = client.get("/collections").text
    assert ", Host" in body  # "Good morning/afternoon/evening, Host"
    assert "Meal Planner" in body
    assert "1 active item" in body
    assert "last session" in body  # per-collection last-session label
    assert "Last session kept 1 pick" in body  # kept-picks strip


def test_hub_kept_picks_are_scoped_to_own_groups(client, db_session):
    """Cross-tenant negative (fix round 2026-08-29): account B's hub must
    never show account A's kept-picks strip or last-session labels — and B's
    hub must not change when A's session completes."""
    # Account A: a group + collection, with a session that completes later.
    host = _get_or_make_account(db_session, "host@example.com", "Host")
    group = _make_group(db_session, "Household", host.email)
    collection = _make_collection(db_session, group.id)
    apple = Item(collection_id=collection.id, name="Apple", normalized_name="apple")
    db_session.add(apple)
    db_session.commit()
    session = _make_session(db_session, group.id, host.id)  # lobby, not complete

    # Account B: its own group, no overlap with A's.
    stranger = _get_or_make_account(db_session, "stranger@example.com", "Stranger")
    _make_group(db_session, "Their House", stranger.email)

    _login(client, db_session, stranger.email)
    before = client.get("/collections").text
    assert "No collections yet" in before  # B's own hub renders (empty state)
    assert "Last session kept" not in before  # nothing from A
    assert "last session" not in before  # no last-session label from A

    # A's session completes with a kept pick...
    session.status = "complete"
    session.finished_at = datetime.now(UTC)
    batch = Batch(session_id=session.id, seq=1, track_label="dinner", status="closed")
    db_session.add(batch)
    db_session.flush()
    db_session.add(
        BatchItem(
            batch_id=batch.id,
            item_id=apple.id,
            ad_hoc_label=None,
            sort_order=0,
            outcome="kept_unanimous",
            yes_count=1,
            no_count=0,
        )
    )
    db_session.commit()

    # ...and B's hub still shows none of it.
    after = client.get("/collections").text
    assert "Last session kept" not in after
    assert "last session" not in after


def test_hub_shows_kept_picks_from_collection_less_group(client, db_session):
    """Fix (2026-08-29 review): the kept-picks strip was scoped to groups that
    HAVE collections, so a completed session in a collection-less group was
    invisible. A completed session in the account's own collection-less group
    MUST show the strip."""
    host = _get_or_make_account(db_session, "host@example.com", "Host")
    group = _make_group(db_session, "Household", host.email)  # no collection
    complete = _make_session(db_session, group.id, host.id, status="complete")
    complete.finished_at = datetime.now(UTC)
    batch = Batch(session_id=complete.id, seq=1, track_label="dinner", status="closed")
    db_session.add(batch)
    db_session.flush()
    db_session.add(
        BatchItem(
            batch_id=batch.id,
            item_id=None,
            ad_hoc_label="Taco night",
            sort_order=0,
            outcome="kept_unanimous",
            yes_count=1,
            no_count=0,
        )
    )
    db_session.commit()

    _login(client, db_session, host.email)
    body = client.get("/collections").text
    assert "No collections yet" in body  # empty state kept for zero collections
    assert "Last session kept 1 pick" in body  # strip from the collection-less group


# --- Session chrome: focused flow, no site chrome --------------------------


def _assert_session_chrome(body: str) -> None:
    assert 'class="shell shell--session"' in body
    assert "class=\"sidebar\"" not in body
    assert 'class="topbar-avatar"' not in body
    assert 'href="/privacy"' not in body
    assert 'href="/terms"' not in body
    assert 'href="/collections"' not in body


def test_join_page_renders_session_chrome(client):
    """GET /join is a session-screen: session-brand wordmark, no site footer,
    no app-shell nav."""
    resp = client.get("/join")
    assert resp.status_code == 200
    body = resp.text
    _assert_session_chrome(body)
    assert 'class="session-brand"' in body
    assert "Join a session" in body


def test_session_join_page_renders_session_chrome(client, db_session):
    """A stranger hitting /s/{code} sees the focused join screen — session-brand,
    no site chrome."""
    host = _get_or_make_account(db_session, "host@example.com", "Host")
    group = _make_group(db_session, "Household", host.email)
    session = _make_session(db_session, group.id, host.id)

    resp = client.get(f"/s/{session.code}")
    assert resp.status_code == 200
    body = resp.text
    _assert_session_chrome(body)
    assert 'class="session-brand"' in body
    assert 'name="display_name"' in body  # the join form, not the app shell


def test_lobby_page_renders_session_chrome(client, db_session):
    """The host's lobby is session chrome too — no site footer or sidebar."""
    host = _get_or_make_account(db_session, "host@example.com", "Host")
    group = _make_group(db_session, "Household", host.email)
    session = _make_session(db_session, group.id, host.id)
    _login(client, db_session, host.email)

    resp = client.get(f"/s/{session.code}")
    assert resp.status_code == 200
    body = resp.text
    _assert_session_chrome(body)
    assert "at the table" in body
    assert "Start voting" in body


def test_completed_session_page_renders_session_chrome(client, db_session):
    """The completion plan (public to anyone with the code) still runs in the
    session chrome — no site footer."""
    host = _get_or_make_account(db_session, "host@example.com", "Host")
    group = _make_group(db_session, "Household", host.email)
    collection = _make_collection(db_session, group.id)
    apple = Item(collection_id=collection.id, name="Apple", normalized_name="apple")
    db_session.add(apple)
    db_session.commit()
    complete = _make_session(
        db_session, group.id, host.id, status="complete", collection_id=collection.id
    )
    complete.finished_at = datetime.now(UTC)
    batch = Batch(session_id=complete.id, seq=1, track_label="dinner", status="closed")
    db_session.add(batch)
    db_session.flush()
    db_session.add(
        BatchItem(
            batch_id=batch.id,
            item_id=apple.id,
            ad_hoc_label=None,
            sort_order=0,
            outcome="kept_unanimous",
            yes_count=1,
            no_count=0,
        )
    )
    db_session.commit()

    resp = client.get(f"/s/{complete.code}")
    assert resp.status_code == 200
    body = resp.text
    _assert_session_chrome(body)
    assert "Your plan" in body


def test_rate_limited_page_renders_session_chrome(client):
    """The join-code 429 page renders in session chrome (its 'Go home' link
    points at the landing, not the app shell)."""
    for _ in range(20):
        assert client.get("/s/ghost-0000").status_code == 404
    resp = client.get("/s/ghost-0000", headers={"accept": "text/html"})
    assert resp.status_code == 429
    body = resp.text
    _assert_session_chrome(body)
    assert "Too many attempts" in body


# --- Guest landing chrome ---------------------------------------------------


def test_guest_landing_keeps_site_footer_and_no_session_brand(client):
    """The signed-out landing is a normal site page: footer present, no
    session-brand wordmark, no app-shell nav."""
    body = client.get("/").text
    assert 'href="/privacy"' in body
    assert 'href="/terms"' in body
    assert 'class="session-brand"' not in body
    assert "class=\"sidebar\"" not in body
    # M8 R4: the guest header is the topbar-inner column (brand + Sign in
    # aligned with .content's min(1080px) column).
    assert 'class="topbar-inner"' in body
