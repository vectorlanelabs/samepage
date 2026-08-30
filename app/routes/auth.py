"""Auth routes (M5a): Google SSO (OIDC) sign-in, logout, login page.

No passwords anywhere: sign-in is ``GET /auth/google`` → Google → ``GET
/auth/google/callback``, which creates/links an Account + AuthIdentity in one
transaction and stamps the signed session cookie. ``/signup`` is a pure
redirect to ``/login`` (the account-creation UI is Google's now).
"""

from __future__ import annotations

from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_account
from app.db import get_db
from app.models import Account, AuthIdentity
from app.settings import settings
from app.sso import PROVIDERS
from app.templating import templates

router = APIRouter()


def _safe_next(value: str | None) -> str:
    """Only allow a same-site relative path — never an absolute/protocol-relative
    URL (open-redirect guard). Rejects backslashes too: browsers normalize a
    leading ``/\\evil.com`` to ``//evil.com`` (protocol-relative) even though
    the raw string passes a naive ``startswith("//")`` check."""
    if value and value.startswith("/") and not value.startswith("//") and "\\" not in value:
        return value
    return "/"


def _login_page(request: Request, error: str | None, status_code: int = 200, next: str | None = None):
    return templates.TemplateResponse(
        request,
        "login.html",
        {"error": error, "next": next, "sso_configured": PROVIDERS["google"].configured, "chrome": "session"},
        status_code=status_code,
    )


@router.get("/login")
def login_page(request: Request, db: Annotated[Session, Depends(get_db)], next: str | None = None):
    # Redirect to / (or `next`) if already signed in.
    if get_current_account(request, db) is not None:
        return RedirectResponse(_safe_next(next), status_code=303)
    return _login_page(request, error=None, next=next)


@router.get("/auth/google")
async def google_authorize(request: Request, next: str | None = None):
    """Start the Google OAuth flow.

    The post-login destination is stashed in the session (already run through
    ``_safe_next``) and popped by the callback — never re-derived from the
    callback's query string, which is Google's to append to, not ours.
    """
    if not PROVIDERS["google"].configured:
        raise HTTPException(503, "Google sign-in is not configured")
    request.session["post_login_next"] = _safe_next(next)
    return await PROVIDERS["google"].authorize_redirect(
        request, settings.base_url + "/auth/google/callback"
    )


@router.get("/auth/google/callback")
async def google_callback(request: Request, db: Annotated[Session, Depends(get_db)]):
    """Finish the Google OAuth flow: resolve the identity to an Account and
    sign it in (one transaction: lookup-or-create Account + AuthIdentity)."""
    provider = PROVIDERS["google"]
    try:
        identity = await provider.get_identity(request)
    except Exception:  # noqa: BLE001 — ANY provider failure (network, bad
        # token, malformed claims) must degrade to a friendly re-render, never 500.
        return _login_page(request, "Sign-in failed — please try again.", status_code=400)
    if not identity.email_verified:
        return _login_page(request, "Your Google email isn't verified.", status_code=400)

    # Existing identity → its account. Otherwise an existing account with the
    # same verified email gets the identity linked to it; otherwise create a
    # brand-new account + identity together. Wrapped so a DB failure rolls back
    # and re-renders instead of 500ing mid-write (no half-created account).
    try:
        auth_identity = db.scalar(
            select(AuthIdentity).where(
                AuthIdentity.provider == "google", AuthIdentity.subject == identity.subject
            )
        )
        if auth_identity is not None:
            account = db.get(Account, auth_identity.account_id)
        else:
            account = db.scalar(select(Account).where(Account.email == identity.email))
            if account is None:
                account = Account(
                    email=identity.email,
                    display_name=identity.display_name or identity.email.split("@")[0],
                )
                db.add(account)
                db.flush()
            db.add(
                AuthIdentity(
                    account_id=account.id,
                    provider="google",
                    subject=identity.subject,
                    email=identity.email,
                )
            )
        db.commit()
    except Exception:  # noqa: BLE001 — a DB failure must roll back and degrade,
        # never leave a half-written account or bubble a 500 to the browser.
        db.rollback()
        return _login_page(request, "Sign-in failed — please try again.", status_code=400)

    request.session["account_id"] = account.id
    request.session["account_name"] = account.display_name
    # Stashed at /auth/google time and already _safe_next'd — never re-derive
    # from the callback's query string here.
    return RedirectResponse(request.session.pop("post_login_next", "/"), status_code=303)


@router.get("/signup")
def signup_page(next: str | None = None):
    """Account creation is Google's now — /signup just forwards to /login."""
    if next:
        return RedirectResponse(f"/login?{urlencode({'next': next})}", status_code=303)
    return RedirectResponse("/login", status_code=303)


@router.post("/logout")
def logout(request: Request):
    """Clear the session cookie (works for any session, signed-in or not)."""
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
