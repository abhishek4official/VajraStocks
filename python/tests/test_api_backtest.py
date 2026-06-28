"""API tests for the Backtest Lab endpoints (V2.0 spec M2)."""

import datetime as dt

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from stocks.api.deps import get_bar_store, get_db
from stocks.api.main import app
from stocks.data.bar_store import BarStore
from stocks.db.models import DailyPrice, Symbol

D = dt.date


@pytest.fixture
def store(tmp_path):
    s = BarStore(tmp_path / "col")
    closes = [10, 10, 10, 12, 14, 12, 10, 9]
    s.write_bars(
        "ACME.NS",
        pd.DataFrame(
            [
                {
                    "trading_date": D(2023, 1, 1) + dt.timedelta(days=i),
                    "open": c, "high": c, "low": c, "close": c, "adj_close": c, "volume": 1000,
                }
                for i, c in enumerate(closes)
            ]
        ),
    )
    # A longer series for walk-forward windows.
    long_closes = [10, 11, 12, 11, 13, 15, 14, 16, 18, 17, 19, 21, 20, 22, 24, 23, 25, 27, 26, 28]
    s.write_bars(
        "WIDE.NS",
        pd.DataFrame(
            [
                {
                    "trading_date": D(2023, 3, 1) + dt.timedelta(days=i),
                    "open": c, "high": c, "low": c, "close": c, "adj_close": c, "volume": 1000,
                }
                for i, c in enumerate(long_closes)
            ]
        ),
    )
    # A small multi-symbol panel for portfolio backtests.
    for si, sym in enumerate(["PA.NS", "PB.NS", "PC.NS"]):
        price = 100.0 + si * 10
        rows = []
        for i in range(70):
            price *= 1 + 0.01 * (((i + si) % 5) - 1.5) / 3
            c = round(price, 2)
            rows.append({
                "trading_date": D(2022, 1, 3) + dt.timedelta(days=i),
                "open": c, "high": round(c * 1.01, 2), "low": round(c * 0.99, 2),
                "close": c, "adj_close": c, "volume": 100000,
            })
        s.write_bars(sym, pd.DataFrame(rows))
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


def test_walk_forward_endpoint(api_client):
    resp = api_client.post("/api/v1/backtest/walk-forward", json={
        "symbol": "WIDE", "signal": "sma_crossover",
        "param_grid": [{"fast": 2, "slow": 3}, {"fast": 3, "slow": 6}],
        "n_splits": 2, "train_frac": 0.5, "metric": "total_return",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["windows"]) == 2
    assert 0.0 <= body["pct_profitable_windows"] <= 1.0
    # Each window's chosen params come from the supplied grid.
    for w in body["windows"]:
        assert w["best_params"] in [{"fast": 2, "slow": 3}, {"fast": 3, "slow": 6}]


def test_walk_forward_empty_grid_400(api_client):
    resp = api_client.post("/api/v1/backtest/walk-forward", json={"symbol": "WIDE", "param_grid": []})
    assert resp.status_code == 400


def test_portfolio_endpoint_runs_real_strategy(api_client):
    resp = api_client.post("/api/v1/backtest/portfolio", json={
        "strategy_id": "minervini",
        "universe": ["PA", "PB", "PC"],
        "force_market_ok": True,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbols"] == 3
    assert body["bars"] == len(body["equity_curve"]) > 0
    assert isinstance(body["metrics"]["total_return"], (int, float))


def test_portfolio_unknown_strategy_404(api_client):
    resp = api_client.post("/api/v1/backtest/portfolio", json={"strategy_id": "nope", "universe": ["PA"]})
    assert resp.status_code == 404


def test_portfolio_empty_universe_400(api_client):
    resp = api_client.post("/api/v1/backtest/portfolio", json={"strategy_id": "minervini", "universe": ["ZZZ"]})
    assert resp.status_code == 400  # no stored bars for ZZZ


def test_backfill_endpoint_mirrors_db_prices(api_client, db_session, store):
    sym = Symbol(symbol="BFILL.NS", company_name="Backfill Co", isin="INE0BFILL1", series="EQ", is_active=True)
    db_session.add(sym)
    db_session.flush()
    for d, c in [(D(2023, 5, 1), 100.0), (D(2023, 5, 2), 101.0)]:
        db_session.add(DailyPrice(
            symbol_id=sym.id, trading_date=d, open=c, high=c, low=c, close=c,
            adj_close=c, volume=1000, granularity="1d", data_source="TEST",
        ))
    db_session.commit()

    resp = api_client.post("/api/v1/backtest/backfill")
    assert resp.status_code == 200
    assert resp.json()["symbols_mirrored"] >= 1
    # The DB prices are now readable from the columnar store.
    assert len(store.read_bars("BFILL.NS")) == 2
