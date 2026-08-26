"""Identity & auth helpers (M1, T1.2–T1.3): session person lookup + guards.

The signed session cookie stores only ``person_id`` (D2). Everything else is
derived from the database on every request, so deactivating a person
immediately invalidates any live session.
"""

from __future__ import annotations

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.models import Person

# PIN-verify attempt limiting (T1.2): N failures within a window lock the
# person out for LOCKOUT_SECONDS.
LOCKOUT_ATTEMPTS = 5
LOCKOUT_SECONDS = 60


def get_current_person(request: Request, db: Session) -> Person | None:
    """Return the signed-in Person, or None when absent/inactive.

    A deactivated person's session is dead on the next request — there is no
    stale-session window (D16 deactivate-not-delete).
    """
    person_id = request.session.get("person_id")
    if person_id is None:
        return None
    person = db.get(Person, person_id)
    if person is None or not person.is_active:
        return None
    return person


def require_admin(request: Request, db: Session) -> Person:
    """Guard for admin-only routes: 403 unless an active admin is signed in."""
    person = get_current_person(request, db)
    if person is None or not person.is_admin:
        raise HTTPException(403, "Admin required")
    return person


def require_any(request: Request, db: Session) -> Person:
    """Guard for sign-in-required routes: 401 unless an active person is in."""
    person = get_current_person(request, db)
    if person is None:
        raise HTTPException(401, "Sign in required")
    return person
