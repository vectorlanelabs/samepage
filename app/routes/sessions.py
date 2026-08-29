"""Session routes (M3b + M3c): create, join by code, live lobby, host
start/remove, and the voting flow.

The session lifecycle (plan §5.6) is: ``lobby → voting → complete`` with
``expired`` reachable from either. M3b shipped the lobby phase — creation,
join-by-code (no account required), the htmx-polled roster, and the host's
``start voting`` transition. M3c extends ``start voting`` to assemble batch #1
(collection-backed sessions only; ad hoc options entry is a later release) and
adds the one-option-at-a-time voting flow: the voting card, the done/waiting
state, the host's watching overview, and the vote submission endpoint.
Idempotency: a double-submitted ``start`` never assembles a second batch, and a
recorded vote stands (re-submits never flip it). The join window stays
lobby-only for now: a visitor hitting a ``voting`` session sees a waiting
state, not a ballot (§5.6), and joins are refused outright for
``complete``/``expired`` sessions.

Session codes are the one cross-tenant guessing surface on the shared
deployment, so they are generated with collision retry against the permanent
UNIQUE ``session.code`` set and never recycled. ``GET /s/{code}`` and the
roster/voting-status polls are deliberately public (no auth) — voting is open
by link/code per plan §2 — while every host mutation re-checks
``host_account_id`` server-side. The two code-entry routes are throttled per
client IP (20 lookups/minute, M5b: ``app/ratelimit.py``); the polls are not.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.auth import get_current_account, require_account, require_group_admin
from app.db import get_db
from app.models import (
    Account,
    Batch,
    BatchItem,
    BatchResponse,
    Collection,
    Group,
    GroupAdmin,
    Item,
    ItemTag,
    MealDetail,
    MealType,
    SessionParticipant,
    SessionTarget,
    Tag,
)
from app.models import (
    Session as VotingSession,
)
from app.ratelimit import JOIN_LIMITER, client_ip
from app.routes.library import _item_ingredients, _item_meal_types, _types_label
from app.session_logic import (
    BATCH_SIZE,
    Outcome,
    Tally,
    apply_batch_close,
    apply_transition,
    assemble_batch,
    classify,
    make_code,
    next_seq,
)
from app.templating import templates

router = APIRouter()

ENDED_STATUSES = ("complete", "expired")

# §5.5 rule 3: a lobby/voting session with no activity for this many hours
# becomes 'expired'. Enforcement is lazy — any route that loads a session
# first applies the expiry check (no scheduler/background job).
EXPIRY_HOURS = 24


def _enforce_join_rate_limit(request: Request) -> None:
    """Throttle the code-guessing surface (M5b, plan §5.6/§8): 20 code
    lookups per IP per minute via the in-memory JOIN_LIMITER. Must run BEFORE
    the DB lookup so a guesser can't even probe whether a code exists. The
    roster/voting-status polls are deliberately NOT limited here — they fire
    every 2s from every participant (a normal lobby would 429) and are hit by
    already-joined clients, not code guessers."""
    if JOIN_LIMITER.hit(client_ip(request)):
        raise HTTPException(429, "Too many attempts — slow down.")


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


# --- Batch + voting helpers (M3c) -------------------------------------------


def _open_batch(db: Session, session: VotingSession) -> Batch | None:
    """The session's open batch — at most one by construction — or None."""
    return db.scalar(
        select(Batch)
        .where((Batch.session_id == session.id) & (Batch.status == "open"))
        .order_by(Batch.seq)
    )


def _batch_items(db: Session, batch: Batch) -> list[BatchItem]:
    """A batch's options in voting (sort) order."""
    return list(
        db.scalars(
            select(BatchItem)
            .where(BatchItem.batch_id == batch.id)
            .order_by(BatchItem.sort_order, BatchItem.id)
        ).all()
    )


def _responded_item_ids(db: Session, batch: Batch, participant: SessionParticipant) -> set[int]:
    """The batch_item ids this participant has already answered in this batch."""
    return set(
        db.scalars(
            select(BatchResponse.batch_item_id).where(
                (BatchResponse.session_participant_id == participant.id)
                & BatchResponse.batch_item_id.in_(
                    select(BatchItem.id).where(BatchItem.batch_id == batch.id)
                )
            )
        ).all()
    )


def _next_option(
    db: Session, batch: Batch | None, participant: SessionParticipant
) -> BatchItem | None:
    """The participant's next unanswered option in the open batch (voting
    order), or None once they've voted on every option."""
    if batch is None:
        return None
    responded = _responded_item_ids(db, batch, participant)
    for batch_item in _batch_items(db, batch):
        if batch_item.id not in responded:
            return batch_item
    return None


