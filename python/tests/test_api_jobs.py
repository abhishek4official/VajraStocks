"""API tests for the background jobs endpoints (V2.0 spec M1)."""

import pytest
from fastapi.testclient import TestClient

from stocks.api.deps import get_db
from stocks.api.main import app
from stocks.services.jobs.runner import JobRunner, register_handler

# A trivial handler so the test can drive a job to completion via the runner.
register_handler("noop")(lambda job, s, set_progress, is_cancelled: {"ok": True})


@pytest.fixture
def api_client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_enqueue_list_get(api_client):
    r = api_client.post("/api/v1/jobs", json={"kind": "noop", "params": {"x": 1}})
    assert r.status_code == 200
    jid = r.json()["id"]
    assert r.json()["status"] == "PENDING"

    assert any(j["id"] == jid for j in api_client.get("/api/v1/jobs").json())
    assert api_client.get(f"/api/v1/jobs/{jid}").json()["kind"] == "noop"


def test_cancel(api_client, db_session):
    jid = api_client.post("/api/v1/jobs", json={"kind": "noop"}).json()["id"]
    r = api_client.post(f"/api/v1/jobs/{jid}/cancel")
    assert r.status_code == 200
    assert r.json()["cancel_requested"] is True


def test_get_missing_404(api_client):
    assert api_client.get("/api/v1/jobs/99999").status_code == 404


def test_progress_reflected_after_run(api_client, db_session):
    # Enqueue via API, then run it through the runner (the worker would do this in prod).
    jid = api_client.post("/api/v1/jobs", json={"kind": "noop"}).json()["id"]
    JobRunner(db_session).run_next()
    body = api_client.get(f"/api/v1/jobs/{jid}").json()
    assert body["status"] == "SUCCESS"
    assert body["finished_at"] is not None
