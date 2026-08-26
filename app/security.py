"""Security middleware (D16): session cookies + origin/CSRF check."""

from __future__ import annotations

from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from app.settings import settings

_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def setup_middleware(app: FastAPI) -> None:
    """Install the session cookie middleware and the origin-check middleware."""
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        https_only=settings.https_only,
        same_site="lax",
        max_age=60 * 60 * 24 * 30,
    )

    @app.middleware("http")
    async def origin_check(request: Request, call_next):
        """Reject state-changing requests whose Origin doesn't match the Host.

        Absent Origin (curl, same-site tests, non-browser clients) is allowed;
        a present-but-mismatched Origin is rejected with 403 (CSRF defense).
        """
        if request.method in _MUTATING_METHODS:
            origin = request.headers.get("origin")
            if origin is None:
                return await call_next(request)  # non-browser clients; browsers send Origin on state-changing requests
            parsed = urlparse(origin)
            scheme_ok = parsed.scheme in ("http", "https")
            host = request.headers.get("host", "")
            if not scheme_ok or not parsed.netloc or parsed.netloc != host:
                return JSONResponse({"detail": "CSRF origin mismatch"}, status_code=403)
        return await call_next(request)
