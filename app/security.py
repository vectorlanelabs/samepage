"""Security middleware (D16): session cookies + origin/CSRF check.

Origin policy (fail-closed): every state-changing (mutating) request must
carry a present ``Origin`` header whose scheme is http(s) and whose netloc
matches the Host, or it is rejected with 403. Absent Origin is rejected too
(``CSRF origin required``) — non-browser clients like curl and scripts must
send an explicit same-origin Origin. The one exemption: the token-
authenticated surfaces (M6) — any path under ``/api/``, and exactly ``/mcp``
or ``/mcp/...`` — are authenticated by Bearer token, so Origin is
CSRF-irrelevant and absent Origins are allowed there.
"""

from __future__ import annotations

from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from app.settings import settings

_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# /api/ prefix (M6): Bearer auth makes Origin irrelevant. /mcp is matched
# with exact-boundary logic in origin_check (below), not via this tuple.
_ORIGIN_EXEMPT_PREFIXES = ("/api/",)


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
        """Reject state-changing requests without a same-origin Origin header.

        Fail-closed: absent Origin is 403 (``CSRF origin required``) except
        on token-authenticated paths — under ``/api/``, or exactly ``/mcp``
        or ``/mcp/...`` (Bearer-token auth, CSRF-irrelevant); present-but-
        mismatched / null / non-http(s) / malformed Origin is 403
        (``CSRF origin mismatch``).
        """
        if request.method in _MUTATING_METHODS:
            origin = request.headers.get("origin")
            if origin is None:
                path = request.url.path
                is_exempt = path.startswith(_ORIGIN_EXEMPT_PREFIXES) or (
                    path == "/mcp" or path.startswith("/mcp/")
                )
                if is_exempt:
                    return await call_next(request)  # token-authenticated (M6)
                return JSONResponse({"detail": "CSRF origin required"}, status_code=403)
            parsed = urlparse(origin)
            scheme_ok = parsed.scheme in ("http", "https")
            host = request.headers.get("host", "")
            if not scheme_ok or not parsed.netloc or parsed.netloc != host:
                return JSONResponse({"detail": "CSRF origin mismatch"}, status_code=403)
        return await call_next(request)