def _progress(
    db: Session, batch: Batch | None, participant: SessionParticipant
) -> tuple[int, int]:
    """(responded_count, total_count) for one participant in this batch."""
    if batch is None:
        return 0, 0
    items = _batch_items(db, batch)
    return len(_responded_item_ids(db, batch, participant)), len(items)


def _voting_progress_counts(db: Session, session: VotingSession) -> tuple[int, int]:
    """(finished, roster): roster is the participant count; finished is how
    many participants have responded to every option in the open batch."""
    roster = db.scalar(
        select(func.count())
        .select_from(SessionParticipant)
        .where(SessionParticipant.session_id == session.id)
    ) or 0
    open_batch = _open_batch(db, session)
    if open_batch is None:
        return roster, roster  # nothing to respond to → vacuously finished
    total_items = db.scalar(
        select(func.count()).select_from(BatchItem).where(BatchItem.batch_id == open_batch.id)
    ) or 0
    if total_items == 0:
        return roster, roster
    counts = db.execute(
        select(BatchResponse.session_participant_id, func.count(BatchResponse.id))
        .where(
            BatchResponse.session_participant_id.in_(
                select(SessionParticipant.id).where(SessionParticipant.session_id == session.id)
            ),
            BatchResponse.batch_item_id.in_(
                select(BatchItem.id).where(BatchItem.batch_id == open_batch.id)
            ),
        )
        .group_by(BatchResponse.session_participant_id)
    ).all()
    finished = sum(1 for _pid, responded in counts if responded == total_items)
    return finished, roster


# Meal tracks in canonical order (matches the library's MEAL_TYPES order).
_MEAL_TRACK_ORDER = {"breakfast": 0, "lunch": 1, "dinner": 2}
_MEAL_TRACK_LABELS = {"breakfast": "Breakfasts", "lunch": "Lunches", "dinner": "Dinners"}


def _track_order(track_label: str) -> tuple[int, str]:
    """Deterministic track ordering: the meal tracks (breakfast, lunch, dinner)
    first in that order, then any other label alphabetically. Shared by target
    progress, batch assembly, and the completion plan."""
    if track_label in _MEAL_TRACK_ORDER:
        return (_MEAL_TRACK_ORDER[track_label], "")
    return (len(_MEAL_TRACK_ORDER), track_label)


def _track_display_label(track_label: str) -> str:
    """Human label for progress/plan summaries: 'Breakfasts'/'Lunches'/'Dinners'
    for the meal tracks, any other label capitalized."""
    return _MEAL_TRACK_LABELS.get(track_label, track_label.capitalize())


def _first_track(db: Session, session: VotingSession) -> str | None:
    """The session's first track with a positive target, in _track_order. None
    when the session has no targets (defensive — creation always writes at
    least one)."""
    targets = db.scalars(
        select(SessionTarget).where(SessionTarget.session_id == session.id)
    ).all()
    for target in sorted(targets, key=lambda t: _track_order(t.track_label)):
        if target.target_count > 0:
            return target.track_label
    return None


def _eligible_item_ids(db: Session, session: VotingSession, track: str) -> list[int]:
    """Non-archived items in the session's collection eligible for the track —
    a meal track ('breakfast'/'lunch'/'dinner') selects items whose meal-type
    set includes that slot; any other track label selects all items. Ordered by
    normalized_name for deterministic batches (recency-weighting is a post-MVP
    refinement)."""
    stmt = select(Item.id).where(
        (Item.collection_id == session.collection_id) & Item.archived_at.is_(None)
    )
    if track in _MEAL_TRACK_ORDER:
        stmt = stmt.where(
            Item.id.in_(select(MealType.item_id).where(MealType.meal_type == track))
        )
    return list(db.scalars(stmt.order_by(Item.normalized_name, Item.id)).all())


def _track_progress(db: Session, session: VotingSession) -> list[dict]:
    """Per-target progress across the session's batches: for each
    ``SessionTarget`` row, how many BatchItem outcomes in
    ('kept_unanimous', 'kept_host') that track has so far, plus
    ``remaining`` and ``met``. Ordered by ``_track_order`` (dinner, lunch,
    then others alphabetically). Aggregate/outcome-only — no participant data."""
    targets = db.scalars(
        select(SessionTarget).where(SessionTarget.session_id == session.id)
    ).all()
    kept_rows = db.execute(
        select(Batch.track_label, func.count(BatchItem.id))
        .join(BatchItem, BatchItem.batch_id == Batch.id)
        .where(
            (Batch.session_id == session.id)
            & BatchItem.outcome.in_([Outcome.KEPT_UNANIMOUS.value, Outcome.KEPT_HOST.value])
        )
        .group_by(Batch.track_label)
    ).all()
    kept_by_track = dict(kept_rows)
    progress = []
    for target in sorted(targets, key=lambda t: _track_order(t.track_label)):
        kept = kept_by_track.get(target.track_label, 0)
        progress.append(
            {
                "track_label": target.track_label,
                "label": _track_display_label(target.track_label),
                "target_count": target.target_count,
                "kept": kept,
                "remaining": max(0, target.target_count - kept),
                "met": kept >= target.target_count,
            }
        )
    return progress


