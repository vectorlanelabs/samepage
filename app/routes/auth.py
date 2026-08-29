"""Auth routes (M2a): signup, email+password login, logout."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_account
from app.credentials import hash_password, is_valid_email, is_valid_password, verify_password
from app.db import get_db
from app.models import Account

router = APIRouter()

templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


def _login_page(request: Request, error: str | None, status_code: int = 200):
    return templates.TemplateResponse(
        request, "login.html", {"error": error}, status_code=status_code
    )


def _signup_page(request: Request, error: str | None, status_code: int = 200):
    return templates.TemplateResponse(
        request, "signup.html", {"error": error}, status_code=status_code
    )


@router.get("/login")
def login_page(request: Request, db: Annotated[Session, Depends(get_db)]):
    # Redirect to / if already signed in.
    if get_current_account(request, db) is not None:
        return RedirectResponse("/", status_code=303)
    return _login_page(request, error=None)


@router.post("/login")
def login(
    request: Request,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    db: Annotated[Session, Depends(get_db)],
):
    """Verify email + password.

    Failure paths re-render the login form with an error (HTTP 401). Success
    stores ``account_id`` in the signed session cookie and 303-redirects to / (PRG).
    """
    email = email.strip().lower()
    account = db.scalar(select(Account).where(Account.email == email))
    if account is None or not verify_password(password, account.password_hash):
        return _login_page(request, "Email or password doesn't match.", status_code=401)

    request.session["account_id"] = account.id
    return RedirectResponse("/", status_code=303)


@router.get("/signup")
def signup_page(request: Request, db: Annotated[Session, Depends(get_db)]):
    # Redirect to / if already signed in.
    if get_current_account(request, db) is not None:
        return RedirectResponse("/", status_code=303)
    return _signup_page(request, error=None)


@router.post("/signup")
def signup(
    request: Request,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    display_name: Annotated[str, Form()],
    db: Annotated[Session, Depends(get_db)],
):
    """Create an account with email + password + display_name.

    Failure paths re-render the signup form with an error (HTTP 400).
    Success stores ``account_id`` in session and 303-redirects to / (PRG).
    """
    email = email.strip().lower()
    display_name = display_name.strip()

    if not email:
        return _signup_page(request, "Email is required.", status_code=400)
    if not is_valid_email(email):
        return _signup_page(request, "Email is not valid.", status_code=400)
    if not password:
        return _signup_page(request, "Password is required.", status_code=400)
    if not is_valid_password(password):
        return _signup_page(request, "Password must be at least 8 characters.", status_code=400)
    if not display_name:
        return _signup_page(request, "Display name is required.", status_code=400)

    account = Account(
        email=email,
        password_hash=hash_password(password),
        display_name=display_name,
    )
    db.add(account)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return _signup_page(request, "That email is already in use.", status_code=400)

    request.session["account_id"] = account.id
    return RedirectResponse("/", status_code=303)


@router.post("/logout")
def logout(request: Request):
    """Clear the session cookie (works for any session, signed-in or not)."""
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
