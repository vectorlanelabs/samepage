"""Collections hub + create-collection routes (M2c/M2e): the index of every
collection belonging to groups the signed-in account owns or admins, and the
flow a blank production DB needs to create a collection in the first place.

This is the post-login hub for collection-scoped routing (plan §9) — the
library now lives at /collections/{id}, so an account in two groups can
actually reach both groups' libraries (the multi-group dead end this slice
closes). Requires a signed-in account; a signed-out visitor gets the standard
401 → /login redirect, and no account ever sees another group's collections.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import require_account, require_group_admin
from app.db import get_db
from app.models import Account, Collection, Group, GroupAdmin, Item
from app.templating import templates

router = APIRouter()


def _owned_groups(db: Session, account: Account) -> list[dict]:
    """Groups the account owns or admins, as picker rows (id + name).

    Same ownership query pattern as the hub below: one query, owner-or-admin
    via the outerjoin, ordered by name then id so same-named groups stay
    distinct (ordering keyed on group id, not the display name).
    """
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
    return [{"id": group_id, "name": group_name} for group_id, group_name in rows]


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


@router.get("/collections/new")
def new_collection_page(request: Request, db: Annotated[Session, Depends(get_db)]):
    """New-collection page (M2e): requires sign-in; renders a card with a Name
    field, a group picker (groups the account owns/admins — the form can only
    ever create into a group the account already manages), kind fixed to
    "meal" (hidden input; the visible text says so — other kinds arrive
    later). An account with no groups gets no form, just "Create a group
    first." linking to /groups."""
    account = require_account(request, db)
    return templates.TemplateResponse(
        request,
        "collection_new.html",
        {"groups": _owned_groups(db, account), "name": "", "error": None},
    )


@router.post("/collections")
def create_collection(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    name: Annotated[str, Form()] = "",
    group_id: Annotated[int, Form()] = -1,
):
    """Create a collection in one of the account's own groups (M2e).

    ``name`` is required (stripped; blank → 400 re-render with the error and
    the group picker still populated). ``group_id`` is validated with the
    same semantics as ``require_group_admin``: a group that doesn't exist OR
    isn't owned/admined by the account is 404 — never 403 — so the status
    code alone can't be used to enumerate which group ids exist on the
    deployment (no-existence-oracle rule). Kind is fixed to "meal" server-side
    (the hidden form field is presentational for now). 303 to the new
    collection's library page.
    """
    account = require_account(request, db)
    name = name.strip()
    groups = _owned_groups(db, account)
    if not name:
        return templates.TemplateResponse(
            request,
            "collection_new.html",
            {
                "groups": [
                    {"id": g["id"], "name": g["name"], "selected": g["id"] == group_id}
                    for g in groups
                ],
                "name": name,
                "error": "Name is required.",
            },
            status_code=400,
        )

    # 404 for a group that doesn't exist or isn't the account's to manage.
    require_group_admin(request, db, group_id)

    collection = Collection(group_id=group_id, kind="meal", name=name)
    db.add(collection)
    db.commit()
    return RedirectResponse(f"/collections/{collection.id}", status_code=303)
