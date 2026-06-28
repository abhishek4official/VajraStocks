"""Anchored walk-forward analysis (V2.0 spec M2).

Guards against curve-fitting: for each out-of-sample window, grid-search the signal's
parameters on the in-sample (expanding) history, then evaluate the chosen parameters on the
held-out window. Reports per-window results plus out-of-sample consistency.

A ``signal_factory`` maps a params dict to a signal generator, so the same setup can be
re-parameterised across the grid.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

import pandas as pd

from stocks.services.quant.backtest.engine import BacktestConfig, BacktestMetrics, run_backtest

SignalFactory = Callable[[dict[str, Any]], Callable[[pd.DataFrame], tuple[Sequence[bool], Sequence[bool]]]]


@dataclass(frozen=True)
class WindowResult:
    train_end: int          # in-sample is bars[0:train_end] (== test_start, expanding window)
    test_start: int
    test_end: int
    best_params: dict[str, Any]
    in_sample_metric: float
    oos: BacktestMetrics


@dataclass(frozen=True)
class WalkForwardResult:
    windows: list[WindowResult]
    avg_oos_return: float
    avg_oos_sharpe: float
    pct_profitable_windows: float


def _evaluate(bars: pd.DataFrame, signal_fn, stop_pct, target_pct, config) -> BacktestMetrics:
    entries, exits = signal_fn(bars)
    return run_backtest(
        bars, entries, stop_pct=stop_pct, target_pct=target_pct, exits=exits, config=config
    ).metrics


def walk_forward(
    bars: pd.DataFrame,
    signal_factory: SignalFactory,
    param_grid: Sequence[dict[str, Any]],
    *,
    n_splits: int = 4,
    train_frac: float = 0.6,
    metric: str = "sharpe_ratio",
    stop_pct: float | None = None,
    target_pct: float | None = None,
    config: BacktestConfig | None = None,
) -> WalkForwardResult:
    """Run anchored walk-forward over ``bars``. See module docstring for the method."""
    if not param_grid:
        raise ValueError("param_grid must contain at least one parameter set")

    n = len(bars)
    initial_train = int(n * train_frac)
    remaining = n - initial_train
    if n_splits < 1 or remaining < n_splits:
        raise ValueError("not enough bars for the requested number of splits")

    test_size = remaining // n_splits
    windows: list[WindowResult] = []

    for k in range(n_splits):
        test_start = initial_train + k * test_size
        # Last window absorbs the remainder so all bars are covered.
        test_end = n if k == n_splits - 1 else test_start + test_size
        train = bars.iloc[:test_start].reset_index(drop=True)
        test = bars.iloc[test_start:test_end].reset_index(drop=True)

        # Grid-search parameters on the in-sample window.
        best_params = param_grid[0]
        best_score = float("-inf")
        for params in param_grid:
            signal_fn = signal_factory(params)
            score = getattr(_evaluate(train, signal_fn, stop_pct, target_pct, config), metric)
            if score > best_score:
                best_score, best_params = score, params

        oos = _evaluate(test, signal_factory(best_params), stop_pct, target_pct, config)
        windows.append(
            WindowResult(
                train_end=test_start,
                test_start=test_start,
                test_end=test_end,
                best_params=dict(best_params),
                in_sample_metric=best_score,
                oos=oos,
            )
        )

    avg_return = sum(w.oos.total_return for w in windows) / len(windows)
    avg_sharpe = sum(w.oos.sharpe_ratio for w in windows) / len(windows)
    pct_profitable = sum(1 for w in windows if w.oos.total_return > 0) / len(windows)
    return WalkForwardResult(
        windows=windows,
        avg_oos_return=avg_return,
        avg_oos_sharpe=avg_sharpe,
        pct_profitable_windows=pct_profitable,
    )
