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


# ---------- 401 -> /login redirect (app/main.py's exception handler) ----------


def test_anonymous_page_load_401_redirects_to_login(client):
    """A signed-out browser navigation that hits a 401 gets a login redirect
    with `next` set to where they were headed, not a bare JSON error body."""
    resp = client.get("/groups", headers={"accept": "text/html"}, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login?next=%2Fgroups"


def test_anonymous_api_style_401_stays_json(client):
    """A non-browser request (no text/html Accept) keeps the plain JSON 401 --
    relevant once M6's token-authenticated routes exist."""
    resp = client.get("/groups", headers={"accept": "application/json"})
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Sign in required"}


def test_login_next_redirects_after_success(client, post, db_session):
    _make_account(db_session)
    resp = post(
        "/login",
        data={"email": "test@example.com", "password": "testpass123", "next": "/groups"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/groups"


# ---------- Signup `next` handling ----------


def test_signup_next_redirects_after_success(client, post, db_session):
    resp = post(
        "/signup",
        data={
            "email": "newuser@example.com",
            "password": "testpass123",
            "display_name": "New User",
            "next": "/groups",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/groups"


def test_signup_next_rejects_absolute_url(client, post, db_session):
    resp = post(
        "/signup",
        data={
            "email": "newuser@example.com",
            "password": "testpass123",
            "display_name": "New User",
            "next": "https://evil.example.com",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"


# ---------- Account indicator / sign-out in the chrome (base.html) ----------


def test_signed_in_page_shows_account_and_sign_out(client, post, db_session):
    _make_account(db_session, display_name="Ada Lovelace")
    post("/login", data={"email": "test@example.com", "password": "testpass123"})
    resp = client.get("/groups")
    assert resp.status_code == 200
    assert "Ada Lovelace" in resp.text
    assert '<form method="post" action="/logout">' in resp.text


def test_signed_out_page_shows_sign_in_link(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert '<a class="nav-link" href="/login">Sign in</a>' in resp.text
    assert "Sign out" not in resp.text


# ---------- _safe_next open-redirect guard ----------


def test_login_next_rejects_absolute_url(client, post, db_session):
    _make_account(db_session)
    resp = post(
        "/login",
        data={"email": "test@example.com", "password": "testpass123", "next": "https://evil.example.com"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"


def test_login_next_rejects_protocol_relative(client, post, db_session):
    _make_account(db_session)
    resp = post(
        "/login",
        data={"email": "test@example.com", "password": "testpass123", "next": "//evil.example.com"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"


def test_login_next_rejects_backslash_bypass(client, post, db_session):
    """Regression: `/\\evil.com` starts with `/` and not `//`, but a browser
    normalizes the backslash to a forward slash, turning it into the
    protocol-relative `//evil.com` the plain startswith check was meant to
    reject in the first place."""
    _make_account(db_session)
    resp = post(
        "/login",
        data={"email": "test@example.com", "password": "testpass123", "next": "/\\evil.example.com"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"
