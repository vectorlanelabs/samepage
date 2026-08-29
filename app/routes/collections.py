"""Collections hub route (M2c): the index of every collection belonging to
groups the signed-in account owns or admins.

This is the post-login hub for collection-scoped routing (plan §9) — the
library now lives at /collections/{id}, so an account in two groups can
actually reach both groups' libraries (the multi-group dead end this slice
closes). Requires a signed-in account; a signed-out visitor gets the standard
401 → /login redirect, and no account ever sees another group's collections.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import require_account
from app.db import get_db
from app.models import Collection, Group, GroupAdmin, Item
from app.templating import templates

router = APIRouter()


@router.get("/collections")
def collections_page(request: Request, db: Annotated[Session, Depends(get_db)]):
    """Hub: every collection of groups the account owns or admins, grouped by
    group (distinct groups with the same name stay separate — grouping is keyed
    on group id, not the display name), with per-collection active-item counts
    (archived items don't count)."""
    account = require_account(request, db)

    rows = db.execute(
        select(Collection.id, Collection.name, Group.id, Group.name, func.count(Item.id))
        .join(Group, Group.id == Collection.group_id)
        .outerjoin(
            GroupAdmin,
            (GroupAdmin.group_id == Group.id) & (GroupAdmin.account_id == account.id),
        )
        .outerjoin(
            Item,
            (Item.collection_id == Collection.id) & (Item.archived_at.is_(None)),
        )
        .where(
            (Group.owner_account_id == account.id) | (GroupAdmin.account_id == account.id)
        )
        .group_by(Collection.id, Collection.name, Group.id, Group.name)
        .order_by(Group.name, Group.id, Collection.name)
    ).all()

    groups: list[dict] = []
    for collection_id, collection_name, group_id, group_name, active_count in rows:
        if not groups or groups[-1]["id"] != group_id:
            groups.append({"id": group_id, "name": group_name, "collections": []})
        groups[-1]["collections"].append(
            {"id": collection_id, "name": collection_name, "active_count": active_count}
        )

    return templates.TemplateResponse(
        request,
        "collections.html",
        {"groups": groups},
    )
