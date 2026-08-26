"""Auth routes (M1, T1.2): login with PIN + attempt limiting, logout, /me."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.auth import LOCKOUT_ATTEMPTS, LOCKOUT_SECONDS, require_any
from app.db import get_db
from app.models import Person
from app.pins import verify_pin

router = APIRouter()

templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


def _now() -> datetime:
    """Naive-UTC now, matching SQLAlchemy's DateTime storage in SQLite."""
    return datetime.now(UTC).replace(tzinfo=None)


def _login_page(request: Request, error: str | None, status_code: int = 200):
    return templates.TemplateResponse(
        request, "login.html", {"error": error}, status_code=status_code
    )


@router.get("/login")
def login_page(request: Request):
    return _login_page(request, error=None)


@router.post("/login")
def login(
    request: Request,
    name: Annotated[str, Form()],
    pin: Annotated[str, Form()],
    db: Annotated[Session, Depends(get_db)],
):
    """Verify name + PIN; lock the person out after LOCKOUT_ATTEMPTS failures.

    Failure paths re-render the login form with an error (HTTP 401). Success
    resets the attempt counters, stores ``person_id`` in the signed session
    cookie, and 303-redirects to /people (PRG).
    """
    person = db.scalar(select(Person).where(Person.name == name.strip()))
    now = _now()
    if person is None or not person.is_active:
        return _login_page(request, "Name or PIN doesn't match.", status_code=401)

    if person.locked_until is not None and person.locked_until > now:
        remaining = max(1, math.ceil((person.locked_until - now).total_seconds()))
        return _login_page(
            request,
            f"Too many attempts — try again in {remaining} seconds.",
            status_code=401,
        )

    if not verify_pin(pin, person.pin_hash):
        # PBKDF2 verify happened above, so this write window is tiny. SQLite
        # serializes writers: the atomic UPDATE + same-transaction read-back
        # means concurrent failures cannot overwrite each other (the previous
        # read-modify-write collapsed 10 guesses into 1 counter increment).
        db.execute(
            update(Person)
            .where(Person.id == person.id)
            .values(failed_pin_attempts=Person.failed_pin_attempts + 1)
        )
        new_count, locked_until = db.execute(
            select(Person.failed_pin_attempts, Person.locked_until).where(
                Person.id == person.id
            )
        ).one()
        if locked_until is not None and locked_until > _now():
            # A concurrent failure locked the person while this request was
            # verifying the PIN; the straggler's increment must not inflate
            # the post-lock counter (concurrent writes serialize, so this
            # read-back reflects the committed lock state).
            db.execute(
                update(Person)
                .where(Person.id == person.id)
                .values(failed_pin_attempts=0)
            )
        elif new_count >= LOCKOUT_ATTEMPTS:
            db.execute(
                update(Person)
                .where(Person.id == person.id)
                .values(
                    failed_pin_attempts=0,
                    locked_until=_now() + timedelta(seconds=LOCKOUT_SECONDS),
                )
            )
        db.commit()
        return _login_page(request, "Wrong PIN.", status_code=401)

    person.failed_pin_attempts = 0
    person.locked_until = None
    db.commit()
    request.session["person_id"] = person.id
    return RedirectResponse("/people", status_code=303)


@router.post("/logout")
def logout(request: Request):
    """Clear the session cookie (works for any session, signed-in or not)."""
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@router.get("/me")
def me(request: Request, db: Annotated[Session, Depends(get_db)]):
    """JSON identity probe (T1.4): who am I on this device?"""
    person = require_any(request, db)
    return {
        "name": person.name,
        "is_admin": person.is_admin,
        "is_active": person.is_active,
    }
