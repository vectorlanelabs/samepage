"""Session routes + code generation (M3b): create, join-by-code (no account),
live lobby, roster polling, host start/remove, and the make_code helper.

Every POST that mutates goes through the ``post`` fixture (same-origin Origin
header — the origin-check middleware is fail-closed). The host is stamped via
``stamp_session`` (conftest) everywhere a signed-in account is needed; join
tests exercise the signed-OUT path (codes are the join surface, per plan §2).
"""

from __future__ import annotations

import base64
import json
import random

import pytest
from conftest import stamp_session
from itsdangerous import TimestampSigner
from sqlalchemy import func, select

from app.models import (
    Account,
    Batch,
    BatchItem,
    BatchResponse,
    Collection,
    Group,
    Item,
    ItemTag,
    MealDetail,
    SessionParticipant,
    SessionTarget,
    Tag,
)
from app.models import (
    Session as VotingSession,
)
from app.session_logic import BATCH_SIZE, WORDLIST, make_code

_seq = 0


def _next_code() -> str:
    global _seq
    _seq += 1
    return f"test-{_seq:04d}"


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


def _session_count(db_session) -> int:
    return db_session.scalar(select(func.count()).select_from(VotingSession)) or 0


def _participant_count(db_session) -> int:
    return db_session.scalar(select(func.count()).select_from(SessionParticipant)) or 0


def _make_item(
    db_session, collection_id: int, name: str, type: str = "dinner", recipe_text: str = ""
) -> Item:
    item = Item(collection_id=collection_id, name=name, normalized_name=name.casefold())
    db_session.add(item)
    db_session.flush()
    detail = MealDetail(item_id=item.id, type=type)
    if recipe_text:
        detail.recipe_text = recipe_text
    db_session.add(detail)
    db_session.commit()
    return item


def _stamp_participant(client, participant_id: int) -> None:
    """Point the client's signed session cookie at a participant row (like
    conftest.stamp_session does for accounts). Clears the jar first — a real
    browser holds ONE session cookie, but the test client accumulates a second
    'session' entry (server-set + manually-set) that httpx then can't
    disambiguate, so the switch silently wouldn't reach the server."""
    client.cookies.clear()
    payload = base64.b64encode(json.dumps({"participant_id": participant_id}).encode())
    client.cookies.set("session", TimestampSigner("test-secret-for-tests").sign(payload).decode())


def _open_batch(db_session, session_id: int) -> Batch | None:
    return db_session.scalar(
        select(Batch)
        .where((Batch.session_id == session_id) & (Batch.status == "open"))
        .order_by(Batch.seq)
    )


def _batch_items(db_session, batch_id: int) -> list[BatchItem]:
    return list(
        db_session.scalars(
            select(BatchItem)
            .where(BatchItem.batch_id == batch_id)
            .order_by(BatchItem.sort_order, BatchItem.id)
        ).all()
    )


def _item_names(db_session, batch_items: list[BatchItem]) -> list[str]:
    ids = [bi.item_id for bi in batch_items]
    by_id = {i.id: i.name for i in db_session.scalars(select(Item).where(Item.id.in_(ids))).all()}
    return [by_id[i] for i in ids]


# ---------------------------------------------------------------------------
# make_code (pure helper)
# ---------------------------------------------------------------------------


def test_wordlist_is_32_unique_lowercase_words():
    assert len(WORDLIST) == 32
    assert len(set(WORDLIST)) == 32
    assert all(w.isalpha() and w == w.lower() for w in WORDLIST)


def test_make_code_seeded_deterministic():
    """A seeded Random(0) always yields the same code: word-nnnn."""
    code = make_code(set(), random.Random(0))
    word, num = code.rsplit("-", 1)
    assert word in WORDLIST
    assert num.isdigit() and len(num) == 4
    assert code == "quartz-6890"


def test_make_code_retries_on_collision():
    """Pre-populating existing with the first code the seed produces forces a
    retry — a different, unused code comes back."""
    first = make_code(set(), random.Random(0))
    existing = {first}
    code = make_code(existing, random.Random(0))
    assert code != first
    assert code not in existing


def test_make_code_exhaustion_raises():
    """Every possible word-nnnn code already taken → RuntimeError after the
    retry budget is spent, never an infinite loop."""
    all_codes = {f"{w}-{n:04d}" for w in WORDLIST for n in range(10000)}
    with pytest.raises(RuntimeError):
        make_code(all_codes, random.Random(0))


# ---------------------------------------------------------------------------
# GET /sessions/new
# ---------------------------------------------------------------------------


