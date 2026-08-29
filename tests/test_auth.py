"""SSO auth (M5a): Google OAuth sign-in behind the provider seam, logout,
session identity, and the 401 → /login redirect.

The provider seam is ``app.routes.auth.PROVIDERS["google"]`` — tests
monkeypatch a fake provider there, so authlib's internals are never touched.
The ``client`` and ``db_session`` fixtures share one tmp engine (conftest),
so state created through the HTTP layer is visible to direct session queries.
"""

import pytest
from conftest import stamp_session
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select

from app.models import Account, AuthIdentity
from app.routes import auth as auth_routes
from app.sso import Identity


def _make_account(db_session, email="test@example.com", display_name="Test User"):
    account = Account(email=email, display_name=display_name)
    db_session.add(account)
    db_session.commit()
    return account


class FakeProvider:
    """Stands in for GoogleProvider at the app.routes.auth.PROVIDERS seam."""

    def __init__(self, identity=None, configured=True, error=None):
        self.identity = identity
        self.configured = configured
        self.error = error

    async def authorize_redirect(self, request, redirect_uri):
        return RedirectResponse("https://accounts.google.com/fake", status_code=302)

    async def get_identity(self, request):
        if self.error is not None:
            raise self.error
        return self.identity


# ---------- Login page ----------


def test_login_page_shows_google_button_when_configured(client, monkeypatch):
    monkeypatch.setitem(auth_routes.PROVIDERS, "google", FakeProvider(configured=True))
    resp = client.get("/login")
    assert resp.status_code == 200
    assert "Continue with Google" in resp.text
    assert 'href="/auth/google"' in resp.text
    # No email/password form anywhere.
    assert 'type="password"' not in resp.text
    assert 'name="email"' not in resp.text


