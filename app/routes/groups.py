"""Group management routes (M2a): list, create, detail, add admin, remove admin."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import is_group_owner, require_account, require_group_admin
from app.db import get_db
from app.models import Account, Group, GroupAdmin
from app.templating import templates

router = APIRouter()


def _groups_context(db: Session, account: Account) -> dict:
    """Groups owned or admined by the account, as template rows."""
    # Get groups owned by this account.
    owned_groups = db.scalars(
        select(Group).where(Group.owner_account_id == account.id)
    ).all()
    # Get groups admined by this account.
    admin_groups = db.scalars(
        select(Group)
        .join(GroupAdmin, GroupAdmin.group_id == Group.id)
        .where(GroupAdmin.account_id == account.id)
    ).all()
    # Combine and dedupe.
    all_groups = list(dict.fromkeys(owned_groups + admin_groups))
    return {
        "groups": [
            {
                "id": g.id,
                "name": g.name,
                "is_owner": g.owner_account_id == account.id,
            }
            for g in all_groups
        ]
    }


def _group_detail_context(db: Session, group: Group, account: Account) -> dict:
    """Build context dict for group detail template with owner and admins list."""
    owner = db.get(Account, group.owner_account_id)
    admin_accounts = db.scalars(
        select(Account)
        .join(GroupAdmin, GroupAdmin.account_id == Account.id)
        .where(GroupAdmin.group_id == group.id)
    ).all()
    admins = [
        {
            "id": a.id,
            "email": a.email,
            "display_name": a.display_name,
            "is_self": a.id == account.id,
        }
        for a in admin_accounts
    ]
    return {
        "group": group,
        "owner": owner,
        "admins": admins,
        "is_owner": account.id == group.owner_account_id,
    }


@router.get("/groups")
def groups_page(request: Request, db: Annotated[Session, Depends(get_db)]):
    """List groups owned or admined by the current account."""
    account = require_account(request, db)
    return templates.TemplateResponse(
        request,
        "groups.html",
        _groups_context(db, account),
        status_code=200,
    )


@router.post("/groups")
def create_group(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    name: Annotated[str, Form()] = "",
):
    """Create a group owned by the current account."""
    account = require_account(request, db)
    name = name.strip()
    if not name:
        context = _groups_context(db, account)
        context["error"] = "Group name is required."
        return templates.TemplateResponse(
            request,
            "groups.html",
            context,
            status_code=400,
        )

    group = Group(name=name, owner_account_id=account.id)
    db.add(group)
    db.commit()
    return RedirectResponse(f"/groups/{group.id}", status_code=303)


@router.get("/groups/{group_id}")
def group_detail(
    request: Request, group_id: int, db: Annotated[Session, Depends(get_db)]
):
    """Group detail: name, owner, admin list."""
    account, group = require_group_admin(request, db, group_id)
    context = _group_detail_context(db, group, account)
    return templates.TemplateResponse(
        request,
        "group_detail.html",
        context,
        status_code=200,
    )


@router.post("/groups/{group_id}/admins")
def add_admin(
    request: Request,
    group_id: int,
    email: Annotated[str, Form()],
    db: Annotated[Session, Depends(get_db)],
):
    """Add an admin to a group (owner-only)."""
    account, group = require_group_admin(request, db, group_id)

    # Owner-only check.
    if not is_group_owner(account, group):
        raise HTTPException(403, "Owner required")

    email = email.strip().lower()
    target = db.scalar(select(Account).where(Account.email == email))

    if target is None:
        context = _group_detail_context(db, group, account)
        context["error"] = "No account with that email exists."
        return templates.TemplateResponse(
            request,
            "group_detail.html",
            context,
            status_code=400,
        )

    if target.id == group.owner_account_id:
        context = _group_detail_context(db, group, account)
        context["error"] = "That account is already the owner."
        return templates.TemplateResponse(
            request,
            "group_detail.html",
            context,
            status_code=400,
        )

    # Check if already admin.
    existing = db.scalar(
        select(GroupAdmin).where(
            (GroupAdmin.group_id == group.id) & (GroupAdmin.account_id == target.id)
        )
    )
    if existing is not None:
        context = _group_detail_context(db, group, account)
        context["error"] = "That account is already an admin."
        return templates.TemplateResponse(
            request,
            "group_detail.html",
            context,
            status_code=400,
        )

    # Add the admin.
    admin_row = GroupAdmin(group_id=group.id, account_id=target.id)
    db.add(admin_row)
    db.commit()

    return RedirectResponse(f"/groups/{group.id}", status_code=303)


@router.post("/groups/{group_id}/admins/{admin_account_id}/remove")
def remove_admin(
    request: Request,
    group_id: int,
    admin_account_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """Remove an admin from a group (owner-only, idempotent)."""
    account, group = require_group_admin(request, db, group_id)

    # Owner-only check.
    if not is_group_owner(account, group):
        raise HTTPException(403, "Owner required")

    # Delete the row if it exists (idempotent).
    admin_row = db.scalar(
        select(GroupAdmin).where(
            (GroupAdmin.group_id == group.id) & (GroupAdmin.account_id == admin_account_id)
        )
    )
    if admin_row is not None:
        db.delete(admin_row)
        db.commit()

    return RedirectResponse(f"/groups/{group.id}", status_code=303)