def test_new_session_page_requires_signin(client):
    resp = client.get(
        "/sessions/new", headers={"accept": "text/html"}, follow_redirects=False
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login?next=%2Fsessions%2Fnew"


def test_new_session_page_no_groups(client, db_session):
    host = _get_or_make_account(db_session, "host@example.com", "Host")
    _login(client, db_session, host.email)
    resp = client.get("/sessions/new")
    assert resp.status_code == 200
    assert "Create a group first." in resp.text
    assert 'name="group_id"' not in resp.text  # no form without groups


def test_new_session_page_lists_groups_and_collections(client, db_session):
    host = _get_or_make_account(db_session, "host@example.com", "Host")
    group = _make_group(db_session, "Household", host.email)
    _make_collection(db_session, group.id, "Weeknight dinners")
    _login(client, db_session, host.email)
    resp = client.get("/sessions/new")
    assert resp.status_code == 200
    assert "Host a session" in resp.text
    assert "Household" in resp.text
    assert "Ad hoc (no collection)" in resp.text
    assert "Weeknight dinners" in resp.text
    assert 'name="group_id"' in resp.text
    assert 'name="collection_id"' in resp.text
    assert 'name="dinners"' in resp.text
    assert 'name="lunches"' in resp.text
    assert 'name="picks"' in resp.text
    assert 'href="/collections"' in resp.text  # back link


# ---------------------------------------------------------------------------
# POST /sessions
# ---------------------------------------------------------------------------


def test_create_session_requires_signin(client, post, db_session):
    resp = post(
        "/sessions",
        data={"group_id": "1", "collection_id": "", "dinners": "3", "lunches": "0", "picks": "3"},
    )
    assert resp.status_code == 401
    assert _session_count(db_session) == 0


def test_create_session_happy_path_meal_collection(client, post, db_session):
    host = _get_or_make_account(db_session, "host@example.com", "Host")
    group = _make_group(db_session, "Household", host.email)
    collection = _make_collection(db_session, group.id, "Weeknight dinners")
    _login(client, db_session, host.email)

    resp = post(
        "/sessions",
        data={
            "group_id": str(group.id),
            "collection_id": str(collection.id),
            "dinners": "2",
            "lunches": "1",
            "picks": "3",  # ignored for a collection session
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    session = db_session.scalar(select(VotingSession).order_by(VotingSession.id.desc()))
    assert session is not None
    assert session.status == "lobby"
    assert session.host_account_id == host.id
    assert session.group_id == group.id
    assert session.collection_id == collection.id
    assert resp.headers["location"] == f"/s/{session.code}"

    targets = db_session.scalars(
        select(SessionTarget)
        .where(SessionTarget.session_id == session.id)
        .order_by(SessionTarget.track_label)
    ).all()
    assert [(t.track_label, t.target_count) for t in targets] == [("dinner", 2), ("lunch", 1)]

    # The host lands in the lobby.
    lobby = client.get(f"/s/{session.code}")
    assert lobby.status_code == 200
    assert "Weeknight dinners" in lobby.text
    assert "Waiting room" in lobby.text
    assert "Start voting" in lobby.text
    assert session.code in lobby.text
    assert f'hx-get="/s/{session.code}/roster"' in lobby.text


def test_create_session_cross_tenant_group_404(client, post, db_session):
    """Another account's group id → 404 with no Session rows — the status code
    must not double as an oracle for which group ids exist."""
    _get_or_make_account(db_session, "other@example.com", "Other")
    other_group = _make_group(db_session, "Other Household", "other@example.com")
    host = _get_or_make_account(db_session, "host@example.com", "Host")
    _make_group(db_session, "Own Household", host.email)
    _login(client, db_session, host.email)

    resp = post(
        "/sessions",
        data={
            "group_id": str(other_group.id),
            "collection_id": "",
            "dinners": "3",
            "lunches": "0",
            "picks": "3",
        },
    )
    assert resp.status_code == 404
    assert _session_count(db_session) == 0
    assert db_session.scalar(select(func.count()).select_from(SessionTarget)) == 0


def test_create_session_collection_not_in_group_404(client, post, db_session):
    """A collection that belongs to a different group than the posted group_id
    is 404 — collection.group_id must equal group_id."""
    host = _get_or_make_account(db_session, "host@example.com", "Host")
    group = _make_group(db_session, "Household", host.email)
    other_group = _make_group(db_session, "Other Household", "other@example.com")
    foreign_collection = _make_collection(db_session, other_group.id, "Their meals")
    _login(client, db_session, host.email)

    resp = post(
        "/sessions",
        data={
            "group_id": str(group.id),
            "collection_id": str(foreign_collection.id),
            "dinners": "3",
            "lunches": "0",
            "picks": "3",
        },
    )
    assert resp.status_code == 404
    assert _session_count(db_session) == 0


def test_create_session_no_targets_400(client, post, db_session):
    host = _get_or_make_account(db_session, "host@example.com", "Host")
    group = _make_group(db_session, "Household", host.email)
    collection = _make_collection(db_session, group.id)
    _login(client, db_session, host.email)

    resp = post(
        "/sessions",
        data={
            "group_id": str(group.id),
            "collection_id": str(collection.id),
            "dinners": "0",
            "lunches": "0",
            "picks": "3",
        },
    )
    assert resp.status_code == 400
    assert "Set at least one target." in resp.text
    assert _session_count(db_session) == 0


def test_create_session_negative_targets_400(client, post, db_session):
    """Negative counts create no positive rows → same 400 as nothing set."""
    host = _get_or_make_account(db_session, "host@example.com", "Host")
    group = _make_group(db_session, "Household", host.email)
    collection = _make_collection(db_session, group.id)
    _login(client, db_session, host.email)

    resp = post(
        "/sessions",
        data={
            "group_id": str(group.id),
            "collection_id": str(collection.id),
            "dinners": "-1",
            "lunches": "0",
            "picks": "3",
        },
    )
    assert resp.status_code == 400
    assert "Set at least one target." in resp.text
    assert _session_count(db_session) == 0


def test_create_session_ad_hoc(client, post, db_session):
    host = _get_or_make_account(db_session, "host@example.com", "Host")
    group = _make_group(db_session, "Household", host.email)
    _login(client, db_session, host.email)

    resp = post(
        "/sessions",
        data={
            "group_id": str(group.id),
            "collection_id": "",
            "dinners": "3",
            "lunches": "0",
            "picks": "4",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    session = db_session.scalar(select(VotingSession).order_by(VotingSession.id.desc()))
    assert session is not None
    assert session.collection_id is None
    targets = db_session.scalars(
        select(SessionTarget).where(SessionTarget.session_id == session.id)
    ).all()
    assert [(t.track_label, t.target_count) for t in targets] == [("picks", 4)]
    assert resp.headers["location"] == f"/s/{session.code}"

    lobby = client.get(f"/s/{session.code}")
    assert lobby.status_code == 200
    assert "Ad hoc session" in lobby.text


def test_create_session_ad_hoc_zero_picks_400(client, post, db_session):
    host = _get_or_make_account(db_session, "host@example.com", "Host")
    group = _make_group(db_session, "Household", host.email)
    _login(client, db_session, host.email)

    resp = post(
        "/sessions",
        data={
            "group_id": str(group.id),
            "collection_id": "",
            "dinners": "0",
            "lunches": "0",
            "picks": "0",
        },
    )
    assert resp.status_code == 400
    assert _session_count(db_session) == 0


# ---------------------------------------------------------------------------
# Join flow (no account required)
# ---------------------------------------------------------------------------


def test_join_page_get(client):
    resp = client.get("/join")
    assert resp.status_code == 200
    assert 'name="code"' in resp.text
    assert "Join" in resp.text


def test_join_page_with_code_redirects(client):
    resp = client.get("/join?code=Amber-1234", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/s/amber-1234"


def test_signed_out_join_flow(client, post, db_session):
    host = _get_or_make_account(db_session, "host@example.com", "Host")
    group = _make_group(db_session, "Household", host.email)
    _login(client, db_session, host.email)
    resp = post(
        "/sessions",
        data={"group_id": str(group.id), "collection_id": "", "dinners": "0", "lunches": "0", "picks": "3"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    session = db_session.scalar(select(VotingSession).order_by(VotingSession.id.desc()))
    assert session is not None
    client.cookies.clear()  # signed out now

    # Stranger hits the code → join page, no account required.
    page = client.get(f"/s/{session.code}")
    assert page.status_code == 200
    assert session.code in page.text
    assert 'class="sp-code"' in page.text
    assert 'name="display_name"' in page.text
    assert "Waiting room" not in page.text

    resp = post(f"/s/{session.code}/join", data={"display_name": "  Sam  "}, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/s/{session.code}"

    participant = db_session.scalar(
        select(SessionParticipant).where(SessionParticipant.session_id == session.id)
    )
    assert participant is not None
    assert participant.account_id is None
    assert participant.display_name == "Sam"  # stripped

    # The lobby now lists them, with no host controls.
    lobby = client.get(f"/s/{session.code}")
    assert lobby.status_code == 200
    assert "Sam" in lobby.text
    assert "Waiting for the host to start…" in lobby.text
    assert "Start voting" not in lobby.text


def test_join_blank_name_400(client, post, db_session):
    host = _get_or_make_account(db_session, "host@example.com", "Host")
    group = _make_group(db_session, "Household", host.email)
    session = _make_session(db_session, group.id, host.id)

    resp = post(f"/s/{session.code}/join", data={"display_name": "   "})
    assert resp.status_code == 400
    assert "Display name is required." in resp.text
    assert _participant_count(db_session) == 0


def test_join_signed_in_prefills_name_but_override_wins(client, post, db_session):
    host = _get_or_make_account(db_session, "host@example.com", "Host")
    group = _make_group(db_session, "Household", host.email)
    session = _make_session(db_session, group.id, host.id)
    viewer = _get_or_make_account(db_session, "viewer@example.com", "Viewer")
    _login(client, db_session, viewer.email)

    # Pre-filled with the signed-in account's display name, still editable.
    page = client.get(f"/s/{session.code}")
    assert page.status_code == 200
    assert 'value="Viewer"' in page.text

    resp = post(f"/s/{session.code}/join", data={"display_name": "Zoe"}, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/s/{session.code}"
    participant = db_session.scalar(
        select(SessionParticipant).where(SessionParticipant.session_id == session.id)
    )
    assert participant is not None
    assert participant.account_id == viewer.id
    assert participant.display_name == "Zoe"

    lobby = client.get(f"/s/{session.code}")
    assert "Zoe" in lobby.text
    assert "you" in lobby.text


def test_voting_session_join_is_waiting_state(client, post, db_session):
    """§5.6: no mid-vote joins — a visitor hitting a voting session sees the
    waiting state, not a ballot; the join POST is refused (no row created)."""
    host = _get_or_make_account(db_session, "host@example.com", "Host")
    group = _make_group(db_session, "Household", host.email)
    session = _make_session(db_session, group.id, host.id, status="voting")

    page = client.get(f"/s/{session.code}")
    assert page.status_code == 200
    assert "Voting has already started — ask the host." in page.text
    assert 'name="display_name"' not in page.text

    resp = post(f"/s/{session.code}/join", data={"display_name": "Sam"})
    assert resp.status_code == 200
    assert _participant_count(db_session) == 0


@pytest.mark.parametrize("status", ["complete", "expired"])
def test_ended_session_shows_ended_page_and_refuses_join(client, post, db_session, status):
    host = _get_or_make_account(db_session, "host@example.com", "Host")
    group = _make_group(db_session, "Household", host.email)
    session = _make_session(db_session, group.id, host.id, status=status)

    page = client.get(f"/s/{session.code}")
    assert page.status_code == 200
    assert "This session has ended." in page.text

    resp = post(f"/s/{session.code}/join", data={"display_name": "Sam"})
    assert resp.status_code == 200
    assert "This session has ended." in resp.text
    assert _participant_count(db_session) == 0


def test_unknown_code_404(client):
    assert client.get("/s/ghost-0000").status_code == 404
    assert client.get("/s/ghost-0000/roster").status_code == 404


# ---------------------------------------------------------------------------
# Roster polling
# ---------------------------------------------------------------------------


def test_roster_partial_remove_buttons_only_for_host(client, db_session):
    host = _get_or_make_account(db_session, "host@example.com", "Host")
    group = _make_group(db_session, "Household", host.email)
    session = _make_session(db_session, group.id, host.id)
    sam = SessionParticipant(session_id=session.id, account_id=None, display_name="Sam")
    host_row = SessionParticipant(
        session_id=session.id, account_id=host.id, display_name="Host Person"
    )
    db_session.add_all([sam, host_row])
    db_session.commit()

    # Signed-out viewer: rows + count, no Remove buttons, host row chip shown.
    resp = client.get(f"/s/{session.code}/roster")
    assert resp.status_code == 200
    assert "Sam" in resp.text
    assert "Host Person" in resp.text
    assert "2 joined" in resp.text
    assert "Remove" not in resp.text
    assert "host" in resp.text

    # Host viewer: exactly one Remove button — for Sam, never the host row.
    _login(client, db_session, host.email)
    resp = client.get(f"/s/{session.code}/roster")
    assert resp.status_code == 200
    assert resp.text.count("Remove") == 1


# ---------------------------------------------------------------------------
# Host actions
# ---------------------------------------------------------------------------


def test_start_voting_requires_signin(client, post, db_session):
    host = _get_or_make_account(db_session, "host@example.com", "Host")
    group = _make_group(db_session, "Household", host.email)
    session = _make_session(db_session, group.id, host.id)
    resp = post(f"/s/{session.code}/start")
    assert resp.status_code == 401
    db_session.refresh(session)
    assert session.status == "lobby"


def test_start_voting_unknown_code_404(client, post, db_session):
    host = _get_or_make_account(db_session, "host@example.com", "Host")
    _login(client, db_session, host.email)
    resp = post("/s/ghost-0000/start")
    assert resp.status_code == 404


def test_start_voting_non_host_403(client, post, db_session):
    host = _get_or_make_account(db_session, "host@example.com", "Host")
    group = _make_group(db_session, "Household", host.email)
    session = _make_session(db_session, group.id, host.id)
    other = _get_or_make_account(db_session, "other@example.com", "Other")
    _login(client, db_session, other.email)
    resp = post(f"/s/{session.code}/start")
    assert resp.status_code == 403
    db_session.refresh(session)
    assert session.status == "lobby"


def test_start_voting_host_sets_voting_and_is_idempotent(client, post, db_session):
    host = _get_or_make_account(db_session, "host@example.com", "Host")
    group = _make_group(db_session, "Household", host.email)
    session = _make_session(db_session, group.id, host.id)
    _login(client, db_session, host.email)

    resp = post(f"/s/{session.code}/start", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/s/{session.code}"
    db_session.refresh(session)
    assert session.status == "voting"

    # Idempotent: a second identical POST applies once, never an error.
    resp = post(f"/s/{session.code}/start", follow_redirects=False)
    assert resp.status_code == 303
    db_session.refresh(session)
    assert session.status == "voting"

    # This session is ad hoc (no collection): voting shows the coming-soon
    # placeholder, not a ballot, and no batch was assembled.
    page = client.get(f"/s/{session.code}")
    assert page.status_code == 200
    assert "Ad hoc voting is coming soon — options entry lands in a later release." in page.text


def test_remove_participant_requires_signin(client, post, db_session):
    host = _get_or_make_account(db_session, "host@example.com", "Host")
    group = _make_group(db_session, "Household", host.email)
    session = _make_session(db_session, group.id, host.id)
    sam = SessionParticipant(session_id=session.id, account_id=None, display_name="Sam")
    db_session.add(sam)
    db_session.commit()
    resp = post(f"/s/{session.code}/participants/{sam.id}/remove")
    assert resp.status_code == 401


def test_remove_participant_host_removes_row(client, post, db_session):
    host = _get_or_make_account(db_session, "host@example.com", "Host")
    group = _make_group(db_session, "Household", host.email)
    session = _make_session(db_session, group.id, host.id)
    sam = SessionParticipant(session_id=session.id, account_id=None, display_name="Sam")
    db_session.add(sam)
    db_session.commit()
    sam_id = sam.id  # capture before the row is deleted by the route
    _login(client, db_session, host.email)

    resp = post(f"/s/{session.code}/participants/{sam_id}/remove", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/s/{session.code}"
    # Query the DB directly (the identity map still holds the deleted row).
    remaining = db_session.scalar(
        select(func.count())
        .select_from(SessionParticipant)
        .where(SessionParticipant.id == sam_id)
    )
    assert remaining == 0

    page = client.get(f"/s/{session.code}/roster")
    assert "Sam" not in page.text
    assert "Nobody has joined yet" in page.text


def test_remove_participant_non_host_403(client, post, db_session):
    host = _get_or_make_account(db_session, "host@example.com", "Host")
    group = _make_group(db_session, "Household", host.email)
    session = _make_session(db_session, group.id, host.id)
    sam = SessionParticipant(session_id=session.id, account_id=None, display_name="Sam")
    db_session.add(sam)
    db_session.commit()
    other = _get_or_make_account(db_session, "other@example.com", "Other")
    _login(client, db_session, other.email)

    resp = post(f"/s/{session.code}/participants/{sam.id}/remove")
    assert resp.status_code == 403
    assert db_session.get(SessionParticipant, sam.id) is not None


def test_remove_participant_after_start_400(client, post, db_session):
    """§5.6: removal is only allowed while no batch is open (lobby)."""
    host = _get_or_make_account(db_session, "host@example.com", "Host")
    group = _make_group(db_session, "Household", host.email)
    session = _make_session(db_session, group.id, host.id, status="voting")
    sam = SessionParticipant(session_id=session.id, account_id=None, display_name="Sam")
    db_session.add(sam)
    db_session.commit()
    _login(client, db_session, host.email)

    resp = post(f"/s/{session.code}/participants/{sam.id}/remove")
    assert resp.status_code == 400
    assert "Can't remove participants after voting starts" in resp.text
    assert db_session.get(SessionParticipant, sam.id) is not None


def test_remove_host_own_row_400(client, post, db_session):
    host = _get_or_make_account(db_session, "host@example.com", "Host")
    group = _make_group(db_session, "Household", host.email)
    session = _make_session(db_session, group.id, host.id)
    host_row = SessionParticipant(
        session_id=session.id, account_id=host.id, display_name="Host Person"
    )
    db_session.add(host_row)
    db_session.commit()
    _login(client, db_session, host.email)

    resp = post(f"/s/{session.code}/participants/{host_row.id}/remove")
    assert resp.status_code == 400
    assert "The host can't be removed" in resp.text
    assert db_session.get(SessionParticipant, host_row.id) is not None


def test_remove_unknown_participant_404(client, post, db_session):
    host = _get_or_make_account(db_session, "host@example.com", "Host")
    group = _make_group(db_session, "Household", host.email)
    session = _make_session(db_session, group.id, host.id)
    _login(client, db_session, host.email)
    resp = post(f"/s/{session.code}/participants/999999/remove")
    assert resp.status_code == 404


def test_remove_participant_from_other_session_404(client, post, db_session):
    """A participant id from a DIFFERENT session is 404 for this session's
    remove route — removal is scoped to the session in the URL."""
    host = _get_or_make_account(db_session, "host@example.com", "Host")
    group = _make_group(db_session, "Household", host.email)
    session_a = _make_session(db_session, group.id, host.id)
    session_b = _make_session(db_session, group.id, host.id)
    sam = SessionParticipant(session_id=session_a.id, account_id=None, display_name="Sam")
    db_session.add(sam)
    db_session.commit()
    _login(client, db_session, host.email)

    resp = post(f"/s/{session_b.code}/participants/{sam.id}/remove")
    assert resp.status_code == 404
    assert db_session.get(SessionParticipant, sam.id) is not None


# ---------------------------------------------------------------------------
# M3c: batch assembly + the voting flow
# ---------------------------------------------------------------------------


def _make_voting_setup(
    db_session,
    host_email: str = "host@example.com",
    item_specs: list[tuple[str, str]] | None = None,
    targets: list[tuple[str, int]] | None = None,
) -> tuple[VotingSession, Collection, Group]:
    """Host + group + collection with items, and a lobby session with targets."""
    host = _get_or_make_account(db_session, host_email, "Host")
    group = _make_group(db_session, "Household", host.email)
    collection = _make_collection(db_session, group.id, "Meal Planner")
    for name, type in item_specs or [("Apple", "dinner")]:
        _make_item(db_session, collection.id, name, type=type)
    session = _make_session(db_session, group.id, host.id, collection_id=collection.id)
    for track, count in targets or [("dinner", 1)]:
        db_session.add(
            SessionTarget(session_id=session.id, track_label=track, target_count=count)
        )
    db_session.commit()
    return session, collection, group


def test_start_assembles_first_batch(client, post, db_session):
    """Starting a collection-backed session with N dinner items assembles batch
    #1: seq 1, track 'dinner', min(N, BATCH_SIZE) items in normalized_name
    order; 'both' items count for dinner, 'lunch'-only items don't."""
    host = _get_or_make_account(db_session, "host@example.com", "Host")
    group = _make_group(db_session, "Household", host.email)
    collection = _make_collection(db_session, group.id)
    names = [
        "Zebra", "Apple", "Mango", "Banana", "Cherry", "Date", "Fig", "Grape",
        "Kiwi", "Lemon", "Melon", "Nectarine", "Olive", "Papaya", "Quince",
        "Raspberry", "Strawberry", "Tangerine", "Ugli", "Vanilla",
    ]
    for name in names:
        _make_item(db_session, collection.id, name, type="dinner")
    _make_item(db_session, collection.id, "Both Dish", type="both")
    _make_item(db_session, collection.id, "Lunch Only", type="lunch")
    session = _make_session(db_session, group.id, host.id, collection_id=collection.id)
    db_session.add(SessionTarget(session_id=session.id, track_label="dinner", target_count=3))
    db_session.commit()
    _login(client, db_session, host.email)

    resp = post(f"/s/{session.code}/start", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/s/{session.code}"
    db_session.refresh(session)
    assert session.status == "voting"

    batch = _open_batch(db_session, session.id)
    assert batch is not None
    assert batch.seq == 1
    assert batch.track_label == "dinner"
    assert batch.status == "open"
    items = _batch_items(db_session, batch.id)
    assert len(items) == min(20, BATCH_SIZE) == 15
    assert all(bi.ad_hoc_label is None for bi in items)
    assert [bi.sort_order for bi in items] == list(range(15))
    names_in_batch = _item_names(db_session, items)
    assert names_in_batch == sorted(names + ["Both Dish"])[:15]
    assert "Lunch Only" not in names_in_batch


def test_start_empty_pool_400_stays_lobby(client, post, db_session):
    """A collection with no items for the first track refuses the start: 400,
    session stays 'lobby', no batch created."""
    host = _get_or_make_account(db_session, "host@example.com", "Host")
    group = _make_group(db_session, "Household", host.email)
    collection = _make_collection(db_session, group.id)
    _make_item(db_session, collection.id, "Lunch Only", type="lunch")
    session = _make_session(db_session, group.id, host.id, collection_id=collection.id)
    db_session.add(SessionTarget(session_id=session.id, track_label="dinner", target_count=3))
    db_session.commit()
    _login(client, db_session, host.email)

    resp = post(f"/s/{session.code}/start")
    assert resp.status_code == 400
    assert "No items available for the dinner track — add items to this collection first." in resp.text
    db_session.refresh(session)
    assert session.status == "lobby"
    assert _open_batch(db_session, session.id) is None


def test_start_picks_lunch_when_dinner_target_zero(client, post, db_session):
    """The first track is 'dinner' then 'lunch' then others alphabetically; a
    session whose only positive target is lunch assembles a 'lunch' batch."""
    session, _, _ = _make_voting_setup(
        db_session,
        item_specs=[("Pasta", "dinner"), ("Salad", "lunch")],
        targets=[("lunch", 2)],  # dinner target 0 writes no row
    )
    _login(client, db_session, "host@example.com")

    resp = post(f"/s/{session.code}/start", follow_redirects=False)
    assert resp.status_code == 303
    batch = _open_batch(db_session, session.id)
    assert batch is not None
    assert batch.track_label == "lunch"
    assert _item_names(db_session, _batch_items(db_session, batch.id)) == ["Salad"]


def test_start_twice_creates_one_batch(client, post, db_session):
    """Idempotent start: a second POST /start on an already-voting session does
    not assemble a second batch."""
    session, _, _ = _make_voting_setup(
        db_session,
        item_specs=[("Apple", "dinner"), ("Banana", "dinner")],
        targets=[("dinner", 1)],
    )
    _login(client, db_session, "host@example.com")

    resp = post(f"/s/{session.code}/start", follow_redirects=False)
    assert resp.status_code == 303
    resp = post(f"/s/{session.code}/start", follow_redirects=False)
    assert resp.status_code == 303

    batches = db_session.scalars(select(Batch).where(Batch.session_id == session.id)).all()
    assert len(batches) == 1
    assert batches[0].status == "open"


def test_voting_card_progresses_through_options(client, post, db_session):
    """A joined participant sees one option at a time ('Option 1 of N'), with
    type label + tags, and advances to option 2 after voting."""
    host = _get_or_make_account(db_session, "host@example.com", "Host")
    group = _make_group(db_session, "Household", host.email)
    collection = _make_collection(db_session, group.id)
    apple = _make_item(db_session, collection.id, "Apple", type="dinner", recipe_text="Boil water.")
    _make_item(db_session, collection.id, "Banana", type="dinner")
    _make_item(db_session, collection.id, "Cherry", type="dinner")
    tag = Tag(group_id=group.id, name="quick")
    db_session.add(tag)
    db_session.flush()
    db_session.add(ItemTag(item_id=apple.id, tag_id=tag.id))
    session = _make_session(db_session, group.id, host.id, collection_id=collection.id)
    db_session.add(SessionTarget(session_id=session.id, track_label="dinner", target_count=1))
    db_session.commit()
    _login(client, db_session, host.email)
    resp = post(f"/s/{session.code}/join", data={"display_name": "Sam"}, follow_redirects=False)
    assert resp.status_code == 303
    resp = post(f"/s/{session.code}/start", follow_redirects=False)
    assert resp.status_code == 303

    page = client.get(f"/s/{session.code}")
    assert page.status_code == 200
    assert "Option 1 of 3" in page.text
    assert "Apple" in page.text
    assert "Dinner" in page.text
    assert "quick" in page.text
    assert f'href="/collections/{collection.id}/items/{apple.id}"' in page.text
    assert 'name="batch_item_id"' in page.text
    assert 'name="choice"' in page.text

    first = _batch_items(db_session, _open_batch(db_session, session.id).id)[0]
    resp = post(
        f"/s/{session.code}/vote",
        data={"batch_item_id": str(first.id), "choice": "yes"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/s/{session.code}"

    page = client.get(f"/s/{session.code}")
    assert page.status_code == 200
    assert "Option 2 of 3" in page.text
    assert "Banana" in page.text


def test_vote_records_once_and_first_vote_stands(client, post, db_session):
    """POST /vote records one batch_response; a re-submit (yes or no) leaves
    the first choice unchanged and adds no row."""
    session, _, _ = _make_voting_setup(
        db_session,
        item_specs=[("Apple", "dinner"), ("Banana", "dinner")],
        targets=[("dinner", 1)],
    )
    _login(client, db_session, "host@example.com")
    post(f"/s/{session.code}/join", data={"display_name": "Sam"}, follow_redirects=False)
    post(f"/s/{session.code}/start", follow_redirects=False)
    first = _batch_items(db_session, _open_batch(db_session, session.id).id)[0]

    resp = post(
        f"/s/{session.code}/vote",
        data={"batch_item_id": str(first.id), "choice": "yes"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    # Re-submit: same choice, then the opposite — the first vote stands.
    resp = post(
        f"/s/{session.code}/vote",
        data={"batch_item_id": str(first.id), "choice": "yes"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    resp = post(
        f"/s/{session.code}/vote",
        data={"batch_item_id": str(first.id), "choice": "no"},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    rows = db_session.scalars(
        select(BatchResponse).where(BatchResponse.batch_item_id == first.id)
    ).all()
    assert len(rows) == 1
    assert rows[0].choice == "yes"


def test_vote_non_participant_403(client, post, db_session):
    """POST /vote without a participant cookie (host who never joined) → 403."""
    session, _, _ = _make_voting_setup(
        db_session,
        item_specs=[("Apple", "dinner")],
        targets=[("dinner", 1)],
    )
    _login(client, db_session, "host@example.com")  # account cookie, no participant
    post(f"/s/{session.code}/start", follow_redirects=False)
    first = _batch_items(db_session, _open_batch(db_session, session.id).id)[0]

    resp = post(
        f"/s/{session.code}/vote",
        data={"batch_item_id": str(first.id), "choice": "yes"},
    )
    assert resp.status_code == 403
    assert "Join the session to vote" in resp.text


def test_vote_batch_item_not_in_open_batch_404(client, post, db_session):
    """An option from a different session's batch (or a bogus id) is 404 — a
    voter can only vote on their own session's OPEN batch."""
    session_a, _, _ = _make_voting_setup(
        db_session,
        item_specs=[("Apple", "dinner")],
        targets=[("dinner", 1)],
    )
    session_b, _, _ = _make_voting_setup(
        db_session,
        host_email="other@example.com",
        item_specs=[("Pasta", "dinner")],
        targets=[("dinner", 1)],
    )
    # Another session's batch with one option (built directly — its host is a
    # different account, irrelevant here; it is NOT session_a's open batch).
    pasta = db_session.scalar(select(Item).where(Item.name == "Pasta"))
    batch_b = Batch(session_id=session_b.id, seq=1, track_label="dinner", status="open")
    db_session.add(batch_b)
    db_session.flush()
    foreign = BatchItem(batch_id=batch_b.id, item_id=pasta.id, ad_hoc_label=None, sort_order=0)
    db_session.add(foreign)
    db_session.commit()

    _login(client, db_session, "host@example.com")
    post(f"/s/{session_a.code}/join", data={"display_name": "Sam"}, follow_redirects=False)
    post(f"/s/{session_a.code}/start", follow_redirects=False)

    resp = post(
        f"/s/{session_a.code}/vote",
        data={"batch_item_id": str(foreign.id), "choice": "yes"},
    )
    assert resp.status_code == 404

    resp = post(
        f"/s/{session_a.code}/vote",
        data={"batch_item_id": "999999", "choice": "yes"},
    )
    assert resp.status_code == 404


def test_vote_bad_choice_400(client, post, db_session):
    session, _, _ = _make_voting_setup(
        db_session,
        item_specs=[("Apple", "dinner")],
        targets=[("dinner", 1)],
    )
    _login(client, db_session, "host@example.com")
    post(f"/s/{session.code}/join", data={"display_name": "Sam"}, follow_redirects=False)
    post(f"/s/{session.code}/start", follow_redirects=False)
    first = _batch_items(db_session, _open_batch(db_session, session.id).id)[0]

    resp = post(
        f"/s/{session.code}/vote",
        data={"batch_item_id": str(first.id), "choice": "maybe"},
    )
    assert resp.status_code == 400
    assert "Choice must be 'yes' or 'no'" in resp.text


def test_voting_done_and_finished_counts(client, post, db_session):
    """A participant who voted on every option sees the done state; the
    /voting-status poll counts finished/roster, reaching roster when everyone
    has voted."""
    host = _get_or_make_account(db_session, "host@example.com", "Host")
    group = _make_group(db_session, "Household", host.email)
    collection = _make_collection(db_session, group.id)
    _make_item(db_session, collection.id, "Apple", type="dinner")
    _make_item(db_session, collection.id, "Banana", type="dinner")
    session = _make_session(db_session, group.id, host.id, collection_id=collection.id)
    db_session.add(SessionTarget(session_id=session.id, track_label="dinner", target_count=1))
    lee = SessionParticipant(session_id=session.id, account_id=None, display_name="Lee")
    db_session.add(lee)
    db_session.commit()
    _login(client, db_session, host.email)
    post(f"/s/{session.code}/join", data={"display_name": "Sam"}, follow_redirects=False)
    post(f"/s/{session.code}/start", follow_redirects=False)

    batch_items = _batch_items(db_session, _open_batch(db_session, session.id).id)
    assert len(batch_items) == 2
    for bi in batch_items:
        resp = post(
            f"/s/{session.code}/vote",
            data={"batch_item_id": str(bi.id), "choice": "yes"},
            follow_redirects=False,
        )
        assert resp.status_code == 303

    # Sam has voted on everything; Lee (roster 2) hasn't voted at all.
    page = client.get(f"/s/{session.code}")
    assert page.status_code == 200
    assert "All your votes are in." in page.text
    assert "1/2 finished." in page.text
    status = client.get(f"/s/{session.code}/voting-status")
    assert status.status_code == 200
    assert "1/2 finished." in status.text

    # Lee votes on everything → finished == roster.
    _stamp_participant(client, lee.id)
    for bi in batch_items:
        resp = post(
            f"/s/{session.code}/vote",
            data={"batch_item_id": str(bi.id), "choice": "yes"},
            follow_redirects=False,
        )
        assert resp.status_code == 303
    status = client.get(f"/s/{session.code}/voting-status")
    assert status.status_code == 200
    assert "2/2 finished." in status.text


def test_host_overview_when_not_joined(client, post, db_session):
    """A host who never joined watches the voting session: finished/roster
    overview + htmx poll, never a voting card."""
    host = _get_or_make_account(db_session, "host@example.com", "Host")
    group = _make_group(db_session, "Household", host.email)
    collection = _make_collection(db_session, group.id)
    _make_item(db_session, collection.id, "Apple", type="dinner")
    _make_item(db_session, collection.id, "Banana", type="dinner")
    session = _make_session(db_session, group.id, host.id, collection_id=collection.id)
    db_session.add(SessionTarget(session_id=session.id, track_label="dinner", target_count=1))
    db_session.add(SessionParticipant(session_id=session.id, account_id=None, display_name="Sam"))
    db_session.commit()
    _login(client, db_session, host.email)  # host never joined → no participant cookie
    post(f"/s/{session.code}/start", follow_redirects=False)

    page = client.get(f"/s/{session.code}")
    assert page.status_code == 200
    assert "0/1 finished voting." in page.text
    assert "Results and batch controls arrive in the next release." in page.text
    assert f'hx-get="/s/{session.code}/voting-status"' in page.text
    assert "Option 1 of" not in page.text
    assert "All your votes are in." not in page.text


def test_ad_hoc_start_shows_coming_soon_placeholder(client, post, db_session):
    """An ad hoc session (no collection) starts without assembling a batch; the
    voting view shows the 'coming soon' placeholder."""
    host = _get_or_make_account(db_session, "host@example.com", "Host")
    group = _make_group(db_session, "Household", host.email)
    session = _make_session(db_session, group.id, host.id)
    db_session.add(SessionTarget(session_id=session.id, track_label="picks", target_count=3))
    db_session.commit()
    _login(client, db_session, host.email)

    resp = post(f"/s/{session.code}/start", follow_redirects=False)
    assert resp.status_code == 303
    db_session.refresh(session)
    assert session.status == "voting"
    assert _open_batch(db_session, session.id) is None

    page = client.get(f"/s/{session.code}")
    assert page.status_code == 200
    assert "Ad hoc voting is coming soon — options entry lands in a later release." in page.text


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


def test_collections_hub_host_session_button(client, db_session):
    host = _get_or_make_account(db_session, "host@example.com", "Host")
    group = _make_group(db_session, "Household", host.email)
    _make_collection(db_session, group.id)
    _login(client, db_session, host.email)
    resp = client.get("/collections")
    assert resp.status_code == 200
    assert 'href="/sessions/new"' in resp.text
    assert "Host a session" in resp.text


def test_home_join_session_entry_signed_out(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Join a session" in resp.text
    assert 'href="/join"' in resp.text


def test_home_join_session_entry_signed_in(client, db_session):
    host = _get_or_make_account(db_session, "host@example.com", "Host")
    _login(client, db_session, host.email)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Join a session" in resp.text
    assert 'href="/join"' in resp.text
    assert 'href="/sessions/new"' in resp.text
