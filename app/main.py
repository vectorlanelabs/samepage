"""FastAPI application entry point (T0.4).

The app runs ``alembic upgrade head`` on startup (lifespan) so a fresh
install boots to a working schema instead of 500ing on every page. Migration
errors propagate — a server that refuses to start is better than one that
boots and fails on every request.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlencode

from alembic.config import Config
from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from alembic import command
from app.routes import api, auth, collections, groups, home, library, pages, reports, sessions
from app.security import setup_middleware
from app.settings import REPO_ROOT, settings
from app.templating import templates

logger = logging.getLogger("samepage")


def _run_migrations(db_path: str | None = None) -> None:
    """Run ``alembic upgrade head`` against the configured DB.

    When ``db_path`` is given, ``SP_DB_PATH`` is pointed at it for the
    duration of the upgrade (restored afterwards). Exceptions are NOT caught:
    a boot-time migration failure must fail fast. After a successful upgrade
    the migrated DB file is tightened to 0o600 (the file holds private
    household data; a chmod failure is logged, not fatal).
    """
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    if db_path is None:
        command.upgrade(cfg, "head")
        target = settings.db_path
    else:
        previous = os.environ.get("SP_DB_PATH")
        os.environ["SP_DB_PATH"] = db_path
        try:
            command.upgrade(cfg, "head")
        finally:
            if previous is None:
                os.environ.pop("SP_DB_PATH", None)
            else:
                os.environ["SP_DB_PATH"] = previous
        target = db_path
    try:
        os.chmod(target, 0o600)
    except OSError as exc:
        logger.warning("could not chmod migrated DB %s to 0o600: %s", target, exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _run_migrations()
    yield


app = FastAPI(title="Same Page", lifespan=lifespan)

setup_middleware(app)

app.mount("/static", StaticFiles(directory=Path(__file__).resolve().parent / "static"), name="static")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/sw.js", include_in_schema=False)
def service_worker() -> FileResponse:
    """Serve the PWA service worker from the root so its scope is the whole
    app (a worker under /static/ would only control /static/)."""
    return FileResponse(
        Path(__file__).resolve().parent / "static" / "sw.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache"},
    )


@app.exception_handler(StarletteHTTPException)
async def _handle_http_exceptions(request: Request, exc: StarletteHTTPException):
    """Browser-friendly bodies for errors a page load can hit. A 429 (the
    join-by-code rate limiter, M5b) renders the friendly rate-limit page; a
    401 redirects to /login. API-style requests (no ``text/html`` in Accept)
    keep the default JSON body — relevant once M6's token-authenticated
    routes exist."""
    if exc.status_code == 429 and "text/html" in request.headers.get("accept", ""):
        return templates.TemplateResponse(request, "rate_limited.html", {}, status_code=429)
    if exc.status_code == 401 and "text/html" in request.headers.get("accept", ""):
        target = request.url.path + (f"?{request.url.query}" if request.url.query else "")
        return RedirectResponse(f"/login?{urlencode({'next': target})}", status_code=303)
    return await http_exception_handler(request, exc)


app.include_router(home.router)
app.include_router(auth.router)
app.include_router(groups.router)
app.include_router(collections.router)
app.include_router(library.router)
app.include_router(reports.router)
app.include_router(sessions.router)
app.include_router(api.router)
app.include_router(pages.router)
