import datetime

import pytest
from fastapi.testclient import TestClient

from stocks.api.deps import get_db
from stocks.api.main import app
from stocks.db.models import (
    DailyPrice,
    ScreeningSnapshot,
    Symbol,
)


@pytest.fixture(scope="function")
def api_client(db_session):
    """Provides a TestClient with dependency overrides redirecting DB to in-memory SQLite."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_api_health_check(api_client):
    """Verifies that the /health check endpoint is active and returns status HEALTHY."""
    response = api_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "HEALTHY"


def test_api_symbols_endpoints(api_client, db_session):
    """Verifies that GET /symbols and GET /symbols/{symbol} resolve and filter correctly."""
    # Seed 2 test symbols
    sym1 = Symbol(symbol="MOCK1.NS", company_name="Mock Company One", isin="INE000000001", series="EQ", is_active=True)
    sym2 = Symbol(symbol="MOCK2.NS", company_name="Mock Company Two", isin="INE000000002", series="EQ", is_active=False)
    db_session.add_all([sym1, sym2])
    db_session.commit()

    # 1. Test GET /symbols with active_only=True (default)
    response = api_client.get("/api/v1/symbols")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["symbol"] == "MOCK1.NS"

    # 2. Test GET /symbols with active_only=False
    response = api_client.get("/api/v1/symbols?active_only=false")
    assert response.status_code == 200
    assert len(response.json()) == 2

    # 3. Test GET /symbols/{symbol} details
    response = api_client.get("/api/v1/symbols/MOCK1.NS")
    assert response.status_code == 200
    assert response.json()["company_name"] == "Mock Company One"

    # 4. Test GET /symbols/{symbol} missing 404
    response = api_client.get("/api/v1/symbols/MISSING.NS")
    assert response.status_code == 404


def test_api_strategies_endpoints(api_client, db_session):
    """Verifies the Strategy Screener API: registry list, materialized signals, detail, 404s."""
    import json as _json

    from stocks.db.models import StrategySignal

    # 1. Registry list includes the swing strategies with a param schema.
    resp = api_client.get("/api/v1/strategies")
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()]
    assert "minervini" in ids
    meta = next(s for s in resp.json() if s["id"] == "minervini")
    assert meta["param_schema"] and "stop_atr_mult" in meta["param_schema"]

    # Seed a symbol + a materialized BUY signal.
    sym = Symbol(symbol="ACME.NS", company_name="Acme Ltd", isin="INE000ACME1", series="EQ", is_active=True)
    db_session.add(sym)
    db_session.commit()
    db_session.add(StrategySignal(
        symbol_id=sym.id, symbol="ACME.NS", company_name="Acme Ltd",
        strategy_id="minervini", as_of=datetime.date(2026, 6, 5), signal="BUY",
        score=92.0, last_close=100.0, entry_ref=100.0, initial_stop=91.0, target=None,
        risk_pct=0.09, rr=None, key_metrics=_json.dumps({"leadership": 0.42}),
        gates=_json.dumps({"eligible": True, "hold_ok": True}),
        reasons=_json.dumps(["Minervini: eligible entry", "market risk_on=True"]),
    ))
    db_session.commit()

    # 2. Signals list returns the BUY row with parsed JSON + counts.
    resp = api_client.get("/api/v1/strategies/minervini/signals?signal=BUY&min_score=70")
    assert resp.status_code == 200
    body = resp.json()
    assert body["counts"]["BUY"] == 1
    assert body["as_of"] == "2026-06-05"
    assert len(body["rows"]) == 1
    row = body["rows"][0]
    assert row["symbol"] == "ACME.NS" and row["score"] == 92.0
    assert row["gates"]["eligible"] is True and row["reasons"][0].startswith("Minervini")

    # 3. Detail endpoint resolves a bare ticker.
    resp = api_client.get("/api/v1/strategies/minervini/signals/ACME")
    assert resp.status_code == 200
    assert resp.json()["entry_ref"] == 100.0

    # 4. Unknown strategy → 404.
    assert api_client.get("/api/v1/strategies/nope/signals").status_code == 404

    # 5. Matrix endpoint pivots symbol × strategy with a consensus tally.
    db_session.add(StrategySignal(
        symbol_id=sym.id, symbol="ACME.NS", company_name="Acme Ltd",
        strategy_id="high52", as_of=datetime.date(2026, 6, 5), signal="WATCH",
        score=70.0, last_close=100.0, updated_at=datetime.datetime.now(),
    ))
    db_session.commit()
    resp = api_client.get("/api/v1/strategies/matrix?only_active=true")
    assert resp.status_code == 200
    mat = resp.json()
    assert any(s["id"] == "minervini" for s in mat["strategies"])
    acme = next(r for r in mat["rows"] if r["symbol"] == "ACME.NS")
    assert acme["cells"]["minervini"]["signal"] == "BUY"
    assert acme["cells"]["high52"]["signal"] == "WATCH"
    assert acme["consensus"]["BUY"] == 1 and acme["consensus"]["WATCH"] == 1


def test_api_charts_endpoints(api_client, db_session):
    """Verifies that all charts endpoints return valid chronological JSON arrays."""
    sym = Symbol(symbol="MOCK1.NS", company_name="Mock Company", isin="INE000000001", series="EQ", is_active=True)
    db_session.add(sym)
    db_session.commit()

    # Seed prices
    t_date = datetime.date(2026, 5, 29)
    price = DailyPrice(
        symbol_id=sym.id,
        trading_date=t_date,
        open=100.0,
        high=105.0,
        low=95.0,
        close=102.0,
        adj_close=102.0,
        volume=5000,
    )
    db_session.add(price)
    db_session.commit()

    # 1. Test GET /charts/{symbol}/candles
    response = api_client.get("/api/v1/charts/MOCK1.NS/candles")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["close"] == 102.0
    assert data[0]["time"] == "2026-05-29"


def test_api_screening_endpoints(api_client, db_session):
    """Verifies screener sweeps directly hit snapshots and filter properly."""
    sym = Symbol(symbol="MOCK1.NS", company_name="Mock Company", isin="INE000000001", series="EQ", is_active=True)
    db_session.add(sym)
    db_session.commit()

    snap = ScreeningSnapshot(
        symbol_id=sym.id,
        symbol="MOCK1.NS",
        company_name="Mock Company",
        last_trading_date=datetime.date(2026, 5, 29),
        close_price=102.0,
        volume=5000,
        ha_close=102.0,
        ha_direction="UP",
        rsi_14=72.5,
        sma_200_cross_direction="ABOVE",
    )
    db_session.add(snap)
    db_session.commit()

    # 1. Test GET /screeners with overbought RSI query filter
    response = api_client.get("/api/v1/screeners?min_rsi=70")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["symbol"] == "MOCK1.NS"
    assert data[0]["rsi_14"] == 72.5

    # 2. Test POST /screeners/run with custom body
    response = api_client.post("/api/v1/screeners/run", json={"min_rsi": 75})
    assert response.status_code == 200
    assert len(response.json()) == 0  # 72.5 < 75, so should be filtered out!


def test_api_screening_volume_filters(api_client, db_session):
    """Verifies that weekly average volume and breakout metrics are computed dynamically and filtered correctly."""
    sym = Symbol(
        symbol="VOLMOCK.NS", company_name="Volume Mock Company", isin="INE000000003", series="EQ", is_active=True
    )
    db_session.add(sym)
    db_session.commit()

    # Seed 6 daily prices to test rolling volumes
    dates = [
        datetime.date(2026, 5, 29),  # Today (rn=1, volume=15000)
        datetime.date(2026, 5, 28),  # rn=2, volume=5000
        datetime.date(2026, 5, 27),  # rn=3, volume=4000
        datetime.date(2026, 5, 26),  # rn=4, volume=6000
        datetime.date(2026, 5, 25),  # rn=5, volume=5000
        datetime.date(2026, 5, 22),  # rn=6, volume=5000
    ]
    volumes = [15000, 5000, 4000, 6000, 5000, 5000]

    for d, v in zip(dates, volumes):
        p = DailyPrice(
            symbol_id=sym.id, trading_date=d, open=100.0, high=105.0, low=95.0, close=100.0, adj_close=100.0, volume=v
        )
        db_session.add(p)

    # Add snapshot
    snap = ScreeningSnapshot(
        symbol_id=sym.id,
        symbol="VOLMOCK.NS",
        company_name="Volume Mock Company",
        last_trading_date=datetime.date(2026, 5, 29),
        close_price=100.0,
        volume=15000,
        ha_close=100.0,
        ha_direction="UP",
    )
    db_session.add(snap)
    db_session.commit()

    # 1. Query with volume filter matching average (average of preceding 5 is 5000, close is 100, so avg traded value is 500,000)
    response = api_client.post("/api/v1/screeners/run", json={"min_avg_traded_value": 450000})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["symbol"] == "VOLMOCK.NS"
    assert data[0]["avg_traded_value"] == 500000.0
    assert data[0]["volume_breakout_ratio"] == 3.0

    # 2. Query with too high average (should not match)
    response = api_client.post("/api/v1/screeners/run", json={"min_avg_traded_value": 600000})
    assert response.status_code == 200
    assert len(response.json()) == 0

    # 3. Query with 3.0x Breakout (should match)
    response = api_client.post("/api/v1/screeners/run", json={"volume_breakout": "3.0X"})
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["symbol"] == "VOLMOCK.NS"

    # 4. Query with 2.0x Breakout (should match since 3.0 >= 2.0)
    response = api_client.post("/api/v1/screeners/run", json={"volume_breakout": "2.0X"})
    assert response.status_code == 200
    assert len(response.json()) == 1

    # 5. Query with 1.5x Breakout (should match)
    response = api_client.post("/api/v1/screeners/run", json={"volume_breakout": "1.5X"})
    assert response.status_code == 200
    assert len(response.json()) == 1
