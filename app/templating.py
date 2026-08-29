"""Shared Jinja2 templates instance with an auth context processor (M2c).

Every route module renders through this single ``templates`` object so the
signed-in account is available to every template — base.html needs it for the
account indicator and the sign-out control. The context processor reads the
signed session cookie only (no DB hit): login/signup store ``account_name``
alongside ``account_id``, and display names are not editable anywhere, so the
session copy cannot go stale. If that ever changes, revisit this shortcut.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "static"


def short_date_label(value: datetime) -> str:
    """'%b %-d'-style label ('Aug 8'), built portably from '%b %d'.

    strftime's '%-d' is platform-specific (GNU vs BSD), so strip the leading
    zero from the day ourselves.
    """
    month, day = value.strftime("%b %d").split()
    return f"{month} {day.lstrip('0')}"



def _static_version(name: str) -> str:
    """A short content hash for a static file, for cache-busting its URL.

    Static assets sit behind a CDN (Cloudflare) with a long TTL, so a bare
    /static/app.css keeps serving the stale file for hours after a deploy. A
    ?v=<content-hash> query param makes each change a fresh URL — the CDN
    caches each version immutably, and a new version is fetched immediately.
    """
    try:
        return hashlib.sha256((STATIC_DIR / name).read_bytes()).hexdigest()[:10]
    except OSError:
        return "0"


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

# Content-hashed versions for cache-busted static URLs (computed once at import).
templates.env.globals["static_v"] = {
    "app.css": _static_version("app.css"),
    "htmx.min.js": _static_version("htmx.min.js"),
}
