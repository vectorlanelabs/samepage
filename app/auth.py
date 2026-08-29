"""Identity & auth helpers (M2a): session account lookup + guards.

The signed session cookie stores only ``account_id``. Everything else is
derived from the database on every request.
"""

from __future__ import annotations

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, Group, GroupAdmin


def get_current_account(request: Request, db: Session) -> Account | None:
    """Return the signed-in Account, or None when absent."""
    account_id = request.session.get("account_id")
    if account_id is None:
        return None
    account = db.get(Account, account_id)
    return account


def require_account(request: Request, db: Session) -> Account:
    """Guard for sign-in-required routes: 401 unless signed in."""
    account = get_current_account(request, db)
    if account is None:
        raise HTTPException(401, "Sign in required")
    return account


def is_group_owner(account: Account, group: Group) -> bool:
    """Check if account owns the group."""
    return account.id == group.owner_account_id


def is_group_admin(account: Account, group: Group, db: Session) -> bool:
    """Check if account owns or admins the group."""
    if is_group_owner(account, group):
        return True
    return db.scalar(select(GroupAdmin).where(GroupAdmin.group_id == group.id, GroupAdmin.account_id == account.id)) is not None


def require_group_admin(request: Request, db: Session, group_id: int) -> tuple[Account, Group]:
    """Guard: 401 if not signed in; 404 if the group doesn't exist OR the
    signed-in account isn't an owner/admin of it — never 403 for that case,
    so the status code alone can't be used to enumerate which group ids exist
    on the deployment (matches the no-existence-oracle rule in library.py)."""
    account = require_account(request, db)
    group = db.get(Group, group_id)
    if group is None or not is_group_admin(account, group, db):
        raise HTTPException(404, "Group not found")
    return account, group


