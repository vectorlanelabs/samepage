"""Live adversarial probes against the M3b session routes.
Run with: python -m pytest -q -s probe_sessions.py  (or run as a script via conftest fixtures)
We reuse tests/conftest.py fixtures by putting this file in tests/ temporarily... instead
we just write it as a pytest file importing conftest helpers, placed in tests/ dir.
"""
from __future__ import annotations

import base64
import json

from itsdangerous import TimestampSigner
from sqlalchemy import select

from app.models import Account, Collection, Group, SessionParticipant
from app.models import Session as VotingSession
from conftest import stamp_session


def _acct(db, email, name=None):
    a = db.scalar(select(Account).where(Account.email == email))
    if a:
        return a
    a = Account(email=email, display_name=name or email.split("@")[0])
    db.add(a)
    db.commit()
    return a


def _group(db, name, owner_email):
    o = _acct(db, owner_email)
    g = Group(name=name, owner_account_id=o.id)
    db.add(g)
    db.commit()
    return g


def _login(client, db, email):
    a = db.scalar(select(Account).where(Account.email == email))
    stamp_session(client, a)


def test_probe_cross_tenant_creation_garbage_ids(client, post, db_session):
    host = _acct(db_session, "host@example.com", "Host")
    group = _group(db_session, "H", host.email)
    _login(client, db_session, host.email)

    # garbage group_id
    r = post("/sessions", data={"group_id": "not-a-number", "collection_id": "", "dinners": "1", "lunches": "0", "picks": "1"})
    print("garbage group_id ->", r.status_code)
    assert r.status_code == 404

    # garbage collection_id
    r = post("/sessions", data={"group_id": str(group.id), "collection_id": "not-a-number", "dinners": "1", "lunches": "0", "picks": "1"})
    print("garbage collection_id ->", r.status_code)
    assert r.status_code == 404

    # absent group_id entirely
    r = post("/sessions", data={"collection_id": "", "dinners": "1", "lunches": "0", "picks": "1"})
    print("absent group_id ->", r.status_code)
    assert r.status_code == 404

    # huge collection_id (int overflow risk?)
    r = post("/sessions", data={"group_id": str(group.id), "collection_id": "99999999999999999999999999", "dinners": "1", "lunches": "0", "picks": "1"})
    print("huge collection_id ->", r.status_code, r.text[:200])
    assert r.status_code in (400, 404)


def test_probe_public_surface_leak(client, post, db_session):
    host = _acct(db_session, "host@example.com", "Host")
    group = _group(db_session, "SecretGroupName", host.email)
    coll = Collection(group_id=group.id, kind="meal", name="SecretCollectionName")
    db_session.add(coll)
    db_session.commit()
    _login(client, db_session, host.email)
    r = post("/sessions", data={"group_id": str(group.id), "collection_id": str(coll.id), "dinners": "2", "lunches": "0", "picks": "1"}, follow_redirects=False)
    session = db_session.scalar(select(VotingSession).order_by(VotingSession.id.desc()))
    print("created", session.code)

    # stranger, no cookie
    stranger = client
    stranger.cookies.clear()
    pre_join = stranger.get(f"/s/{session.code}")
    print("PRE-JOIN PAGE LEAK CHECK:")
    print("  contains group name?", "SecretGroupName" in pre_join.text)
    print("  contains collection name?", "SecretCollectionName" in pre_join.text)
    print("  contains host email?", host.email in pre_join.text)
    assert "SecretGroupName" not in pre_join.text
    assert "SecretCollectionName" not in pre_join.text
    assert host.email not in pre_join.text

    roster = stranger.get(f"/s/{session.code}/roster")
    print("ROSTER (pre-join, no participants) leak check:", roster.status_code)
    print("  body:", roster.text[:300])
    assert host.email not in roster.text
    assert "SecretCollectionName" not in roster.text

    # nonexistent code
    r404 = stranger.get("/s/ghost-9999")
    print("nonexistent code ->", r404.status_code)
    r404b = stranger.get("/s/ghost-9999/roster")
    print("nonexistent code roster ->", r404b.status_code)


