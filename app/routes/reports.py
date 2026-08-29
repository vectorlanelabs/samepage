"""Per-collection reporting & discovery (M4, plan §6): a read-only report
of which items and tags succeed or get rejected, plus a "not offered
lately" discovery list for the host.

Tenant scoping is the load-bearing requirement here (plan §6, §6.1): the
route runs ``_get_owned_collection_or_404`` FIRST — the single choke point
that 404s for a collection that doesn't exist or isn't the signed-in
account's group — and every query below starts from the guarded
``collection.id``. There is deliberately no query in this module that can
reach another group's items, tags, or outcomes, and nothing per-person or
per-session is ever rendered: the report is aggregate item/tag counters
only (``item.times_offered``/``times_kept``/``last_kept_at``), never raw
votes.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import require_account
from app.db import get_db
from app.models import Item, ItemTag, Tag
from app.routes.library import _get_owned_collection_or_404
from app.templating import templates

router = APIRouter()

NOT_OFFERED_LATELY_COUNT = 5


def _rate_row(name: str, offered: int, kept: int) -> dict:
    """One by-item / by-tag report row: aggregate counters plus the reject
    rate (float 0..1 and rounded percentage for display/bar width).

    Callers guarantee ``offered > 0`` (items filter on ``times_offered``;
    tags are dropped when their aggregate offered is 0).
    """
    rejected = offered - kept
    rate = rejected / offered
    return {
        "name": name,
        "offered": offered,
        "kept": kept,
        "rejected": rejected,
        "reject_rate": rate,
        "reject_rate_pct": round(rate * 100),
    }


@router.get("/collections/{collection_id}/report")
def collection_report(
    request: Request,
    collection_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """Per-collection report (signed-in accounts only, own collection):
    reject rates by item and by tag, plus the "not offered lately" list.

    Every query starts from the guarded collection: items by
    ``Item.collection_id == collection.id``, tags via the item → item_tag →
    tag join filtered on that same collection id (never a group-wide tag
    scan), and the neglected list from Item columns scoped to the
    collection's non-archived items.
    """
    account = require_account(request, db)
    collection = _get_owned_collection_or_404(db, account, collection_id)

    # By item: every offered item in THIS collection (archived items keep
    # their history — the spec only requires times_offered > 0), ordered by
    # reject rate descending, then name.
    item_rows = [
        {
            **_rate_row(item.name, item.times_offered, item.times_kept),
            "last_kept": (
                item.last_kept_at.strftime("%b %d, %Y") if item.last_kept_at else None
            ),
        }
        for item in db.scalars(
            select(Item).where(
                (Item.collection_id == collection.id) & (Item.times_offered > 0)
            )
        ).all()
    ]
    item_rows.sort(key=lambda r: (-r["reject_rate"], r["name"].casefold()))

    # By tag: aggregate THIS collection's items per tag. The join is
    # collection-scoped — Item.collection_id is the only filter, so a tag
    # shared with another collection only ever sums this one's items. Tags
    # with aggregate offered == 0 are dropped.
    tag_rows = [
        _rate_row(tag_name, offered, kept)
        for tag_name, offered, kept in db.execute(
            select(Tag.name, func.sum(Item.times_offered), func.sum(Item.times_kept))
            .select_from(Item)
            .join(ItemTag, ItemTag.item_id == Item.id)
            .join(Tag, Tag.id == ItemTag.tag_id)
            .where(Item.collection_id == collection.id)
            .group_by(Tag.id, Tag.name)
        ).all()
        if offered > 0
    ]
    tag_rows.sort(key=lambda r: (-r["reject_rate"], r["name"].casefold()))

    # "Not offered lately": the collection's non-archived items with the
    # LOWEST times_offered (ties broken by name), top 5 — a discovery
    # signal for the host, purely from Item columns.
    not_offered_rows = [
        {"name": item.name, "times_offered": item.times_offered}
        for item in db.scalars(
            select(Item)
            .where((Item.collection_id == collection.id) & (Item.archived_at.is_(None)))
            .order_by(Item.times_offered, Item.normalized_name)
            .limit(NOT_OFFERED_LATELY_COUNT)
        ).all()
    ]

    return templates.TemplateResponse(
        request,
        "report.html",
        {
            "collection": collection,
            "item_rows": item_rows,
            "tag_rows": tag_rows,
            "not_offered_rows": not_offered_rows,
        },
    )
