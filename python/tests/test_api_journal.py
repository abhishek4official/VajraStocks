"""API tests for the Trade Journal endpoints (V2.0 spec M3)."""

import pytest
from fastapi.testclient import TestClient

from stocks.api.deps import get_db
from stocks.api.main import app


@pytest.fixture
def api_client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_log_close_and_compute(api_client):
    # Log an open trade.
    r = api_client.post("/api/v1/journal/trades", json={
        "symbol": "RELIANCE", "setup": "pullback", "entry_date": "2026-01-05",
        "entry_price": 100.0, "qty": 10, "stop_price": 95.0, "target_price": 120.0,
    })
    assert r.status_code == 200
    t = r.json()
    assert t["symbol"] == "RELIANCE.NS" and t["status"] == "OPEN" and t["pnl"] is None
    tid = t["id"]

    # Close it at 110 -> pnl 100, R = (110-100)/(100-95) = 2.0
    r = api_client.post(f"/api/v1/journal/trades/{tid}/close", json={
        "exit_date": "2026-01-20", "exit_price": 110.0,
    })
    assert r.status_code == 200
    c = r.json()
    assert c["status"] == "CLOSED"
    assert c["pnl"] == pytest.approx(100.0)
    assert c["r_multiple"] == pytest.approx(2.0)


def test_list_and_review(api_client):
    api_client.post("/api/v1/journal/trades", json={
        "symbol": "A", "setup": "pullback", "entry_date": "2026-01-01", "entry_price": 100, "qty": 10,
        "stop_price": 95, "exit_date": "2026-01-05", "exit_price": 110,
    })
    api_client.post("/api/v1/journal/trades", json={
        "symbol": "B", "setup": "pullback", "entry_date": "2026-01-01", "entry_price": 100, "qty": 10,
        "stop_price": 95, "exit_date": "2026-01-05", "exit_price": 96,
    })
    assert len(api_client.get("/api/v1/journal/trades").json()) == 2

    review = api_client.get("/api/v1/journal/review").json()
    pb = next(s for s in review if s["setup"] == "pullback")
    assert pb["trades"] == 2
    assert pb["win_rate"] == pytest.approx(0.5)
    assert pb["avg_r"] == pytest.approx(0.6)


def test_close_missing_404(api_client):
    r = api_client.post("/api/v1/journal/trades/999/close", json={"exit_date": "2026-01-01", "exit_price": 10})
    assert r.status_code == 404


def test_delete(api_client):
    tid = api_client.post("/api/v1/journal/trades", json={
        "symbol": "Z", "entry_date": "2026-01-01", "entry_price": 10, "qty": 1,
    }).json()["id"]
    assert api_client.delete(f"/api/v1/journal/trades/{tid}").status_code == 200
    assert api_client.get(f"/api/v1/journal/trades/{tid}").status_code == 404