def test_probe_participant_cookie_cross_session(client, post, db_session):
    host = _acct(db_session, "host@example.com", "Host")
    group = _group(db_session, "G", host.email)
    _login(client, db_session, host.email)
    r1 = post("/sessions", data={"group_id": str(group.id), "collection_id": "", "dinners": "0", "lunches": "0", "picks": "1"}, follow_redirects=False)
    session_a = db_session.scalar(select(VotingSession).order_by(VotingSession.id.desc()))
    r2 = post("/sessions", data={"group_id": str(group.id), "collection_id": "", "dinners": "0", "lunches": "0", "picks": "1"}, follow_redirects=False)
    session_b = db_session.scalar(select(VotingSession).order_by(VotingSession.id.desc()))
    print("session A", session_a.code, "session B", session_b.code)

    client.cookies.clear()
    # stranger joins A
    join = post(f"/s/{session_a.code}/join", data={"display_name": "Pat"}, follow_redirects=False)
    print("join A ->", join.status_code)
    participant = db_session.scalar(select(SessionParticipant).where(SessionParticipant.session_id == session_a.id))
    print("participant id", participant.id)

    # Now GET session B with the participant cookie pointed at A's participant.
    page_b = client.get(f"/s/{session_b.code}")
    print("GET B with A's participant cookie -> status", page_b.status_code)
    print("  shows join form (name='display_name')?", 'name="display_name"' in page_b.text)
    print("  shows lobby (Waiting room)?", "Waiting room" in page_b.text)
    assert 'name="display_name"' in page_b.text
    assert "Waiting room" not in page_b.text

    # Host removes Pat from A, then Pat's browser (still holding stale participant_id) hits A again.
    _login(client, db_session, host.email)
    rm = post(f"/s/{session_a.code}/participants/{participant.id}/remove", follow_redirects=False)
    print("host removed Pat ->", rm.status_code)
    client.cookies.clear()
    # restore Pat's session cookie manually (simulate Pat's browser still holding old cookie)
    # Actually the cookie was cleared above when host logged in via stamp_session overwrite of the 'session' cookie
    # (participant_id lives in the same session cookie as account_id). Let's check that overwrite behavior:
    print("NOTE: stamp_session overwrites the whole 'session' cookie, so participant_id may be wiped by host login.")


def test_probe_participant_id_survives_host_login_shared_cookie(client, post, db_session):
    """The signed session cookie carries BOTH account_id and participant_id.
    Does stamp_session-style login (SSO) clobber a visitor's participant_id?
    More realistically: does joining as a signed-in viewer then having someone else
    log in on the SAME browser wipe participant_id, or is participant_id additive?
    """
    host = _acct(db_session, "host@example.com", "Host")
    group = _group(db_session, "G", host.email)
    _login(client, db_session, host.email)
    post("/sessions", data={"group_id": str(group.id), "collection_id": "", "dinners": "0", "lunches": "0", "picks": "1"}, follow_redirects=False)
    session_a = db_session.scalar(select(VotingSession).order_by(VotingSession.id.desc()))
    client.cookies.clear()

    join = post(f"/s/{session_a.code}/join", data={"display_name": "Pat"}, follow_redirects=False)
    participant = db_session.scalar(select(SessionParticipant).where(SessionParticipant.session_id == session_a.id))
    print("Pat participant id", participant.id)

    # host removes Pat
    _login(client, db_session, host.email)  # this OVERWRITES the whole session cookie
    rm = post(f"/s/{session_a.code}/participants/{participant.id}/remove", follow_redirects=False)
    print("removed ->", rm.status_code)

    # Simulate host's OWN browser continuing to hold the stale participant_id (if host had joined as a participant too)
    # More realistic stale-id test: participant revisits with their OWN old cookie (not clobbered by anyone else).
    # Redo cleanly:


