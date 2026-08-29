"""Home screen route (T0.4): hero + library/groups stat cards.

The page itself is reachable without signing in (it's the front door — sign
in/sign up links live here), but it never shows real data to a signed-out
visitor, and never shows anything beyond the signed-in account's own groups.
Earlier versions queried global counts across every group on the deployment
and showed them to anyone — a real information leak on a multi-tenant
platform, fixed alongside the same class of bug in app/routes/library.py.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_account
from app.db import get_db
from app.models import Collection, Group, GroupAdmin, Item
from app.templating import templates

router = APIRouter()


@router.get("/")
def home(request: Request, db: Annotated[Session, Depends(get_db)]):
    account = get_current_account(request, db)
    if account is None:
        return templates.TemplateResponse(request, "home.html", {"account": None})

    own_group_ids = db.scalars(
        select(Group.id)
        .outerjoin(GroupAdmin, GroupAdmin.group_id == Group.id)
        .where((Group.owner_account_id == account.id) | (GroupAdmin.account_id == account.id))
        .distinct()
    ).all()

    active_item_count = (
        db.scalar(
            select(func.count())
            .select_from(Item)
            .join(Collection, Collection.id == Item.collection_id)
            .where(Collection.group_id.in_(own_group_ids), Item.archived_at.is_(None))
        )
        or 0
    )
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "account": account,
            "active_meal_count": active_item_count,
            "active_group_count": len(own_group_ids),
        },
    )
