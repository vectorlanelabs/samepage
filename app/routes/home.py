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
from app.models import Collection, Group, GroupAdmin
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

    # The dashboard is a generic surface — it counts collections (of any kind),
    # not meals. Meal-specific framing lives inside a Meal Planner collection,
    # not here, so an account with no collections isn't shown a "meal library".
    collection_count = (
        db.scalar(
            select(func.count())
            .select_from(Collection)
            .where(Collection.group_id.in_(own_group_ids))
        )
        or 0
    )
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "account": account,
            "collection_count": collection_count,
            "active_group_count": len(own_group_ids),
        },
    )