def _all_targets_met(db: Session, session: VotingSession) -> bool:
    """True when every track's kept count meets its target (the session has
    nothing left to vote toward — the host finishes)."""
    return all(row["met"] for row in _track_progress(db, session))


def _already_offered_ids(db: Session, session: VotingSession) -> set[int]:
    """Every item_id ever offered in ANY batch of this session (across all
    tracks) — the exclusion set for the next batch's assembly."""
    return set(
        db.scalars(
            select(BatchItem.item_id)
            .join(Batch, Batch.id == BatchItem.batch_id)
            .where(Batch.session_id == session.id)
        ).all()
    )


def _next_batch_assembly(db: Session, session: VotingSession) -> tuple[str | None, list[int]]:
    """What the next batch would be: ``(track_label, chosen_ids)`` for the
    first track in order with ``remaining > 0`` whose pool still has un-offered
    items, or ``(None, [])`` when all targets are met or every remaining
    track's pool is exhausted (the host then finishes with fewer than target).
    Preconditions (no open batch, no outcome-NULL pending items) are the
    ROUTE's job — this helper only does the pool math."""
    progress = _track_progress(db, session)
    already_offered = _already_offered_ids(db, session)
    for row in progress:
        if row["remaining"] <= 0:
            continue
        eligible_ids = _eligible_item_ids(db, session, row["track_label"])
        chosen = assemble_batch(eligible_ids, already_offered, size=BATCH_SIZE)
        if chosen:
            return row["track_label"], chosen
    return None, []


def _expire_if_stale(db: Session, session: VotingSession) -> bool:
    """Lazy §5.5 rule 3 expiry, applied at the top of every route that loads a
    session: a 'lobby'/'voting' session with no activity for EXPIRY_HOURS
    becomes 'expired' — participants are deleted (rule 2), an abandoned open
    batch's per-person vote rows are deleted (rule 4; the batch stays open and
    unreported, outcomes NULL/counts 0), and finished_at is stamped. Returns
    True when it just expired. 'complete' sessions are terminal and never
    expire. The caller commits nothing further — this helper commits."""
    if session.status not in ("lobby", "voting"):
        return False
    last_activity = session.last_activity_at
    if last_activity is None:
        last_activity = session.created_at
    if last_activity is None:
        return False
    if last_activity.tzinfo is None:
        last_activity = last_activity.replace(tzinfo=UTC)
    if last_activity >= datetime.now(UTC) - timedelta(hours=EXPIRY_HOURS):
        return False
    session.status = apply_transition(session.status, "expired")
    db.execute(
        delete(BatchResponse).where(
            BatchResponse.batch_item_id.in_(
                select(BatchItem.id).where(
                    BatchItem.batch_id.in_(
                        select(Batch.id).where(
                            (Batch.session_id == session.id) & (Batch.status == "open")
                        )
                    )
                )
            )
        )
    )
    db.execute(delete(SessionParticipant).where(SessionParticipant.session_id == session.id))
    session.finished_at = func.now()
    db.commit()
    return True


def _completion_context(db: Session, session: VotingSession) -> dict:
    """Render data for the completion view: every KEPT item across all of the
    session's batches (outcome in ('kept_unanimous', 'kept_host')), joined to
    Item for the name and grouped by track. Aggregate/outcome only — no
    participant data exists anymore (§5.5)."""
    collection = db.get(Collection, session.collection_id) if session.collection_id else None
    rows = db.execute(
        select(BatchItem.outcome, Item.name, Batch.track_label)
        .join(Batch, Batch.id == BatchItem.batch_id)
        .join(Item, Item.id == BatchItem.item_id)
        .where(
            (Batch.session_id == session.id)
            & BatchItem.outcome.in_([Outcome.KEPT_UNANIMOUS.value, Outcome.KEPT_HOST.value])
        )
        .order_by(Batch.track_label, Item.normalized_name, Item.id)
    ).all()
    by_track: dict[str, list[dict]] = {}
    for outcome, name, track in rows:
        by_track.setdefault(track, []).append(
            {
                "name": name,
                "label": (
                    "everyone agreed"
                    if outcome == Outcome.KEPT_UNANIMOUS.value
                    else "host pick"
                ),
            }
        )
    kept_groups = [
        {
            "track_label": track,
            "label": _track_display_label(track),
            "kept_items": items,
        }
        for track, items in sorted(by_track.items(), key=lambda kv: _track_order(kv[0]))
    ]
    return {
        "session": session,
        "collection_name": collection.name if collection else None,
        "kept_groups": kept_groups,
    }