def test_login_page_while_already_signed_in_redirects(client, db_session):
    account = _make_account(db_session)
    stamp_session(client, account)
    resp = client.get("/login", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"


# ---------- Callback: identity → account resolution ----------


def test_callback_new_identity_creates_account_and_signs_in(client, db_session, monkeypatch):
    provider = FakeProvider(identity=Identity("sub-123", "brand.new@example.com", True, "Brand New"))
    monkeypatch.setitem(auth_routes.PROVIDERS, "google", provider)

    resp = client.get("/auth/google/callback", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"

    account = db_session.scalar(select(Account).where(Account.email == "brand.new@example.com"))
    assert account is not None
    assert account.display_name == "Brand New"
    auth_identity = db_session.scalar(select(AuthIdentity).where(AuthIdentity.subject == "sub-123"))
    assert auth_identity is not None
    assert auth_identity.provider == "google"
    assert auth_identity.account_id == account.id

    # Session works on a follow-up page load: the display name shows.
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Brand New" in resp.text


def test_callback_existing_identity_logs_into_same_account(client, db_session, monkeypatch):
    account = _make_account(db_session, email="existing@example.com", display_name="Existing User")
    db_session.add(
        AuthIdentity(
            account_id=account.id, provider="google", subject="sub-456", email="existing@example.com"
        )
    )
    db_session.commit()

    provider = FakeProvider(identity=Identity("sub-456", "existing@example.com", True, "Existing User"))
    monkeypatch.setitem(auth_routes.PROVIDERS, "google", provider)

    resp = client.get("/auth/google/callback", follow_redirects=False)
    assert resp.status_code == 303

    # No duplicate rows: still exactly one identity and one account.
    assert db_session.scalar(select(func.count()).select_from(AuthIdentity)) == 1
    assert db_session.scalar(select(func.count()).select_from(Account)) == 1
    resp = client.get("/groups")
    assert resp.status_code == 200
    assert "Existing User" in resp.text


def test_callback_email_match_links_identity_to_existing_account(client, db_session, monkeypatch):
    account = _make_account(db_session, email="linked@example.com", display_name="Linked User")
    provider = FakeProvider(identity=Identity("sub-789", "linked@example.com", True, "Linked User"))
    monkeypatch.setitem(auth_routes.PROVIDERS, "google", provider)

    resp = client.get("/auth/google/callback", follow_redirects=False)
    assert resp.status_code == 303

    # No second account was created — the identity was linked to the existing one.
    assert db_session.scalar(select(func.count()).select_from(Account)) == 1
    auth_identity = db_session.scalar(select(AuthIdentity).where(AuthIdentity.subject == "sub-789"))
    assert auth_identity is not None
    assert auth_identity.account_id == account.id
    assert auth_identity.email == "linked@example.com"
    resp = client.get("/")
    assert "Linked User" in resp.text


def test_callback_unverified_email_400_no_account(client, db_session, monkeypatch):
    provider = FakeProvider(identity=Identity("sub-unv", "unverified@example.com", False, "No"))
    monkeypatch.setitem(auth_routes.PROVIDERS, "google", provider)

    resp = client.get("/auth/google/callback")
    assert resp.status_code == 400
    assert "Your Google email" in resp.text  # apostrophe is HTML-escaped, assert around it
    assert db_session.scalar(select(func.count()).select_from(Account)) == 0
    assert db_session.scalar(select(func.count()).select_from(AuthIdentity)) == 0
    # Not signed in.
    resp = client.get("/groups")
    assert resp.status_code == 401


def test_callback_provider_error_400_sign_in_failed(client, db_session, monkeypatch):
    provider = FakeProvider(error=RuntimeError("token exchange failed"))
    monkeypatch.setitem(auth_routes.PROVIDERS, "google", provider)

    resp = client.get("/auth/google/callback")
    assert resp.status_code == 400
    assert "Sign-in failed" in resp.text
    assert db_session.scalar(select(func.count()).select_from(Account)) == 0
    # Not signed in.
    resp = client.get("/groups")
    assert resp.status_code == 401


# ---------- /auth/google: next stash + open-redirect guard ----------


def test_google_authorize_stashes_next_and_callback_lands_there(client, db_session, monkeypatch):
    provider = FakeProvider(identity=Identity("sub-next", "next@example.com", True, "Next User"))
    monkeypatch.setitem(auth_routes.PROVIDERS, "google", provider)

    resp = client.get("/auth/google", params={"next": "/groups"}, follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "https://accounts.google.com/fake"

    resp = client.get("/auth/google/callback", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/groups"


@pytest.mark.parametrize("evil", ["https://evil.example.com", "/\\evil.example.com"])
def test_google_authorize_rejects_evil_next(client, db_session, monkeypatch, evil):
    provider = FakeProvider(identity=Identity("sub-evil", "evil@example.com", True, "Evil User"))
    monkeypatch.setitem(auth_routes.PROVIDERS, "google", provider)

    resp = client.get("/auth/google", params={"next": evil}, follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "https://accounts.google.com/fake"

    resp = client.get("/auth/google/callback", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"


# ---------- Unconfigured provider ----------


def test_google_authorize_unconfigured_503_and_login_hint(client, monkeypatch):
    monkeypatch.setitem(auth_routes.PROVIDERS, "google", FakeProvider(configured=False))

    resp = client.get("/auth/google")
    assert resp.status_code == 503

    resp = client.get("/login")
    assert resp.status_code == 200
    assert "isn't configured on this server yet" in resp.text


# ---------- /signup forwards to /login ----------


def test_signup_redirects_to_login(client):
    resp = client.get("/signup", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


def test_signup_preserves_next(client):
    resp = client.get("/signup", params={"next": "/groups"}, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login?next=%2Fgroups"


# ---------- Logout / signed-in indicator ----------


def test_logout_clears_session(client, post, db_session):
    account = _make_account(db_session)
    stamp_session(client, account)
    resp = post("/logout", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"
    # Signed out: the response instructs the browser to drop the session cookie.
    # (Asserted on the header because the test jar keeps manually-stamped
    # cookies; a real browser honors this deletion.)
    set_cookie = resp.headers.get("set-cookie", "")
    assert "session=" in set_cookie
    assert ("max-age=0" in set_cookie.lower()) or ("expires=" in set_cookie.lower())


def test_signed_in_page_shows_account_and_sign_out(client, db_session):
    account = _make_account(db_session, display_name="Ada Lovelace")
    stamp_session(client, account)
    resp = client.get("/groups")
    assert resp.status_code == 200
    assert "Ada Lovelace" in resp.text
    assert '<form method="post" action="/logout">' in resp.text


def test_signed_out_page_shows_sign_in_link(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert '<a class="nav-link" href="/login">Sign in</a>' in resp.text
    assert "Sign out" not in resp.text


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


def test_callback_email_verified_string_false_rejected(client, db_session, monkeypatch):
    """Defense-in-depth: a provider sending email_verified as the STRING
    "false" must not sign in (bool("false") would be True)."""
    from app.sso import _claim_is_true
    assert _claim_is_true("false") is False
    assert _claim_is_true("true") is True
    assert _claim_is_true(True) is True
    assert _claim_is_true(None) is False
    assert _claim_is_true("") is False


def test_callback_db_failure_rolls_back_no_account(client, db_session, monkeypatch):
    """A commit failure during account creation degrades to a 400 re-render and
    leaves no half-created account."""
    from sqlalchemy.orm import Session as _Session

    provider = FakeProvider(identity=Identity("sub-dbfail", "dbfail@example.com", True, "DB Fail"))
    monkeypatch.setitem(auth_routes.PROVIDERS, "google", provider)

    def boom(self):
        raise RuntimeError("db down")

    monkeypatch.setattr(_Session, "commit", boom)
    resp = client.get("/auth/google/callback")
    assert resp.status_code == 400
    assert "Sign-in failed" in resp.text
    monkeypatch.undo()
    assert db_session.scalar(
        select(Account).where(Account.email == "dbfail@example.com")
    ) is None
