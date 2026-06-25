"""Swing strategy feature/contract tests on synthetic weekly data."""

import numpy as np
import pandas as pd

from stocks.services.strategies import swing
from stocks.services.strategies.registry import get_strategy


def _weekly(n=160, start=50.0, end=160.0, seed=3):
    dates = pd.bdate_range("2022-01-07", periods=n, freq="W-FRI")
    px = np.linspace(start, end, n) + np.random.RandomState(seed).normal(0, 0.8, n)
    return pd.DataFrame({
        "date": dates, "symbol": "TEST",
        "open": px, "high": px * 1.015, "low": px * 0.985, "close": px, "volume": 1e6,
    })


def _bench(n=160):
    dates = pd.bdate_range("2022-01-07", periods=n, freq="W-FRI")
    return pd.Series(np.linspace(18000, 20000, n), index=pd.to_datetime(dates))


def test_features_return_required_columns():
    for sid in ("minervini", "high52", "weinstein", "momentum", "dual", "rs_ma_cross"):
        strat = get_strategy(sid).make()
        strat.parameters["timeframe"] = "weekly"
        strat._bench_close = _bench()
        feat = strat._features(_weekly())
        for col in ("eligible", "hold_ok", "score", "atr", "close"):
            assert col in feat.columns, f"{sid} missing {col}"
        last = feat.iloc[-1]
        assert isinstance(bool(last["eligible"]), bool)


def test_strong_uptrend_holds_in_minervini():
    strat = get_strategy("minervini").make()
    strat.parameters["timeframe"] = "weekly"
    strat._bench_close = _bench()
    # A steep mover (50 → 250) clears the +30% above 52w-low and stays in Stage 2.
    feat = strat._features(_weekly(end=250.0))
    last = feat.iloc[-1]
    assert bool(last["hold_ok"]) is True
    assert np.isfinite(float(last["score"]))


def test_high52_eligible_near_highs():
    strat = get_strategy("high52").make()
    strat.parameters["timeframe"] = "weekly"
    strat._bench_close = _bench()
    feat = strat._features(_weekly())            # rising series ends at its 52w high
    assert bool(feat.iloc[-1]["eligible"]) is True


def test_timeframe_bar_scaling():
    s = swing.MinerviniTrendTemplate()
    s.parameters["timeframe"] = "weekly"
    assert s._bd(252) == 52          # 252 trading days ≈ 52 weekly bars
    s.parameters["timeframe"] = "monthly"
    assert s._bd(252) == 12          # ≈ 12 monthly bars
    assert s._bm(12) == 12           # 12 months = 12 monthly bars
