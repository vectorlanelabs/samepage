"""Origin-check middleware (D16): state-changing requests with a bad Origin
header are rejected with 403 (fail-closed). Absent Origin is allowed —
documented for non-browser clients like curl and tests.

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


def test_absent_origin_allowed_and_mutation_recorded(probe):
    client, mutations = probe
    resp = client.post("/probe")
    assert resp.status_code == 200
    assert mutations == ["mutated"]
