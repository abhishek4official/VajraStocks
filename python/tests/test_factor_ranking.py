"""Tests for ranking a symbol set by raw academic factors (V2.0 spec M6)."""

import datetime as dt

import pandas as pd
import pytest

from stocks.data.bar_store import BarStore
from stocks.services.quant.factor_ranking import rank_symbols_by_factors

D = dt.date


@pytest.fixture
def store(tmp_path):
    s = BarStore(tmp_path / "col")
    # Each symbol gets a clean uptrend of differing slope (stronger momentum for AAA).
    for sym, step in [("AAA", 6.0), ("BBB", 3.0), ("CCC", 1.0)]:
        rows = []
        price = 100.0
        for i in range(8):
            price += step
            rows.append({
                "trading_date": D(2023, 1, 1) + dt.timedelta(days=i),
                "open": price, "high": price, "low": price, "close": price,
                "adj_close": price, "volume": 1000,
            })
        s.write_bars(f"{sym}.NS", pd.DataFrame(rows))
    return s


def test_rank_by_momentum(store):
    ranked = rank_symbols_by_factors(
        store, ["AAA.NS", "BBB.NS", "CCC.NS"],
        weights={"momentum": 1.0, "low_volatility": 0.0, "high_proximity": 0.0},
        momentum_lookback=2, momentum_skip=1, vol_window=3, high_window=4,
    )
    assert [r["symbol"] for r in ranked] == ["AAA.NS", "BBB.NS", "CCC.NS"]
    assert ranked[0]["composite_z"] > ranked[-1]["composite_z"]
    assert "momentum" in ranked[0]["factors"]


def test_missing_symbol_excluded(store):
    ranked = rank_symbols_by_factors(
        store, ["AAA.NS", "NOPE.NS"],
        momentum_lookback=2, momentum_skip=1, vol_window=3, high_window=4,
    )
    syms = {r["symbol"] for r in ranked}
    assert "NOPE.NS" not in syms  # no bars -> no factors -> excluded
