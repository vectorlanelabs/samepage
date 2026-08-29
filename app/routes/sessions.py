"""Session routes (M3b): create, join by code, live lobby, host start/remove.

The session lifecycle (plan §5.6) is: ``lobby → voting → complete`` with
``expired`` reachable from either; this slice ships the lobby phase —
creation, join-by-code (no account required), the htmx-polled roster, and the
host's ``start voting`` transition (which only flips the status; the actual
voting UI is M3c). The join window is lobby-only for now: a visitor hitting a
``voting`` session sees a waiting state, not a ballot (§5.6), and joins are
refused outright for ``complete``/``expired`` sessions.

Session codes are the one cross-tenant guessing surface on the shared
deployment, so they are generated with collision retry against the permanent
UNIQUE ``session.code`` set and never recycled. ``GET /s/{code}`` and the
roster poll are deliberately public (no auth) — voting is open by link/code
per plan §2 — while every host mutation re-checks ``host_account_id``
server-side.
"""

from __future__ import annotations

import random
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_account, require_account, require_group_admin
from app.db import get_db
from app.models import (
    Account,
    Collection,
    Group,
    GroupAdmin,
    SessionParticipant,
    SessionTarget,
)
from app.models import (
    Session as VotingSession,
)
from app.session_logic import apply_transition, make_code
from app.templating import templates

router = APIRouter()

ENDED_STATUSES = ("complete", "expired")


def _owned_groups(db: Session, account: Account) -> list[dict]:
    """Groups the account owns or admins, as picker rows with their meal
    collections (same owner-or-admin outerjoin query as the collections hub —
    this form can only ever create a session into a group the account manages)."""
    rows = db.execute(
        select(Group.id, Group.name)
        .outerjoin(
            GroupAdmin,
            (GroupAdmin.group_id == Group.id) & (GroupAdmin.account_id == account.id),
        )
        .where(
            (Group.owner_account_id == account.id) | (GroupAdmin.account_id == account.id)
        )
        .order_by(Group.name, Group.id)
    ).all()
    groups: list[dict] = []
    for group_id, group_name in rows:
        collections = db.scalars(
            select(Collection)
            .where(Collection.group_id == group_id)
            .order_by(Collection.name, Collection.id)
        ).all()
        groups.append(
            {
                "id": group_id,
                "name": group_name,
                "collections": [{"id": c.id, "name": c.name} for c in collections],
            }
        )
    return groups


