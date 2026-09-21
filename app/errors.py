"""Browser-facing error rendering: a person never sees a bare JSON error body.

Shared by the app-level exception handlers (main.py) and the origin-check
middleware (security.py)."""

from __future__ import annotations

import logging

from fastapi import Request
from fastapi.responses import HTMLResponse

from app.templating import templates

logger = logging.getLogger("samepage")

_ERROR_HEADINGS = {
    400: "That didn't work.",
    403: "That's not yours to do.",
    404: "We couldn't find that.",
    405: "That didn't work.",
    422: "Something was missing.",
    503: "Not available right now.",
}


def wants_html(request: Request) -> bool:
    """A browser navigation or form post (Accept carries text/html). The JSON
    API, the MCP mount, and htmx/fetch-style requests keep machine bodies."""
    if request.url.path.startswith(("/api/", "/mcp")):
        return False
    return "text/html" in request.headers.get("accept", "")


def error_page(request: Request, status_code: int, message: str | None):
    """A branded error page with a way back — never a bare JSON body in a
    browser. Inside a session (/s/CODE/...) the way back is the session page,
    which always routes to whatever screen is current."""
    heading = _ERROR_HEADINGS.get(
        status_code, "Something went wrong." if status_code >= 500 else "That didn't work."
    )
    if not message or status_code >= 500:
        message = "It's us, not you. Try again in a moment."
    parts = request.url.path.strip("/").split("/")
    in_session = len(parts) > 2 and parts[0] == "s"
    context = {
        "heading": heading,
        "message": message,
        "back_href": f"/s/{parts[1]}" if in_session else None,
        "back_label": "Back to the session",
    }
    if in_session:
        context["chrome"] = "session"
    try:
        return templates.TemplateResponse(request, "error.html", context, status_code=status_code)
    except Exception:  # the error page must never itself become a raw 500
        logger.exception("error page failed to render")
        return HTMLResponse(
            f"<h1>{heading}</h1><p><a href=\"/\">Go home</a></p>", status_code=status_code
        )
