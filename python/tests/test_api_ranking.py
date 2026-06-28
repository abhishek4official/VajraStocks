"""Tests for cross-sectional ranking (service + API), V2.0 spec M4."""

import datetime as dt

import pytest
from fastapi.testclient import TestClient

from stocks.api.deps import get_db
from stocks.api.main import app
from stocks.db.models import ScreeningSnapshot
from stocks.services.quant.ranking import compute_ranking

_SID = {"AAA.NS": 1, "BBB.NS": 2, "CCC.NS": 3}


def _snap(symbol, **scores):
    return ScreeningSnapshot(
        symbol_id=_SID[symbol], symbol=symbol, company_name=symbol,
        last_trading_date=dt.date(2026, 6, 5),
        close_price=100.0, volume=1000, ha_close=100.0, ha_direction="UP", **scores,
    )


@pytest.fixture
def seeded(db_session):
    # Three names with clearly ordered factor scores.
    for snap in [
        _snap("AAA.NS", trend_score_val=90, momentum_score_val=80, rs_score_val=85,
              volume_score_val=70, cmf_score_val=60, breakout_score_val=75),
        _snap("BBB.NS", trend_score_val=50, momentum_score_val=50, rs_score_val=50,
              volume_score_val=50, cmf_score_val=50, breakout_score_val=50),
        _snap("CCC.NS", trend_score_val=10, momentum_score_val=20, rs_score_val=15,
              volume_score_val=30, cmf_score_val=40, breakout_score_val=25),
    ]:
        db_session.add(snap)
        db_session.commit()
    return db_session


def test_ranking_orders_by_composite(seeded):
    ranked = compute_ranking(seeded)
    assert [r["symbol"] for r in ranked] == ["AAA.NS", "BBB.NS", "CCC.NS"]
    assert ranked[0]["composite_z"] > ranked[-1]["composite_z"]
    assert ranked[0]["percentile"] == pytest.approx(100.0)
    assert ranked[-1]["percentile"] == pytest.approx(0.0)


def test_ranking_api(seeded):
    app.dependency_overrides[get_db] = lambda: seeded
    try:
        client = TestClient(app)
        rows = client.get("/api/v1/ranking?limit=2").json()
        assert len(rows) == 2
        assert rows[0]["symbol"] == "AAA.NS"
        assert "trend" in rows[0]["factors"]
        meta = client.get("/api/v1/ranking/factors").json()
        assert "momentum" in meta["factors"]
    finally:
        app.dependency_overrides.clear()
