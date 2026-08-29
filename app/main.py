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
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from alembic import command
from app.routes import auth, groups, home, library
from app.security import setup_middleware
from app.settings import REPO_ROOT, settings

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


@app.exception_handler(StarletteHTTPException)
async def _redirect_unauthenticated(request: Request, exc: StarletteHTTPException):
    """A 401 on a browser page load redirects to /login instead of a bare JSON
    error. API-style requests (no ``text/html`` in Accept) keep the default
    JSON body — relevant once M6's token-authenticated routes exist."""
    if exc.status_code == 401 and "text/html" in request.headers.get("accept", ""):
        target = request.url.path + (f"?{request.url.query}" if request.url.query else "")
        return RedirectResponse(f"/login?{urlencode({'next': target})}", status_code=303)
    return await http_exception_handler(request, exc)


app.include_router(home.router)
app.include_router(auth.router)
app.include_router(groups.router)
app.include_router(library.router)
