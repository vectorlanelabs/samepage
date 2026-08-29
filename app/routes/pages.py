"""Static content pages (privacy, terms) — public, no auth.

Google's OAuth consent screen links to /privacy, so it must render for signed-out
visitors and crawlers.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.templating import templates

router = APIRouter()


@router.get("/privacy")
def privacy(request: Request):
    return templates.TemplateResponse(request, "privacy.html", {})


@router.get("/terms")
def terms(request: Request):
    return templates.TemplateResponse(request, "terms.html", {})
