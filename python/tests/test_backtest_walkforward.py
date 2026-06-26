"""Tests for walk-forward analysis (V2.0 spec M2).

Anchored (expanding-window) walk-forward: for each out-of-sample window, grid-search the
signal's parameters on the in-sample data, then evaluate the chosen params on the held-out
window. Guards against curve-fitting by reporting out-of-sample consistency.
"""

import datetime as dt

import pandas as pd

from stocks.services.quant.backtest.engine import run_backtest
from stocks.services.quant.backtest.signals import sma_crossover_signals
from stocks.services.quant.backtest.walkforward import walk_forward

D = dt.date


def _bars(closes):
    return pd.DataFrame(
        [
            {"trading_date": D(2023, 1, 1) + dt.timedelta(days=i), "open": c, "high": c, "low": c, "close": c}
            for i, c in enumerate(closes)
        ]
    )


def _factory(params):
    return lambda b: sma_crossover_signals(b, **params)


# A 24-bar zig-zag so SMA crossovers actually fire across windows.
_CLOSES = [10, 11, 12, 11, 13, 15, 14, 16, 18, 17, 19, 21, 20, 22, 24, 23, 25, 27, 26, 28, 30, 29, 31, 33]
_GRID = [{"fast": 2, "slow": 3}, {"fast": 3, "slow": 6}]


def test_window_count_and_boundaries():
    res = walk_forward(_bars(_CLOSES), _factory, _GRID, n_splits=3, train_frac=0.5, metric="total_return")
    assert len(res.windows) == 3
    # Anchored: train always starts at 0; test windows are contiguous and non-overlapping.
    prev_end = None
    for w in res.windows:
        assert w.train_end == w.test_start          # expanding train ends where test begins
        assert w.test_end > w.test_start
        if prev_end is not None:
            assert w.test_start == prev_end
        prev_end = w.test_end


def test_best_params_maximize_in_sample_metric():
    bars = _bars(_CLOSES)
    res = walk_forward(bars, _factory, _GRID, n_splits=2, train_frac=0.5, metric="total_return")
    for w in res.windows:
        train = bars.iloc[: w.train_end].reset_index(drop=True)
        # Independently compute the in-sample metric for each grid point (different code path).
        scored = {}
        for p in _GRID:
            entries, exits = sma_crossover_signals(train, **p)
            scored[tuple(sorted(p.items()))] = run_backtest(train, entries, exits=exits).metrics.total_return
        best = max(scored, key=scored.get)
        assert tuple(sorted(w.best_params.items())) == best


def test_aggregate_summary_present():
    res = walk_forward(_bars(_CLOSES), _factory, _GRID, n_splits=3, train_frac=0.5, metric="total_return")
    assert 0.0 <= res.pct_profitable_windows <= 1.0
    assert isinstance(res.avg_oos_return, float)
    assert len(res.windows) == 3
