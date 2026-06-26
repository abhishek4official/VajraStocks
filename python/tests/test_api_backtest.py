"""API tests for the Backtest Lab endpoints (V2.0 spec M2)."""

import datetime as dt

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from stocks.api.deps import get_bar_store, get_db
from stocks.api.main import app
from stocks.data.bar_store import BarStore
from stocks.db.models import Symbol

D = dt.date


@pytest.fixture
def store(tmp_path):
    s = BarStore(tmp_path / "col")
    s.write_bars(
        "ACME.NS",
        pd.DataFrame(
            [
                {
                    "trading_date": D(2023, 1, 1) + dt.timedelta(days=i),
                    "open": c, "high": c, "low": c, "close": c, "adj_close": c, "volume": 1000,
                }
                for i, c in enumerate([10, 10, 10, 12, 14, 12, 10, 9])
            ]
        ),
    )
    return s


@pytest.fixture
def api_client(db_session, store):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_bar_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_list_signals(api_client):
    resp = api_client.get("/api/v1/backtest/signals")
    assert resp.status_code == 200
    assert "breakout" in resp.json()["signals"]


def test_run_unknown_signal_returns_400(api_client):
    resp = api_client.post("/api/v1/backtest/run", json={"symbol": "ACME", "signal": "nope"})
    assert resp.status_code == 400


def test_run_and_persist_then_fetch(api_client, db_session):
    db_session.add(Symbol(symbol="ACME.NS", company_name="Acme", isin="INE0ACME01", series="EQ", is_active=True))
    db_session.commit()

    # Run with a fast/slow that actually trades on 8 bars, and save it.
    resp = api_client.post("/api/v1/backtest/run", json={
        "symbol": "ACME", "signal": "sma_crossover",
        "params": {"fast": 2, "slow": 3}, "save": True,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == "ACME.NS"
    assert body["bars"] == 8
    assert body["metrics"]["trades"] == 1
    assert body["run_id"] is not None

    run_id = body["run_id"]

    # List shows it.
    runs = api_client.get("/api/v1/backtest/runs?symbol=ACME").json()
    assert any(r["id"] == run_id for r in runs)

    # Detail returns metrics + trades; stored metrics match the run response (reproducible).
    detail = api_client.get(f"/api/v1/backtest/runs/{run_id}").json()
    assert detail["trades_count"] == 1
    assert detail["metrics"]["total_return"] == pytest.approx(body["metrics"]["total_return"])


def test_get_missing_run_404(api_client):
    assert api_client.get("/api/v1/backtest/runs/999999").status_code == 404
