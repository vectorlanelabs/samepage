"""Session routes + code generation (M3b): create, join-by-code (no account),
live lobby, roster polling, host start/remove, and the make_code helper.

Every POST that mutates goes through the ``post`` fixture (same-origin Origin
header — the origin-check middleware is fail-closed). The host is stamped via
``stamp_session`` (conftest) everywhere a signed-in account is needed; join
tests exercise the signed-OUT path (codes are the join surface, per plan §2).
"""

from __future__ import annotations

import random

import pytest
from conftest import stamp_session
from sqlalchemy import func, select

from app.models import (
    Account,
    Collection,
    Group,
    SessionParticipant,
    SessionTarget,
)
from app.models import (
    Session as VotingSession,
)
from app.session_logic import WORDLIST, make_code

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

    # M3b placeholder instead of a ballot.
    page = client.get(f"/s/{session.code}")
    assert page.status_code == 200
    assert "Voting starts here — batches arrive in the next release (M3c)." in page.text


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
