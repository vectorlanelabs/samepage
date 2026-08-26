"""People management routes (M1, T1.1–T1.3): roster CRUD, admin gating.

People are deactivated, never deleted (D16) — there is deliberately no DELETE
endpoint. The first person on an empty install is bootstrapped as admin
(T1.3); every later mutation requires an active admin who is not the target
(for admin-toggle / deactivate / PIN-change — you can't demote or lock
yourself out).
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.db import get_db
from app.models import Person
from app.pins import hash_pin, is_valid_pin

router = APIRouter()

templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")

# Per-person avatar palette, cycled by id % 8 (Design Handoff).
PEOPLE_HUES = [20, 90, 150, 220, 300, 60, 320, 180]

# Serialize the first-person bootstrap check+insert (T1.3): two concurrent
# POSTs must not both observe count == 0 and both become admin. A threading
# lock suffices because the deployment is a single uvicorn process;
# multi-worker deployments would need a DB-level guard (e.g. a unique
# partial index on is_admin) instead.
_bootstrap_lock = threading.Lock()


def _roster_rows(db: Session, current: Person | None) -> list[dict]:
    people = db.scalars(select(Person).order_by(Person.id)).all()
    return [
        {
            "id": person.id,
            "name": person.name,
            "initial": person.name[:1].upper(),
            "hue": PEOPLE_HUES[person.id % len(PEOPLE_HUES)],
            "is_admin": person.is_admin,
            "is_active": person.is_active,
            "is_self": current is not None and person.id == current.id,
        }
        for person in people
    ]


def _people_page(
    request: Request,
    db: Session,
    current: Person | None,
    error: str | None = None,
    status_code: int = 200,
):
    return templates.TemplateResponse(
        request,
        "people.html",
        {"people": _roster_rows(db, current), "error": error},
        status_code=status_code,
    )


def _get_person_or_404(db: Session, person_id: int) -> Person:
    person = db.get(Person, person_id)
    if person is None:
        raise HTTPException(404, "No such person")
    return person


def _forbid_self(person_id: int, current: Person) -> None:
    if person_id == current.id:
        raise HTTPException(403, "You cannot change your own account")


@router.get("/people")
def people_page(request: Request, db: Annotated[Session, Depends(get_db)]):
    """Roster (admin-only): every person, ordered by id, never deleted."""
    current = require_admin(request, db)
    return _people_page(request, db, current)


@router.get("/people/{person_id}")
def person_detail(request: Request, person_id: int, db: Annotated[Session, Depends(get_db)]):
    """Person detail (plan §8 ``GET /people/{id}``): the roster page, 404 for
    unknown ids. Exists so that a DELETE to this path is a 405, not a 404 —
    people are deactivated, never deleted (D16)."""
    current = require_admin(request, db)
    _get_person_or_404(db, person_id)
    return _people_page(request, db, current)


@router.post("/people")
def create_person(
    request: Request,
    name: Annotated[str, Form()],
    pin: Annotated[str, Form()],
    db: Annotated[Session, Depends(get_db)],
):
    """Create a person. Bootstrap rule (T1.3): the first person on an empty
    install is automatically admin; every other creation requires an admin."""
    # The whole count-check → validation → insert → commit must be atomic:
    # two concurrent first-person POSTs would otherwise both see count == 0
    # and both bootstrap as admin. require_admin inside the lock is a read —
    # safe to hold the lock across it.
    with _bootstrap_lock:
        person_count = db.scalar(select(func.count()).select_from(Person)) or 0
        if person_count == 0:
            current = None
            is_admin = True
        else:
            current = require_admin(request, db)
            is_admin = False

        name = name.strip()
        if not name:
            return _people_page(
                request, db, current, error="Name is required.", status_code=400
            )
        if not is_valid_pin(pin):
            return _people_page(
                request, db, current, error="PIN must be exactly 4 digits.", status_code=400
            )

        person = Person(name=name, pin_hash=hash_pin(pin), is_admin=is_admin, is_active=True)
        db.add(person)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return _people_page(
                request, db, current, error="That name already exists.", status_code=400
            )
        return RedirectResponse("/people", status_code=303)


@router.post("/people/{person_id}/admin")
def toggle_admin(
    request: Request, person_id: int, db: Annotated[Session, Depends(get_db)]
):
    """Toggle another person's admin flag (you can't demote yourself)."""
    current = require_admin(request, db)
    _forbid_self(person_id, current)
    person = _get_person_or_404(db, person_id)
    person.is_admin = not person.is_admin
    db.commit()
    return RedirectResponse("/people", status_code=303)


@router.post("/people/{person_id}/deactivate")
def deactivate_person(
    request: Request, person_id: int, db: Annotated[Session, Depends(get_db)]
):
    """Deactivate (never delete — D16). You can't deactivate yourself."""
    current = require_admin(request, db)
    _forbid_self(person_id, current)
    person = _get_person_or_404(db, person_id)
    person.is_active = False
    db.commit()
    return RedirectResponse("/people", status_code=303)


@router.post("/people/{person_id}/reactivate")
def reactivate_person(
    request: Request, person_id: int, db: Annotated[Session, Depends(get_db)]
):
    """Bring a deactivated person back (admin-only)."""
    require_admin(request, db)
    person = _get_person_or_404(db, person_id)
    person.is_active = True
    db.commit()
    return RedirectResponse("/people", status_code=303)


@router.post("/people/{person_id}/pin")
def change_pin(
    request: Request,
    person_id: int,
    pin: Annotated[str, Form()],
    db: Annotated[Session, Depends(get_db)],
):
    """Admin resets another person's PIN; clears any lockout state."""
    current = require_admin(request, db)
    _forbid_self(person_id, current)
    person = _get_person_or_404(db, person_id)
    if not is_valid_pin(pin):
        return _people_page(
            request, db, current, error="PIN must be exactly 4 digits.", status_code=400
        )
    person.pin_hash = hash_pin(pin)
    person.failed_pin_attempts = 0
    person.locked_until = None
    db.commit()
    return RedirectResponse("/people", status_code=303)
