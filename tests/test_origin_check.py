"""Origin-check middleware (D16): state-changing requests without a
same-origin Origin header are rejected with 403 (fail-closed). Absent Origin
is 403 too (``CSRF origin required``), except on the token-authenticated
``/api/`` surfaces and the exact ``/mcp``/``/mcp/...`` boundary (M6), where
Origin is CSRF-irrelevant.

The probe app carries a REAL mutating POST route, so an allowed request must
actually reach the handler (and a rejected one must not).
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.security import setup_middleware


@pytest.fixture()
def probe():
    """Fresh probe app with a real mutating POST /probe route."""
    mutations: list[str] = []
    app = FastAPI()
    setup_middleware(app)

    @app.post("/probe")
    def probe_route():
        mutations.append("mutated")
        return {"ok": True}

    # GET-only /api/v1 and /mcp paths: an absent-Origin POST must pass the
    # middleware (exemption) and die in routing with 405 — not 403.
    @app.get("/api/v1/probe")
    def api_probe_route():
        return {"ok": True}

    @app.get("/mcp")
    def mcp_route():
        return {"ok": True}

    # A real mutating POST route OUTSIDE the /mcp boundary: /mcpfoo shares
    # the /mcp prefix but must NOT be exempt — absent Origin must 403 before
    # this handler ever runs.
    @app.post("/mcpfoo")
    def mcpfoo_route():
        mutations.append("mcpfoo-mutated")
        return {"ok": True}

    with TestClient(app) as client:
        yield client, mutations


def test_matching_origin_allowed_and_mutation_recorded(probe):
    client, mutations = probe
    resp = client.post("/probe", headers={"Origin": "http://testserver"})
    assert resp.status_code == 200
    assert mutations == ["mutated"]


def test_evil_origin_rejected_and_mutation_not_recorded(probe):
    client, mutations = probe
    resp = client.post("/probe", headers={"Origin": "https://evil.example"})
    assert resp.status_code == 403
    assert resp.json() == {"detail": "CSRF origin mismatch"}
    assert mutations == []


def test_null_origin_rejected(probe):
    client, mutations = probe
    resp = client.post("/probe", headers={"Origin": "null"})
    assert resp.status_code == 403
    assert mutations == []


def test_non_http_scheme_origin_rejected(probe):
    client, mutations = probe
    resp = client.post("/probe", headers={"Origin": "ftp://testserver"})
    assert resp.status_code == 403
    assert mutations == []


def test_malformed_origin_rejected(probe):
    client, mutations = probe
    resp = client.post("/probe", headers={"Origin": "not-a-url"})
    assert resp.status_code == 403
    assert mutations == []


def test_absent_origin_rejected(probe):
    client, mutations = probe
    resp = client.post("/probe")
    assert resp.status_code == 403
    assert resp.json() == {"detail": "CSRF origin required"}
    assert mutations == []


def test_api_path_exempt_from_origin_requirement(probe):
    client, mutations = probe
    # Absent Origin on /api/... passes the middleware; routing rejects the
    # method (405), proving the exemption rather than a CSRF rejection.
    resp = client.post("/api/v1/probe")
    assert resp.status_code == 405
    assert mutations == []


def test_mcp_path_exempt_from_origin_requirement(probe):
    client, mutations = probe
    # Absent Origin on /mcp... passes the middleware too (Bearer-token auth,
    # CSRF-irrelevant); routing rejects the method (405).
    resp = client.post("/mcp")
    assert resp.status_code == 405
    assert mutations == []


def test_mcp_exact_boundary_not_prefix(probe):
    client, mutations = probe
    # /mcpfoo is NOT /mcp or /mcp/... — absent Origin must be rejected (403),
    # and the real POST handler must not run.
    resp = client.post("/mcpfoo")
    assert resp.status_code == 403
    assert resp.json() == {"detail": "CSRF origin required"}
    assert mutations == []


def test_mcp_subpath_exempt_from_origin_requirement(probe):
    client, mutations = probe
    # /mcp/... IS inside the boundary: absent Origin passes the middleware
    # (404 here — no such route — not the CSRF 403).
    resp = client.post("/mcp/tools/list")
    assert resp.status_code != 403
    assert mutations == []


def test_api_any_subpath_exempt_from_origin_requirement(probe):
    client, mutations = probe
    # Any path under /api/ is exempt: absent Origin is not 403 (404 — the
    # route doesn't exist, but the middleware passed it through).
    resp = client.post("/api/v1/anything")
    assert resp.status_code != 403
    assert mutations == []


def test_api_path_with_evil_origin_still_rejected(probe):
    client, mutations = probe
    # The /api exemption covers ABSENT Origin only — a present-but-mismatched
    # Origin is still rejected (the middleware never trusts an evil Origin).
    resp = client.post("/api/v1/probe", headers={"Origin": "https://evil.example"})
    assert resp.status_code == 403
    assert resp.json() == {"detail": "CSRF origin mismatch"}
    assert mutations == []


def test_login_rejects_cross_site_origin(client):
    resp = client.post(
        "/login",
        data={"name": "Ada", "pin": "1234"},
        headers={"Origin": "https://evil.example"},
    )
    assert resp.status_code == 403
    assert resp.json() == {"detail": "CSRF origin mismatch"}


def test_login_rejects_absent_origin(client):
    resp = client.post("/login", data={"name": "Ada", "pin": "1234"})
    assert resp.status_code == 403
    assert resp.json() == {"detail": "CSRF origin required"}