def _option_data(db: Session, session: VotingSession, batch_item: BatchItem) -> dict:
    """Render data for one option on the voting card: name, type label, tags,
    and the optional recipe link (collection-backed items only in M3c)."""
    item = db.get(Item, batch_item.item_id) if batch_item.item_id is not None else None
    if item is None:
        return {
            "batch_item_id": batch_item.id,
            "name": batch_item.ad_hoc_label or "",
            "type_label": None,
            "tags": [],
            "recipe_url": None,
        }
    detail = db.scalar(select(MealDetail).where(MealDetail.item_id == item.id))
    tags = list(
        db.scalars(
            select(Tag.name)
            .join(ItemTag, ItemTag.tag_id == Tag.id)
            .where(ItemTag.item_id == item.id)
            .order_by(Tag.name)
        ).all()
    )
    ingredients = _item_ingredients(db, item.id)
    has_recipe = bool(
        ingredients or (detail and (detail.source_url or detail.recipe_text))
    )
    type_label = _types_label(_item_meal_types(db, item.id)) or None
    return {
        "batch_item_id": batch_item.id,
        "name": item.name,
        "type_label": type_label,
        "tags": tags,
        "recipe_url": (
            f"/collections/{session.collection_id}/items/{item.id}" if has_recipe else None
        ),
    }


def _close_batch(db: Session, session: VotingSession, batch: Batch, *, manual: bool) -> None:
    """Close one batch (plan §5.5/§5.6): roll up aggregate outcomes, update the
    Item offer/keep counters, DELETE every per-person vote row, and stamp the
    batch closed — all in the CALLER's transaction (the caller commits).

    Idempotent (CLAUDE.md #7): a batch that isn't 'open' is a no-op, so a
    double-submitted close (or a double auto-close) applies exactly once.
    ``manual`` selects D5 semantics — on a manual close, roster members who
    didn't record a 'yes' count as 'no' — but both paths build the same
    ``Tally(yes, roster_size - yes)``: on auto-close everyone has voted, so
    ``roster_size - yes`` equals the recorded no count.
    """
    if batch.status != "open":
        return
    roster_size = (
        db.scalar(
            select(func.count())
            .select_from(SessionParticipant)
            .where(SessionParticipant.session_id == session.id)
        )
        or 0
    )
    for batch_item in _batch_items(db, batch):
        yes = (
            db.scalar(
                select(func.count())
                .select_from(BatchResponse)
                .where(
                    (BatchResponse.batch_item_id == batch_item.id)
                    & (BatchResponse.choice == "yes")
                )
            )
            or 0
        )
        tally = Tally(yes=yes, no=roster_size - yes)
        batch_item.yes_count = tally.yes
        batch_item.no_count = tally.no
        result = classify(tally, roster_size)
        if result == Outcome.KEPT_UNANIMOUS.value:
            batch_item.outcome = Outcome.KEPT_UNANIMOUS.value
        elif result == Outcome.NOT_KEPT.value:
            batch_item.outcome = Outcome.NOT_KEPT.value
        # 'majority' → outcome stays NULL: PENDING the host's accept/pass. A
        # closed batch with outcome NULL means "awaiting host", distinguished
        # from an open batch by batch.status.
        if batch_item.item_id is not None:
            item = db.get(Item, batch_item.item_id)
            if item is not None:
                item.times_offered += 1
                if batch_item.outcome == Outcome.KEPT_UNANIMOUS.value:
                    item.times_kept += 1
                    item.last_kept_at = func.now()
    db.execute(
        delete(BatchResponse).where(
            BatchResponse.batch_item_id.in_(
                select(BatchItem.id).where(BatchItem.batch_id == batch.id)
            )
        )
    )
    batch.status = apply_batch_close(batch.status)
    batch.closed_at = func.now()
    session.last_activity_at = func.now()


