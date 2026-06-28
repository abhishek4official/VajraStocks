"""API tests for screener presets (V2.0 spec M4)."""

import datetime as dt

import pytest
from fastapi.testclient import TestClient

from stocks.api.deps import get_db
from stocks.api.main import app
from stocks.db.models import ScreeningSnapshot


def _snap(sid, symbol, **fields):
    return ScreeningSnapshot(
        symbol_id=sid, symbol=symbol, company_name=symbol, last_trading_date=dt.date(2026, 6, 5),
        close_price=100.0, volume=1000, ha_close=100.0, ha_direction="UP", **fields,
    )


@pytest.fixture
def api_client(db_session):
    # A Stage-2 name and a non-matching one.
    for snap in [
        _snap(1, "WIN.NS", weinstein_stage=2, sma_200_cross_direction="ABOVE", composite_score=88),
        _snap(2, "MEH.NS", weinstein_stage=1, sma_200_cross_direction="BELOW", composite_score=40),
    ]:
        db_session.add(snap)
        db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_list_presets(api_client):
    names = [p["name"] for p in api_client.get("/api/v1/presets").json()]
    assert "stage2_uptrend" in names


def test_run_preset_filters(api_client):
    body = api_client.get("/api/v1/presets/stage2_uptrend").json()
    assert body["count"] == 1
    assert body["rows"][0]["symbol"] == "WIN.NS"
    assert body["rows"][0]["composite_score"] == 88


def test_unknown_preset_404(api_client):
    assert api_client.get("/api/v1/presets/nope").status_code == 404
