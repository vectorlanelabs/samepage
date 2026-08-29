"""Signup/login/logout (M2a): email+password, session identity.

The ``client`` and ``db_session`` fixtures share one tmp engine (conftest),
so state created through the HTTP layer is visible to direct session queries.
"""

from app.credentials import hash_password
from app.models import Account


def _make_account(db_session, email="test@example.com", password="testpass123", display_name="Test User"):
    account = Account(
        email=email,
        password_hash=hash_password(password),
        display_name=display_name,
    )
    db_session.add(account)
    db_session.commit()
    return account


def test_signup_success_creates_account_and_sets_session(client, post, db_session):
    resp = post(
        "/signup",
        data={
            "email": "newuser@example.com",
            "password": "testpass123",
            "display_name": "New User",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"
    # Account was created.
    account = db_session.query(Account).filter_by(email="newuser@example.com").first()
    assert account is not None
    assert account.display_name == "New User"


def test_signup_duplicate_email_400(client, post, db_session):
    _make_account(db_session, email="taken@example.com")
    resp = post(
        "/signup",
        data={
            "email": "taken@example.com",
            "password": "testpass123",
            "display_name": "Another User",
        },
    )
    assert resp.status_code == 400
    assert "already in use" in resp.text


def test_signup_invalid_email_400(client, post, db_session):
    resp = post(
        "/signup",
        data={
            "email": "notanemail",
            "password": "testpass123",
            "display_name": "User",
        },
    )
    assert resp.status_code == 400
    assert "not valid" in resp.text


def test_signup_short_password_400(client, post, db_session):
    resp = post(
        "/signup",
        data={
            "email": "test@example.com",
            "password": "short",
            "display_name": "User",
        },
    )
    assert resp.status_code == 400
    assert "at least 8 characters" in resp.text


def test_signup_empty_display_name_400(client, post, db_session):
    resp = post(
        "/signup",
        data={
            "email": "test@example.com",
            "password": "testpass123",
            "display_name": "  ",  # whitespace only
        },
    )
    assert resp.status_code == 400
    assert "Display name is required" in resp.text


def test_login_success_sets_session(client, post, db_session):
    _make_account(db_session, email="test@example.com", password="testpass123")
    resp = post(
        "/login",
        data={"email": "test@example.com", "password": "testpass123"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"


def test_login_wrong_password_401(client, post, db_session):
    _make_account(db_session, email="test@example.com", password="testpass123")
    resp = post("/login", data={"email": "test@example.com", "password": "wrongpass"})
    assert resp.status_code == 401
    assert "Email or password" in resp.text


def test_login_unknown_email_401(post):
    resp = post("/login", data={"email": "nonexistent@example.com", "password": "anypass"})
    assert resp.status_code == 401
    assert "Email or password" in resp.text


def test_login_case_insensitive_email(client, post, db_session):
    _make_account(db_session, email="test@example.com", password="testpass123")
    resp = post(
        "/login",
        data={"email": "TEST@EXAMPLE.COM", "password": "testpass123"},
        follow_redirects=False,
    )
    assert resp.status_code == 303


def test_logout_clears_session(client, post, db_session):
    _make_account(db_session)
    post("/login", data={"email": "test@example.com", "password": "testpass123"})
    resp = post("/logout", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


def test_login_page_while_already_signed_in_redirects(client, post, db_session):
    """Regression: the redirect-if-already-signed-in check must actually run a
    DB lookup, not crash. Previously called get_current_account(request, None)."""
    _make_account(db_session)
    post("/login", data={"email": "test@example.com", "password": "testpass123"})
    resp = client.get("/login", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"


def test_signup_page_while_already_signed_in_redirects(client, post, db_session):
    _make_account(db_session)
    post("/login", data={"email": "test@example.com", "password": "testpass123"})
    resp = client.get("/signup", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"