def _results_context(
    db: Session, session: VotingSession, batch: Batch, account: Account | None
) -> dict:
    """Render data for the results screen: the closed batch's items grouped by
    outcome with AGGREGATE counts only (yes_count/no_count) — never who voted
    which way (vote privacy is the strong invariant, CLAUDE.md #4) — plus the
    session's target progress and what the host can do next (M3e)."""
    collection = db.get(Collection, session.collection_id) if session.collection_id else None
    is_host = account is not None and account.id == session.host_account_id
    rows = []
    for batch_item in _batch_items(db, batch):
        data = _option_data(db, session, batch_item)
        rows.append(
            {
                "batch_item_id": batch_item.id,
                "name": data["name"],
                "type_label": data["type_label"],
                "tags": data["tags"],
                "yes_count": batch_item.yes_count,
                "no_count": batch_item.no_count,
                "outcome": batch_item.outcome,
            }
        )
    track_progress = _track_progress(db, session)
    all_targets_met = all(row["met"] for row in track_progress)
    next_track, _ = _next_batch_assembly(db, session)
    return {
        "session": session,
        "collection_name": collection.name if collection else "Ad hoc session",
        "is_host": is_host,
        "batch": batch,
        "kept_unanimous": [r for r in rows if r["outcome"] == Outcome.KEPT_UNANIMOUS.value],
        "pending": [r for r in rows if r["outcome"] is None],
        "not_kept": [r for r in rows if r["outcome"] == Outcome.NOT_KEPT.value],
        "track_progress": track_progress,
        "all_targets_met": all_targets_met,
        "next_batch_available": next_track is not None,
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
            "breakfasts": 0,
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
    breakfasts: Annotated[str, Form()] = "",
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
    breakfasts_i, dinners_i, lunches_i, picks_i = (
        _parse_int(breakfasts),
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
                "breakfasts": breakfasts_i,
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
        if breakfasts_i > 0:
            targets.append(("breakfast", breakfasts_i))
        if lunches_i > 0:
            targets.append(("lunch", lunches_i))
        if dinners_i > 0:
            targets.append(("dinner", dinners_i))
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
    """The session front door: the completion plan for a finished session, the
    ended page for an expired one, the join page for strangers (waiting state
    while voting), the live lobby for participants and the host, and — once
    voting — the one-option-at-a-time voting card / done state for
    participants and a watching overview for a host who never joined."""
    _enforce_join_rate_limit(request)  # M5b: throttle code guessing, pre-lookup
    session = _get_session_by_code(db, code)
    if session is None:
        raise HTTPException(404, "Session not found")
    _expire_if_stale(db, session)  # lazy §5.5 expiry on load
    if session.status == "complete":
        # M3e: the resulting plan is public — anyone with the code sees it.
        return templates.TemplateResponse(
            request, "session_complete.html", _completion_context(db, session)
        )
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

    if session.status == "lobby":
        return templates.TemplateResponse(
            request,
            "session_lobby.html",
            _lobby_context(request, db, session, account, participant),
        )

    # status == 'voting'
    if session.collection_id is None:
        # Ad hoc sessions: no batch exists (options entry is a later release);
        # session_lobby.html renders the "coming soon" placeholder.
        return templates.TemplateResponse(
            request,
            "session_lobby.html",
            _lobby_context(request, db, session, account, participant),
        )

    open_batch = _open_batch(db, session)
    if open_batch is None:
        # No open batch but a closed one exists → the results screen for the
        # most recent closed batch (M3d). Its per-person votes are already
        # deleted (§5.5); only the aggregates on batch_item remain.
        closed_batch = db.scalar(
            select(Batch)
            .where((Batch.session_id == session.id) & (Batch.status == "closed"))
            .order_by(Batch.closed_at.desc(), Batch.id.desc())
        )
        if closed_batch is not None:
            return templates.TemplateResponse(
                request,
                "batch_results.html",
                _results_context(db, session, closed_batch, account),
            )

    if participant is not None:
        responded, total = _progress(db, open_batch, participant)
        next_option = _next_option(db, open_batch, participant)
        if next_option is not None:
            return templates.TemplateResponse(
                request,
                "voting_card.html",
                {
                    "session": session,
                    "option": _option_data(db, session, next_option),
                    "responded": responded,
                    "total": total,
                },
            )
        finished, roster = _voting_progress_counts(db, session)
        return templates.TemplateResponse(
            request,
            "voting_done.html",
            {
                "session": session,
                "finished": finished,
                "roster": roster,
                "is_host": is_host,
                "has_open_batch": open_batch is not None,
            },
        )

    # The host watching without having joined: an overview + htmx poll.
    finished, roster = _voting_progress_counts(db, session)
    context = _lobby_context(request, db, session, account, participant)
    context["finished"] = finished
    context["roster"] = roster
    context["has_open_batch"] = open_batch is not None
    return templates.TemplateResponse(request, "session_lobby.html", context)


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
    _enforce_join_rate_limit(request)  # M5b: throttle code guessing, pre-lookup
    session = _get_session_by_code(db, code)
    if session is None:
        raise HTTPException(404, "Session not found")
    _expire_if_stale(db, session)  # lazy §5.5 expiry before any mutation
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
    _expire_if_stale(db, session)  # lazy §5.5 expiry on load
    if session.status in ENDED_STATUSES:
        return templates.TemplateResponse(
            request, "_session_ended_note.html", {"session": session}
        )
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
    """Host-only 'start voting' (plan §5.6). On a fresh lobby→voting transition
    this assembles batch #1 in the SAME transaction: the session's first
    positive track ('dinner', then 'lunch', then others alphabetically), the
    non-archived items in its collection whose type matches that track, capped
    at BATCH_SIZE. An empty pool refuses the start (400, session stays in the
    lobby). Idempotent: a double-submit on an already-voting session applies
    once (apply_transition no-op) and never assembles a second batch — assembly
    is guarded by "no open batch exists"."""
    session = _get_session_by_code(db, code)
    if session is None:
        raise HTTPException(404, "Session not found")
    _expire_if_stale(db, session)  # lazy §5.5 expiry before any mutation
    account = require_account(request, db)
    if session.host_account_id != account.id:
        raise HTTPException(403, "Only the host can start voting")
    if session.status in ENDED_STATUSES:
        raise HTTPException(400, "This session is over.")
    try:
        target_status = apply_transition(session.status, "voting")
    except ValueError:
        raise HTTPException(400, "Session can't be started from its current state")

    # Collection-backed sessions only; ad hoc option entry is deferred. Guard
    # with "no open batch exists" so a double-submitted start never assembles
    # a second batch.
    if session.collection_id is not None and _open_batch(db, session) is None:
        track = _first_track(db, session)
        if track is None:
            raise HTTPException(400, "This session has no targets to vote on")
        eligible_ids = _eligible_item_ids(db, session, track)
        chosen = assemble_batch(eligible_ids, already_offered=set(), size=BATCH_SIZE)
        if not chosen:
            context = _lobby_context(
                request, db, session, account, _viewer_participant(request, db, session)
            )
            context["start_error"] = (
                f"No items available for the {track} track — add items to this collection first."
            )
            return templates.TemplateResponse(
                request, "session_lobby.html", context, status_code=400
            )
        existing_seqs = list(
            db.scalars(select(Batch.seq).where(Batch.session_id == session.id)).all()
        )
        batch = Batch(
            session_id=session.id,
            seq=next_seq(existing_seqs),
            track_label=track,
            status="open",
        )
        db.add(batch)
        db.flush()
        for sort_order, item_id in enumerate(chosen):
            db.add(
                BatchItem(
                    batch_id=batch.id,
                    item_id=item_id,
                    ad_hoc_label=None,
                    sort_order=sort_order,
                )
            )

    session.status = target_status
    session.last_activity_at = func.now()
    db.commit()
    return RedirectResponse(f"/s/{session.code}", status_code=303)


@router.post("/s/{code}/vote")
def vote(
    request: Request,
    code: str,
    db: Annotated[Session, Depends(get_db)],
    batch_item_id: Annotated[int, Form()],
    choice: Annotated[str, Form()],
):
    """Record one participant's private yes/no vote on one open-batch option
    (§5.4/§5.5). The voter is the signed session cookie's participant row — no
    account required; a non-participant (or a participant of a DIFFERENT
    session) is 403. The option must belong to the session's OPEN batch — a
    foreign/closed/nonexistent option is 404. Idempotent: the first recorded
    vote stands; a re-submit or double-tap leaves it unchanged and adds no row.
    Only the aggregate ever surfaces — individual votes are never exposed."""
    session = _get_session_by_code(db, code)
    if session is None:
        raise HTTPException(404, "Session not found")
    _expire_if_stale(db, session)  # lazy §5.5 expiry before any mutation
    if session.status in ENDED_STATUSES:
        raise HTTPException(400, "This session is over — no more votes.")
    participant = _viewer_participant(request, db, session)
    if participant is None:
        raise HTTPException(403, "Join the session to vote")
    open_batch = _open_batch(db, session)
    if open_batch is None:
        raise HTTPException(404, "This session has no open batch")
    batch_item = db.get(BatchItem, batch_item_id)
    if batch_item is None or batch_item.batch_id != open_batch.id:
        raise HTTPException(404, "That option isn't in the open batch")
    if choice not in ("yes", "no"):
        raise HTTPException(400, "Choice must be 'yes' or 'no'")
    existing = db.scalar(
        select(BatchResponse).where(
            (BatchResponse.batch_item_id == batch_item.id)
            & (BatchResponse.session_participant_id == participant.id)
        )
    )
    if existing is None:
        db.add(
            BatchResponse(
                batch_item_id=batch_item.id,
                session_participant_id=participant.id,
                choice=choice,
            )
        )
        # Auto-close (§5.5/§5.6): once every roster member has answered every
        # option, close the batch in THIS transaction — the redirect then
        # lands on the results screen. autoflush is off, so the new response
        # must be flushed before the finished-count query can see it.
        db.flush()
        finished, roster = _voting_progress_counts(db, session)
        if roster > 0 and finished >= roster:
            _close_batch(db, session, open_batch, manual=False)
    session.last_activity_at = func.now()
    db.commit()
    return RedirectResponse(f"/s/{session.code}", status_code=303)


# --- Batch close + results (M3d) ---------------------------------------------


@router.post("/s/{code}/close")
def close_batch(
    request: Request, code: str, db: Annotated[Session, Depends(get_db)]
):
    """Host-only MANUAL batch close (§5.5/§5.6, D5): roll up the open batch's
    outcomes with missing votes counted as 'no', DELETE the per-person vote
    rows, and redirect to the results screen. Idempotent: a second POST finds
    no open batch → 404 — the first close already applied exactly once."""
    session = _get_session_by_code(db, code)
    if session is None:
        raise HTTPException(404, "Session not found")
    _expire_if_stale(db, session)  # lazy §5.5 expiry before any mutation
    account = require_account(request, db)
    if session.host_account_id != account.id:
        raise HTTPException(403, "Only the host can close the batch")
    if session.status in ENDED_STATUSES:
        raise HTTPException(400, "This session is over.")
    batch = _open_batch(db, session)
    if batch is None:
        raise HTTPException(404, "No open batch to close")
    _close_batch(db, session, batch, manual=True)
    db.commit()
    return RedirectResponse(f"/s/{session.code}", status_code=303)


def _decide_pending_item(
    db: Session, session: VotingSession, bid: int, biid: int, *, keep: bool
) -> None:
    """Set a pending (majority) batch_item's outcome: KEPT_HOST on host keep
    (incrementing the Item's keep counters once), NOT_KEPT on pass. The
    batch_item must belong to batch ``bid`` of THIS session, the batch must be
    'closed', and the outcome must still be NULL — a decided item can't be
    re-decided (400); foreign or nonexistent ids are 404 (no existence oracle,
    CLAUDE.md #6)."""
    batch = db.get(Batch, bid)
    if batch is None or batch.session_id != session.id:
        raise HTTPException(404, "Batch not found")
    batch_item = db.get(BatchItem, biid)
    if batch_item is None or batch_item.batch_id != batch.id:
        raise HTTPException(404, "Item not found")
    if batch.status != "closed":
        raise HTTPException(400, "Batch isn't closed yet")
    if batch_item.outcome is not None:
        raise HTTPException(400, "Already decided")
    if keep:
        batch_item.outcome = Outcome.KEPT_HOST.value
        if batch_item.item_id is not None:
            item = db.get(Item, batch_item.item_id)
            if item is not None:
                item.times_kept += 1
                item.last_kept_at = func.now()
    else:
        batch_item.outcome = Outcome.NOT_KEPT.value
    session.last_activity_at = func.now()


@router.post("/s/{code}/batch/{bid}/items/{biid}/keep")
def keep_batch_item(
    request: Request,
    code: str,
    bid: int,
    biid: int,
    db: Annotated[Session, Depends(get_db)],
):
    """Host-only accept of a pending majority item (M3d): KEPT_HOST, keep
    counters incremented once. The outcome-was-NULL guard makes a re-submit a
    400, never a double increment."""
    session = _get_session_by_code(db, code)
    if session is None:
        raise HTTPException(404, "Session not found")
    _expire_if_stale(db, session)  # lazy §5.5 expiry before any mutation
    account = require_account(request, db)
    if session.host_account_id != account.id:
        raise HTTPException(403, "Only the host can decide")
    if session.status in ENDED_STATUSES:
        raise HTTPException(400, "This session is over.")
    _decide_pending_item(db, session, bid, biid, keep=True)
    db.commit()
    return RedirectResponse(f"/s/{session.code}", status_code=303)


@router.post("/s/{code}/batch/{bid}/items/{biid}/pass")
def pass_batch_item(
    request: Request,
    code: str,
    bid: int,
    biid: int,
    db: Annotated[Session, Depends(get_db)],
):
    """Host-only pass on a pending majority item (M3d): NOT_KEPT, no keep
    counter change."""
    session = _get_session_by_code(db, code)
    if session is None:
        raise HTTPException(404, "Session not found")
    _expire_if_stale(db, session)  # lazy §5.5 expiry before any mutation
    account = require_account(request, db)
    if session.host_account_id != account.id:
        raise HTTPException(403, "Only the host can decide")
    if session.status in ENDED_STATUSES:
        raise HTTPException(400, "This session is over.")
    _decide_pending_item(db, session, bid, biid, keep=False)
    db.commit()
    return RedirectResponse(f"/s/{session.code}", status_code=303)


# --- Session progression + teardown (M3e) ------------------------------------


@router.post("/s/{code}/next-batch")
def next_batch(
    request: Request, code: str, db: Annotated[Session, Depends(get_db)]
):
    """Host-only 'start the next batch' (M3e). Preconditions: the session is
    'voting', no batch is open, and no closed batch still has outcome-NULL
    (majority-pending) items — otherwise 400 'Finish reviewing the current
    batch first.' The next batch goes to the first track in order with
    remaining target > 0 whose pool still has items never offered in ANY
    previous batch; every remaining track exhausted → 400 (the host finishes
    with fewer than target — unanimous keeps are always kept)."""
    session = _get_session_by_code(db, code)
    if session is None:
        raise HTTPException(404, "Session not found")
    _expire_if_stale(db, session)  # lazy §5.5 expiry before any mutation
    account = require_account(request, db)
    if session.host_account_id != account.id:
        raise HTTPException(403, "Only the host can start the next batch")
    if session.status in ENDED_STATUSES:
        raise HTTPException(400, "This session is over.")
    if session.status != "voting":
        raise HTTPException(400, "Session hasn't started voting yet.")
    if _open_batch(db, session) is not None:
        raise HTTPException(400, "Finish reviewing the current batch first.")
    pending = (
        db.scalar(
            select(func.count())
            .select_from(BatchItem)
            .join(Batch, Batch.id == BatchItem.batch_id)
            .where((Batch.session_id == session.id) & BatchItem.outcome.is_(None))
        )
        or 0
    )
    if pending > 0:
        raise HTTPException(400, "Finish reviewing the current batch first.")
    track, chosen = _next_batch_assembly(db, session)
    if track is None:
        if _all_targets_met(db, session):
            raise HTTPException(400, "All targets met — finish the session.")
        raise HTTPException(400, "No more options to vote on — finish the session.")
    existing_seqs = list(
        db.scalars(select(Batch.seq).where(Batch.session_id == session.id)).all()
    )
    batch = Batch(
        session_id=session.id,
        seq=next_seq(existing_seqs),
        track_label=track,
        status="open",
    )
    db.add(batch)
    db.flush()
    for sort_order, item_id in enumerate(chosen):
        db.add(
            BatchItem(
                batch_id=batch.id,
                item_id=item_id,
                ad_hoc_label=None,
                sort_order=sort_order,
            )
        )
    session.last_activity_at = func.now()
    db.commit()
    return RedirectResponse(f"/s/{session.code}", status_code=303)


@router.post("/s/{code}/finish")
def finish_session(
    request: Request, code: str, db: Annotated[Session, Depends(get_db)]
):
    """Host-only 'finish the session' (M3e): ends voting/lobby, deletes every
    participant row (§5.5 rule 2 — display names and account links do not
    outlive the session), and stamps finished_at. An OPEN batch is closed
    first (manual close: missing = 'no', D5) so no batch_response rows survive
    to block participant deletion. Idempotent: a second finish on an already
    'complete' session is a 303 no-op; an 'expired' session refuses (400)."""
    session = _get_session_by_code(db, code)
    if session is None:
        raise HTTPException(404, "Session not found")
    _expire_if_stale(db, session)  # lazy §5.5 expiry before any mutation
    account = require_account(request, db)
    if session.host_account_id != account.id:
        raise HTTPException(403, "Only the host can finish the session")
    if session.status == "expired":
        raise HTTPException(400, "This session is over.")
    if session.status == "complete":
        return RedirectResponse(f"/s/{session.code}", status_code=303)  # idempotent
    if session.status not in ("voting", "lobby"):
        raise HTTPException(400, "Session can't be finished from its current state")
    open_batch = _open_batch(db, session)
    if open_batch is not None:
        _close_batch(db, session, open_batch, manual=True)
    if session.status == "lobby":
        # Ending before voting starts is a host decision this slice allows;
        # the base state machine only exposes lobby → voting/expired, so
        # apply_transition('lobby', 'complete') would raise.
        session.status = "complete"
    else:
        session.status = apply_transition(session.status, "complete")
    db.execute(delete(SessionParticipant).where(SessionParticipant.session_id == session.id))
    session.finished_at = func.now()
    db.commit()
    return RedirectResponse(f"/s/{session.code}", status_code=303)


@router.get("/s/{code}/voting-status")
def voting_status_partial(
    request: Request, code: str, db: Annotated[Session, Depends(get_db)]
):
    """htmx poll target for the done/host views: ONLY the _voting_status.html
    partial ("{finished}/{roster} finished."). Public, like the roster poll."""
    session = _get_session_by_code(db, code)
    if session is None:
        raise HTTPException(404, "Session not found")
    _expire_if_stale(db, session)  # lazy §5.5 expiry on load
    if session.status in ENDED_STATUSES:
        return templates.TemplateResponse(
            request, "_session_ended_note.html", {"session": session}
        )
    finished, roster = _voting_progress_counts(db, session)
    return templates.TemplateResponse(
        request, "_voting_status.html", {"finished": finished, "roster": roster}
    )


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
    _expire_if_stale(db, session)  # lazy §5.5 expiry before any mutation
    account = require_account(request, db)
    if session.host_account_id != account.id:
        raise HTTPException(403, "Only the host can remove participants")
    if session.status in ENDED_STATUSES:
        raise HTTPException(400, "This session is over.")
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
