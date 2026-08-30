"""Group management routes (M2a): list, create, detail, add admin, remove admin.
M6a adds the owner-only API-token management routes (generate/regenerate with a
one-time plaintext reveal, and revoke)."""

from __future__ import annotations

from typing import Annotated
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.auth import is_group_owner, require_account, require_group_admin
from app.db import get_db
from app.models import Account, ApiToken, Collection, Group, GroupAdmin
from app.templating import templates
from app.tokens import generate_token, hash_token

router = APIRouter()


def _public_base_url(request: Request) -> str:
    """The app's public origin (no trailing slash), for showing API/MCP URLs.
    Behind a TLS-terminating proxy the request scheme is http internally, so
    present https for any non-local host — that's the real public URL."""
    base = str(request.base_url).rstrip("/")
    parsed = urlparse(base)
    if parsed.scheme == "http" and (parsed.hostname or "") not in ("localhost", "127.0.0.1"):
        base = "https://" + base.split("://", 1)[1]
    return base


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
    # Count collections per group for the card meta line.
    group_ids = [g.id for g in all_groups]
    collection_counts: dict[int, int] = {}
    if group_ids:
        rows = db.execute(
            select(Collection.group_id, func.count(Collection.id))
            .where(Collection.group_id.in_(group_ids))
            .group_by(Collection.group_id)
        ).all()
        collection_counts = {gid: count for gid, count in rows}
    return {
        "groups": [
            {
                "id": g.id,
                "name": g.name,
                "is_owner": g.owner_account_id == account.id,
                "collection_count": collection_counts.get(g.id, 0),
            }
            for g in all_groups
        ]
    }


def _group_detail_context(
    db: Session, group: Group, account: Account, request: Request
) -> dict:
    """Build context dict for group detail template with owner and admins list,
    plus the group's API-token status (created/last-used, never the hash) and
    the public MCP/API endpoint URLs."""
    base_url = _public_base_url(request)
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
    api_token = db.scalar(select(ApiToken).where(ApiToken.group_id == group.id))
    return {
        "group": group,
        "owner": owner,
        "admins": admins,
        "is_owner": account.id == group.owner_account_id,
        "api_token": (
            {"created_at": api_token.created_at, "last_used_at": api_token.last_used_at}
            if api_token is not None
            else None
        ),
        "mcp_url": f"{base_url}/mcp",
        "api_url": f"{base_url}/api/v1",
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
    context = _group_detail_context(db, group, account, request)
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
        context = _group_detail_context(db, group, account, request)
        context["error"] = "No account with that email exists."
        return templates.TemplateResponse(
            request,
            "group_detail.html",
            context,
            status_code=400,
        )

    if target.id == group.owner_account_id:
        context = _group_detail_context(db, group, account, request)
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
        context = _group_detail_context(db, group, account, request)
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


@router.post("/groups/{group_id}/api-token")
def create_api_token(
    request: Request,
    group_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """Generate (or regenerate) the group's API token — owner-only (403 for
    admins/others; 404 for a foreign or nonexistent group, no existence
    oracle). Any existing token is replaced in the same transaction (a group
    has at most one live token — the DB enforces it with a UNIQUE constraint),
    and the PLAINTEXT is rendered once in the response; only its SHA-256 hash
    is ever stored."""
    account, group = require_group_admin(request, db, group_id)

    if not is_group_owner(account, group):
        raise HTTPException(403, "Owner required")

    token = generate_token()
    db.execute(delete(ApiToken).where(ApiToken.group_id == group.id))
    db.add(ApiToken(group_id=group.id, token_hash=hash_token(token)))
    db.commit()

    context = _group_detail_context(db, group, account, request)
    context["api_token_plaintext"] = token
    return templates.TemplateResponse(
        request,
        "group_detail.html",
        context,
        status_code=200,
    )


@router.post("/groups/{group_id}/api-token/revoke")
def revoke_api_token(
    request: Request,
    group_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """Revoke the group's API token — owner-only, idempotent: a revoke with no
    token present is a no-op redirect back to the group page."""
    account, group = require_group_admin(request, db, group_id)

    if not is_group_owner(account, group):
        raise HTTPException(403, "Owner required")

    db.execute(delete(ApiToken).where(ApiToken.group_id == group.id))
    db.commit()
    return RedirectResponse(f"/groups/{group.id}", status_code=303)
