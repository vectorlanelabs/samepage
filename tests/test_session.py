"""Session cookie flags (D16): HttpOnly always; Secure only in production.

Starlette only emits ``Set-Cookie`` when a request actually writes to the
session. The real app's login/signup routes do that, but asserting cookie
flags through them would couple these tests to the auth flow; instead they
exercise the exact production middleware config from
``app.security.setup_middleware`` on a minimal probe app that writes a
session cookie directly.
"""

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.security import setup_middleware


def _probe_client() -> TestClient:
    probe = FastAPI()
    setup_middleware(probe)

    @probe.get("/write")
    def write(request: Request):
        request.session["probe"] = "1"
        return {"ok": True}

    return TestClient(probe)


def test_session_cookie_has_http_only_and_name():
    with _probe_client() as client:
        resp = client.get("/write")
    set_cookie = resp.headers.get("set-cookie")
    assert set_cookie is not None
    assert "session=" in set_cookie
    # Starlette 1.x emits the flag lowercase; cookie attributes are
    # case-insensitive (RFC 6265), so compare case-insensitively.
    assert "httponly" in set_cookie.lower()


def test_session_cookie_not_secure_in_dev():
    with _probe_client() as client:
        resp = client.get("/write")
    set_cookie = resp.headers.get("set-cookie")
    assert set_cookie is not None
    assert "Secure" not in set_cookie