def _parse_int(value: str, default: int = 0) -> int:
    """Form int parsing: a missing/garbage value falls back to the default so
    the target validation below is the single source of truth."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _get_session_by_code(db: Session, code: str) -> VotingSession | None:
    """Look a session up by its permanent code. Codes are lowercase by
    construction; the lookup casefolds so hand-typed codes work."""
    return db.scalar(select(VotingSession).where(VotingSession.code == code.strip().lower()))


def _viewer_participant(request: Request, db: Session, session: VotingSession) -> SessionParticipant | None:
    """The participant row the signed session cookie points at, IF it still
    exists AND belongs to this session. A stale/foreign participant id is
    treated as no participant at all (join page again)."""
    participant_id = request.session.get("participant_id")
    if participant_id is None:
        return None
    participant = db.get(SessionParticipant, participant_id)
    if participant is None or participant.session_id != session.id:
        return None
    return participant


def _roster_rows(
    db: Session, session: VotingSession, viewer_participant_id: int | None
) -> list[dict]:
    """Participant rows for the lobby/roster partial, oldest joiner first."""
    participants = db.scalars(
        select(SessionParticipant)
        .where(SessionParticipant.session_id == session.id)
        .order_by(SessionParticipant.joined_at, SessionParticipant.id)
    ).all()
    return [
        {
            "id": p.id,
            "display_name": p.display_name,
            "is_host_row": p.account_id is not None and p.account_id == session.host_account_id,
            "is_you": p.id == viewer_participant_id,
        }
        for p in participants
    ]


def _lobby_context(
    request: Request,
    db: Session,
    session: VotingSession,
    account: Account | None,
    participant: SessionParticipant | None,
) -> dict:
    collection = db.get(Collection, session.collection_id) if session.collection_id else None
    is_host = account is not None and account.id == session.host_account_id
    viewer_participant_id = participant.id if participant is not None else None
    roster = _roster_rows(db, session, viewer_participant_id)
    return {
        "session": session,
        "collection_name": collection.name if collection else "Ad hoc session",
        "participants": roster,
        "participant_count": len(roster),
        "is_host": is_host,
    }


# --- Creation (host only) ----------------------------------------------------


@router.get("/sessions/new")
def new_session_page(request: Request, db: Annotated[Session, Depends(get_db)]):
    """New-session page: group picker + per-group collection picker (with an
    "Ad hoc (no collection)" option) + target inputs. An account with no
    groups gets the 'Create a group first.' landing, same as collection_new."""
    account = require_account(request, db)
    groups = _owned_groups(db, account)
    if not groups:
        return templates.TemplateResponse(request, "session_new.html", {"groups": []})
    return templates.TemplateResponse(
        request,
        "session_new.html",
        {
            "groups": groups,
            "selected_group_id": None,
            "selected_collection_id": None,
            "dinners": 3,
            "lunches": 0,
            "picks": 3,
            "error": None,
        },
    )


@router.post("/sessions")
def create_session(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    group_id: Annotated[str, Form()] = "",
    collection_id: Annotated[str, Form()] = "",
    dinners: Annotated[str, Form()] = "",
    lunches: Annotated[str, Form()] = "",
    picks: Annotated[str, Form()] = "",
):
    """Create a voting session (plan §5): status 'lobby', hosted by the
    signed-in account, scoped to one of its own groups.

    Validation is enforced, not assumed: the group must be owned/admined by
    the account (404 otherwise — no existence oracle), a given collection must
    belong to that exact group (404), and at least one target must be set
    (400). Meal collections take dinner/lunch targets (only tracks with count
    > 0 create rows); ad hoc sessions take a single picks target.
    """
    account = require_account(request, db)
    dinners_i, lunches_i, picks_i = (
        _parse_int(dinners),
        _parse_int(lunches),
        _parse_int(picks),
    )
    collection_id = collection_id.strip()

    def _re_render(error: str, status_code: int):
        groups = _owned_groups(db, account)
        try:
            selected_group = int(group_id)
        except (TypeError, ValueError):
            selected_group = None
        selected_collection = None
        if collection_id:
            try:
                selected_collection = int(collection_id)
            except (TypeError, ValueError):
                selected_collection = None
        return templates.TemplateResponse(
            request,
            "session_new.html",
            {
                "groups": groups,
                "selected_group_id": selected_group,
                "selected_collection_id": selected_collection,
                "dinners": dinners_i,
                "lunches": lunches_i,
                "picks": picks_i,
                "error": error,
            },
            status_code=status_code,
        )

    # 404 for a group that doesn't exist or isn't the account's to manage.
    try:
        group_id_int = int(group_id)
    except (TypeError, ValueError):
        raise HTTPException(404, "Group not found")
    _, group = require_group_admin(request, db, group_id_int)

    if collection_id:
        try:
            collection_id_int = int(collection_id)
        except (TypeError, ValueError):
            raise HTTPException(404, "Collection not found")
        collection = db.get(Collection, collection_id_int)
        if collection is None or collection.group_id != group.id:
            raise HTTPException(404, "Collection not found")
    else:
        collection_id_int = None

    if collection_id_int is not None:
        targets = []
        if dinners_i > 0:
            targets.append(("dinner", dinners_i))
        if lunches_i > 0:
            targets.append(("lunch", lunches_i))
        if not targets:
            return _re_render("Set at least one target.", 400)
    else:
        targets = [("picks", picks_i)]
        if picks_i <= 0:
            return _re_render("Picks must be at least 1.", 400)

    existing_codes = set(db.scalars(select(VotingSession.code)).all())
    code = make_code(existing_codes, random.Random())

    session = VotingSession(
        code=code,
        status="lobby",
        group_id=group.id,
        host_account_id=account.id,
        collection_id=collection_id_int,
    )
    db.add(session)
    db.flush()
    for track_label, target_count in targets:
        db.add(
            SessionTarget(
                session_id=session.id,
                track_label=track_label,
                target_count=target_count,
            )
        )
    db.commit()
    return RedirectResponse(f"/s/{session.code}", status_code=303)


# --- Join flow (no account required) -----------------------------------------


@router.get("/join")
def join_page(request: Request, code: str | None = None):
    """Public join landing: one code input. With JS the form navigates straight
    to /s/{code}; without JS it GETs /join?code=... and we redirect here."""
    if code:
        return RedirectResponse(f"/s/{code.strip().lower()}", status_code=302)
    return templates.TemplateResponse(request, "join.html", {})


@router.get("/s/{code}")
def session_page(request: Request, code: str, db: Annotated[Session, Depends(get_db)]):
    """The session front door: ended page for finished sessions, join page for
    strangers (waiting state while voting), the live lobby for participants
    and the host."""
    session = _get_session_by_code(db, code)
    if session is None:
        raise HTTPException(404, "Session not found")
    if session.status in ENDED_STATUSES:
        return templates.TemplateResponse(
            request, "session_ended.html", {"session": session}
        )

    account = get_current_account(request, db)
    participant = _viewer_participant(request, db, session)
    is_host = account is not None and account.id == session.host_account_id
    if participant is None and not is_host:
        return templates.TemplateResponse(
            request,
            "join_session.html",
            {
                "session": session,
                "prefill_name": account.display_name if account else "",
                "posted_name": "",
                "error": None,
            },
        )
    return templates.TemplateResponse(
        request,
        "session_lobby.html",
        _lobby_context(request, db, session, account, participant),
    )


@router.post("/s/{code}/join")
def join_session(
    request: Request,
    code: str,
    db: Annotated[Session, Depends(get_db)],
    display_name: Annotated[str, Form()] = "",
):
    """Join a session by code. No account required; a signed-in viewer's name
    is only a pre-fill (they can join as anyone). The join window is lobby-only
    in M3b — voting sessions show the waiting state, ended sessions refuse."""
    session = _get_session_by_code(db, code)
    if session is None:
        raise HTTPException(404, "Session not found")
    if session.status in ENDED_STATUSES:
        return templates.TemplateResponse(
            request, "session_ended.html", {"session": session}
        )
    if session.status == "voting":
        # §5.6: no mid-batch joins — the roster denominator is frozen at batch
        # start. M3c opens the between-batches window; today it's a waiting state.
        return templates.TemplateResponse(
            request,
            "join_session.html",
            {"session": session, "prefill_name": "", "posted_name": "", "error": None},
        )

    display_name = display_name.strip()
    if not display_name:
        return templates.TemplateResponse(
            request,
            "join_session.html",
            {
                "session": session,
                "prefill_name": "",
                "posted_name": display_name,
                "error": "Display name is required.",
            },
            status_code=400,
        )

    account = get_current_account(request, db)
    participant = SessionParticipant(
        session_id=session.id,
        account_id=account.id if account else None,
        display_name=display_name,
    )
    db.add(participant)
    session.last_activity_at = func.now()
    db.commit()
    request.session["participant_id"] = participant.id
    return RedirectResponse(f"/s/{session.code}", status_code=303)


# --- Lobby + polling ----------------------------------------------------------


@router.get("/s/{code}/roster")
def roster_partial(request: Request, code: str, db: Annotated[Session, Depends(get_db)]):
    """htmx poll target: ONLY the _roster.html partial (rows + count). Public —
    joining is open by code — but the host's Remove buttons render only when
    the viewer is the session host."""
    session = _get_session_by_code(db, code)
    if session is None:
        raise HTTPException(404, "Session not found")
    account = get_current_account(request, db)
    participant = _viewer_participant(request, db, session)
    viewer_participant_id = participant.id if participant is not None else None
    is_host = account is not None and account.id == session.host_account_id
    roster = _roster_rows(db, session, viewer_participant_id)
    return templates.TemplateResponse(
        request,
        "_roster.html",
        {
            "session": session,
            "participants": roster,
            "participant_count": len(roster),
            "is_host": is_host,
        },
    )


# --- Host actions --------------------------------------------------------------


@router.post("/s/{code}/start")
def start_voting(
    request: Request, code: str, db: Annotated[Session, Depends(get_db)]
):
    """Host-only 'start voting' (plan §5.6). Idempotent: a double-submit on an
    already-voting session applies once (apply_transition no-op), never an
    error. M3b only flips the status — batches arrive in M3c."""
    session = _get_session_by_code(db, code)
    if session is None:
        raise HTTPException(404, "Session not found")
    account = require_account(request, db)
    if session.host_account_id != account.id:
        raise HTTPException(403, "Only the host can start voting")
    try:
        session.status = apply_transition(session.status, "voting")
    except ValueError:
        raise HTTPException(400, "Session can't be started from its current state")
    session.last_activity_at = func.now()
    db.commit()
    return RedirectResponse(f"/s/{session.code}", status_code=303)


@router.post("/s/{code}/participants/{pid}/remove")
def remove_participant(
    request: Request,
    code: str,
    pid: int,
    db: Annotated[Session, Depends(get_db)],
):
    """Host-only participant removal, allowed only while no batch is open
    (§5.6: the keep rule is unanimity over the roster, so a ghost row must be
    removable while in the lobby). Never the host's own row."""
    session = _get_session_by_code(db, code)
    if session is None:
        raise HTTPException(404, "Session not found")
    account = require_account(request, db)
    if session.host_account_id != account.id:
        raise HTTPException(403, "Only the host can remove participants")
    if session.status != "lobby":
        raise HTTPException(400, "Can't remove participants after voting starts")
    participant = db.scalar(
        select(SessionParticipant).where(
            (SessionParticipant.id == pid) & (SessionParticipant.session_id == session.id)
        )
    )
    if participant is None:
        raise HTTPException(404, "Participant not found")
    if participant.account_id is not None and participant.account_id == session.host_account_id:
        raise HTTPException(400, "The host can't be removed")
    db.delete(participant)
    session.last_activity_at = func.now()
    db.commit()
    return RedirectResponse(f"/s/{session.code}", status_code=303)
