"""Home screen route: the guest landing.

"/" is the front door for signed-out visitors — the value prop and the
join-by-code entry point. A signed-in visitor is redirected to the collections
hub (303): the hub is the composed post-login home, and this page never shows
real data to anyone. Earlier versions rendered signed-in stat cards here and
(earlier still) queried global counts across every group on the deployment —
an information leak on a multi-tenant platform; the redirect closes both.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth import get_current_account
from app.db import get_db
from app.templating import templates

router = APIRouter()


@router.get("/")
def home(request: Request, db: Annotated[Session, Depends(get_db)]):
    account = get_current_account(request, db)
    if account is not None:
        return RedirectResponse("/collections", status_code=303)
    return templates.TemplateResponse(request, "home.html", {"account": None})