def test_probe_stale_participant_id_after_removal(client, post, db_session):
    host = _acct(db_session, "host@example.com", "Host")
    group = _group(db_session, "G", host.email)
    _login(client, db_session, host.email)
    post("/sessions", data={"group_id": str(group.id), "collection_id": "", "dinners": "0", "lunches": "0", "picks": "1"}, follow_redirects=False)
    session_a = db_session.scalar(select(VotingSession).order_by(VotingSession.id.desc()))

    # Use a SEPARATE client (separate cookie jar) to represent Pat, so host login never touches Pat's cookie.
    from fastapi.testclient import TestClient
    from app.main import app
    pat = TestClient(app)
    join = pat.post(f"/s/{session_a.code}/join", data={"display_name": "Pat"}, headers={"Origin": "http://testserver"}, follow_redirects=False)
    print("pat join ->", join.status_code)
    participant = db_session.scalar(select(SessionParticipant).where(SessionParticipant.session_id == session_a.id))
    print("participant id", participant.id, "pat cookies", dict(pat.cookies))

    before = pat.get(f"/s/{session_a.code}")
    print("pat sees lobby before removal:", "Waiting room" in before.text, before.status_code)

    # host removes Pat via the primary `client`
    rm = post(f"/s/{session_a.code}/participants/{participant.id}/remove", follow_redirects=False)
    print("host removed pat ->", rm.status_code)

    after = pat.get(f"/s/{session_a.code}")
    print("pat GET after removal -> status", after.status_code)
    print("  shows join form again?", 'name="display_name"' in after.text)
    print("  crashed (500)?", after.status_code == 500)
    assert after.status_code == 200
    assert 'name="display_name"' in after.text

    roster_after = pat.get(f"/s/{session_a.code}/roster")
    print("pat roster GET after removal -> status", roster_after.status_code)
    assert roster_after.status_code == 200


def test_probe_host_controls_ended_and_replay(client, post, db_session):
    host = _acct(db_session, "host@example.com", "Host")
    group = _group(db_session, "G", host.email)
    session = VotingSession(code="probe-0001", status="complete", group_id=group.id, host_account_id=host.id)
    db_session.add(session)
    db_session.commit()
    _login(client, db_session, host.email)

    r = post(f"/s/{session.code}/start")
    print("start on complete session ->", r.status_code, r.text[:150])
    assert r.status_code == 400

    session2 = VotingSession(code="probe-0002", status="expired", group_id=group.id, host_account_id=host.id)
    db_session.add(session2)
    db_session.commit()
    r2 = post(f"/s/{session2.code}/start")
    print("start on expired session ->", r2.status_code)
    assert r2.status_code == 400

    # double-remove replay
    session3 = VotingSession(code="probe-0003", status="lobby", group_id=group.id, host_account_id=host.id)
    db_session.add(session3)
    db_session.commit()
    p = SessionParticipant(session_id=session3.id, account_id=None, display_name="Sam")
    db_session.add(p)
    db_session.commit()
    pid = p.id
    r3 = post(f"/s/{session3.code}/participants/{pid}/remove")
    print("first remove ->", r3.status_code)
    r4 = post(f"/s/{session3.code}/participants/{pid}/remove")
    print("second remove (replay) ->", r4.status_code)
    assert r4.status_code == 404

    # huge pid (overflow?)
    r5 = post(f"/s/{session3.code}/participants/99999999999999999999999999/remove")
    print("huge pid remove ->", r5.status_code)
    assert r5.status_code in (404, 422)


def test_probe_xss_display_name(client, post, db_session):
    host = _acct(db_session, "host@example.com", "Host")
    group = _group(db_session, "G", host.email)
    session = VotingSession(code="probe-xss1", status="lobby", group_id=group.id, host_account_id=host.id)
    db_session.add(session)
    db_session.commit()
    client.cookies.clear()
    payload = "<script>alert(1)</script>"
    r = post(f"/s/{session.code}/join", data={"display_name": payload}, follow_redirects=False)
    print("join with xss payload ->", r.status_code)

    lobby = client.get(f"/s/{session.code}")
    print("raw script tag present in lobby?", "<script>alert(1)</script>" in lobby.text)
    print("escaped form present?", "&lt;script&gt;" in lobby.text)
    assert "<script>alert(1)</script>" not in lobby.text

    roster = client.get(f"/s/{session.code}/roster")
    print("raw script tag present in ROSTER PARTIAL?", "<script>alert(1)</script>" in roster.text)
    assert "<script>alert(1)</script>" not in roster.text

    # code reflected in URL path
    r404 = client.get("/s/%3Cscript%3Ealert(2)%3C/script%3E")
    print("garbage code in path status:", r404.status_code)
    print("  script reflected raw?", "<script>alert(2)</script>" in r404.text)
    assert "<script>alert(2)</script>" not in r404.text
