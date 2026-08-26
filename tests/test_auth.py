"""Login/logout (M1, T1.2): PIN verify, attempt limiting, session identity.

The ``client`` and ``db_session`` fixtures share one tmp engine (conftest),
so state created through the HTTP layer is visible to direct session queries.
"""

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

from app.auth import LOCKOUT_ATTEMPTS
from app.models import Person
from app.pins import hash_pin


def _make_person(db_session, name="Ada", pin="1234", **kwargs):
    person = Person(name=name, pin_hash=hash_pin(pin), **kwargs)
    db_session.add(person)
    db_session.commit()
    return person


def _past() -> datetime:
    """Naive-UTC timestamp in the past (matches SQLAlchemy DateTime storage)."""
    return datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)


def test_login_success_sets_session_and_me(client, post, db_session):
    _make_person(db_session)
    resp = post("/login", data={"name": "Ada", "pin": "1234"}, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/people"
    me = client.get("/me")
    assert me.status_code == 200
    assert me.json() == {"name": "Ada", "is_admin": False, "is_active": True}


def test_login_wrong_pin_401_and_no_session(client, post, db_session):
    _make_person(db_session)
    resp = post("/login", data={"name": "Ada", "pin": "0000"})
    assert resp.status_code == 401
    assert client.get("/me").status_code == 401  # session never set


def test_unknown_person_401(post):
    resp = post("/login", data={"name": "Ghost", "pin": "1234"})
    assert resp.status_code == 401


def test_lockout_blocks_correct_pin_until_expiry(post, db_session):
    person = _make_person(db_session)
    for _ in range(LOCKOUT_ATTEMPTS):
        resp = post("/login", data={"name": "Ada", "pin": "0000"})
        assert resp.status_code == 401
    # Locked: even the CORRECT pin is rejected with the lockout message.
    resp = post("/login", data={"name": "Ada", "pin": "1234"})
    assert resp.status_code == 401
    assert "Too many attempts" in resp.text
    assert "seconds" in resp.text
    # Simulate expiry by back-dating locked_until, then login succeeds.
    person.locked_until = _past()
    db_session.commit()
    resp = post("/login", data={"name": "Ada", "pin": "1234"}, follow_redirects=False)
    assert resp.status_code == 303


def test_success_resets_failed_attempts(post, db_session):
    person = _make_person(db_session)
    for _ in range(LOCKOUT_ATTEMPTS - 1):
        post("/login", data={"name": "Ada", "pin": "0000"})
    # One more failure would lock; a correct login before that must reset.
    resp = post("/login", data={"name": "Ada", "pin": "1234"}, follow_redirects=False)
    assert resp.status_code == 303
    db_session.refresh(person)
    assert person.failed_pin_attempts == 0
    assert person.locked_until is None


def test_inactive_person_cannot_login(post, db_session):
    _make_person(db_session, is_active=False)
    resp = post("/login", data={"name": "Ada", "pin": "1234"})
    assert resp.status_code == 401


def test_logout_clears_session(client, post, db_session):
    _make_person(db_session)
    post("/login", data={"name": "Ada", "pin": "1234"})
    assert client.get("/me").status_code == 200
    resp = post("/logout", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"
    assert client.get("/me").status_code == 401


def test_concurrent_wrong_pins_engage_lock_atomically(post, db_session):
    """8 concurrent wrong-PIN attempts all 401 AND still engage the lock.

    The old read-modify-write collapsed 10 concurrent guesses into a counter
    of 1–2 and never locked; the atomic UPDATE + same-transaction read-back
    must not lose increments (LOCKOUT_ATTEMPTS = 5 < 8). The barrier holds
    all 8 threads until every one is ready, so the requests cannot serialize
    by accident.
    """
    person = _make_person(db_session)
    barrier = threading.Barrier(8)

    def attempt(_):
        barrier.wait()
        return post("/login", data={"name": "Ada", "pin": "9999"}).status_code

    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(attempt, range(8)))

    assert statuses == [401] * 8
    db_session.refresh(person)
    assert person.locked_until is not None  # lock engaged under concurrency
    assert person.failed_pin_attempts == 0  # post-lock reset
