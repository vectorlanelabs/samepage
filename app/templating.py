"""Shared Jinja2 templates instance with an auth context processor (M2c).

Every route module renders through this single ``templates`` object so the
signed-in account is available to every template — base.html needs it for the
account indicator and the sign-out control. The context processor reads the
signed session cookie only (no DB hit): login/signup store ``account_name``
alongside ``account_id``, and display names are not editable anywhere, so the
session copy cannot go stale. If that ever changes, revisit this shortcut.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def _current_account(request: Request) -> dict:
    """Context processor: expose the signed-in identity (or None) to templates."""
    account_id = request.session.get("account_id")
    if account_id is None:
        return {"current_account": None}
    name = request.session.get("account_name") or "Signed in"
    return {"current_account": {"display_name": name}}


templates = Jinja2Templates(
    directory=TEMPLATES_DIR,
    context_processors=[_current_account],
)
