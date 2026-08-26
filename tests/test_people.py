"""People management (M1, T1.1–T1.3): bootstrap admin, admin gating,
deactivate-not-delete, PIN change."""

import threading
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select

from app.models import Person
from app.pins import hash_pin


def _make_person(db_session, name, pin="1234", is_admin=False, is_active=True):
    person = Person(name=name, pin_hash=hash_pin(pin), is_admin=is_admin, is_active=is_active)
    db_session.add(person)
    db_session.commit()
    return person


def _login(post, name, pin="1234"):
    post("/login", data={"name": name, "pin": pin})


def test_first_person_bootstrap_is_admin(post, db_session):
    resp = post("/people", data={"name": "Ada", "pin": "1234"}, follow_redirects=False)
    assert resp.status_code == 303
    ada = db_session.scalar(select(Person).where(Person.name == "Ada"))
    assert ada is not None
    assert ada.is_admin is True


def test_people_page_renders_roster(client, post, db_session):
    _make_person(db_session, "Mom", is_admin=True)
    _make_person(db_session, "Ava")
    _login(post, "Mom")
    resp = client.get("/people")
    assert resp.status_code == 200
    assert "Name + PIN, no accounts. Deactivated, never deleted." in resp.text
    assert "Mom" in resp.text
    assert "Ava" in resp.text
    assert "★ Admin" in resp.text
    assert "PIN ••••" in resp.text


def test_non_admin_blocked_from_people(client, post, db_session):
    _make_person(db_session, "Admin", is_admin=True)
    _make_person(db_session, "User")
    _login(post, "User")
    assert client.get("/people").status_code == 403
    assert post("/people", data={"name": "Intruder", "pin": "1111"}).status_code == 403


def test_anonymous_blocked_when_people_exist(client, post, db_session):
    _make_person(db_session, "Admin", is_admin=True)
    assert client.get("/people").status_code == 403
    assert post("/people", data={"name": "Intruder", "pin": "1111"}).status_code == 403


def test_admin_creates_second_person_not_admin(post, db_session):
    _make_person(db_session, "Admin", is_admin=True)
    _login(post, "Admin")
    resp = post("/people", data={"name": "Bob", "pin": "2222"}, follow_redirects=False)
    assert resp.status_code == 303
    bob = db_session.scalar(select(Person).where(Person.name == "Bob"))
    assert bob is not None
    assert bob.is_admin is False


def test_admin_toggle(post, db_session):
    _make_person(db_session, "Admin", is_admin=True)
    bob = _make_person(db_session, "Bob")
    _login(post, "Admin")
    resp = post(f"/people/{bob.id}/admin", follow_redirects=False)
    assert resp.status_code == 303
    db_session.refresh(bob)
    assert bob.is_admin is True
    post(f"/people/{bob.id}/admin")
    db_session.refresh(bob)
    assert bob.is_admin is False


def test_deactivate_blocks_login_then_reactivate(post, db_session):
    _make_person(db_session, "Admin", is_admin=True)
    bob = _make_person(db_session, "Bob")
    _login(post, "Admin")
    resp = post(f"/people/{bob.id}/deactivate", follow_redirects=False)
    assert resp.status_code == 303
    db_session.refresh(bob)
    assert bob.is_active is False
    # Deactivated person cannot log in.
    post("/logout")
    assert post("/login", data={"name": "Bob", "pin": "1234"}).status_code == 401
    # Reactivate, and they can.
    _login(post, "Admin")
    post(f"/people/{bob.id}/reactivate")
    db_session.refresh(bob)
    assert bob.is_active is True
    post("/logout")
    resp = post("/login", data={"name": "Bob", "pin": "1234"}, follow_redirects=False)
    assert resp.status_code == 303


def test_self_deactivate_and_self_demote_blocked(post, db_session):
    admin = _make_person(db_session, "Admin", is_admin=True)
    _login(post, "Admin")
    assert post(f"/people/{admin.id}/deactivate").status_code == 403
    assert post(f"/people/{admin.id}/admin").status_code == 403


def test_no_delete_route(client, post, db_session):
    _make_person(db_session, "Admin", is_admin=True)
    _login(post, "Admin")
    admin = db_session.scalar(select(Person).where(Person.name == "Admin"))
    resp = client.delete(f"/people/{admin.id}", headers={"Origin": "http://testserver"})
    assert resp.status_code == 405


def test_duplicate_name_400(post, db_session):
    _make_person(db_session, "Admin", is_admin=True)
    _make_person(db_session, "Bob")
    _login(post, "Admin")
    resp = post("/people", data={"name": "Bob", "pin": "2222"})
    assert resp.status_code == 400
    assert "already exists" in resp.text


def test_invalid_pin_400(post, db_session):
    _make_person(db_session, "Admin", is_admin=True)
    _login(post, "Admin")
    for bad in ["12", "12a4", "abcd"]:
        resp = post("/people", data={"name": "Newbie", "pin": bad})
        assert resp.status_code == 400
    # None of the failed attempts created a person.
    count = db_session.scalar(select(Person).where(Person.name == "Newbie"))
    assert count is None


def test_empty_name_400(post, db_session):
    _make_person(db_session, "Admin", is_admin=True)
    _login(post, "Admin")
    resp = post("/people", data={"name": "  ", "pin": "1234"})
    assert resp.status_code == 400


def test_pin_change_old_fails_new_works(post, db_session):
    _make_person(db_session, "Admin", is_admin=True)
    bob = _make_person(db_session, "Bob")
    _login(post, "Admin")
    resp = post(f"/people/{bob.id}/pin", data={"pin": "9876"}, follow_redirects=False)
    assert resp.status_code == 303
    # Old PIN fails, new PIN works.
    assert post("/login", data={"name": "Bob", "pin": "1234"}).status_code == 401
    resp = post("/login", data={"name": "Bob", "pin": "9876"}, follow_redirects=False)
    assert resp.status_code == 303


def test_pin_change_resets_lockout(post, db_session):
    _make_person(db_session, "Admin", is_admin=True)
    bob = _make_person(db_session, "Bob")
    # Lock Bob out with repeated failures.
    for _ in range(5):
        post("/login", data={"name": "Bob", "pin": "0000"})
    _login(post, "Admin")
    post(f"/people/{bob.id}/pin", data={"pin": "5555"})
    post("/logout")
    resp = post("/login", data={"name": "Bob", "pin": "5555"}, follow_redirects=False)
    assert resp.status_code == 303


def test_concurrent_bootstrap_creates_one_admin(post, db_session):
    """Two concurrent first-person POSTs must not both observe count == 0.

    Old code: both saw count == 0 → both bootstrapped as admin (two 303s).
    Serialized: exactly one wins the bootstrap; the loser sees count > 0 →
    admin required, and has no session → 403. The barrier releases both
    threads at the same instant so the race is exercised deterministically.
    """
    barrier = threading.Barrier(2)

    def create(args):
        name, pin = args
        barrier.wait()
        return post("/people", data={"name": name, "pin": pin}, follow_redirects=False).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(create, [("X1", "1111"), ("X2", "2222")]))

    people = db_session.scalars(select(Person)).all()
    assert len(people) == 1
    assert people[0].is_admin is True
    assert sorted(statuses) == [303, 403]
