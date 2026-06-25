"""Tests for backtest performance metrics (V2.0 spec M2).

These replace the deleted fabricated backtester. Every metric is a pure function of the
inputs and verified against hand-computed values, so a backtest can never again return a
constant. compute_metrics() must be reproducible: identical inputs -> identical output.
"""

import math

import numpy as np
import pytest

from stocks.services.quant.backtest.metrics import (
    cagr,
    compute_metrics,
    max_drawdown,
    profit_factor,
    sharpe_ratio,
    total_return,
    win_rate,
)


def test_total_return():
    assert total_return([100, 120]) == pytest.approx(0.20)
    assert total_return([100, 80]) == pytest.approx(-0.20)
    assert total_return([100]) == 0.0
    assert total_return([]) == 0.0


def test_cagr():
    assert cagr([100, 120], years=1.0) == pytest.approx(0.20)
    assert cagr([100, 144], years=2.0) == pytest.approx(0.20)  # 1.44^(1/2)-1
    assert cagr([100, 120], years=0.0) == 0.0  # guard divide-by-zero


def test_max_drawdown():
    # peaks: 100,110,110,120 ; trough rel peak at 105 -> (110-105)/110
    assert max_drawdown([100, 110, 105, 120]) == pytest.approx(5 / 110)
    assert max_drawdown([100, 90, 80]) == pytest.approx(0.20)  # monotonic down
    assert max_drawdown([100, 110, 120]) == 0.0  # monotonic up
    assert max_drawdown([100]) == 0.0


def test_win_rate():
    assert win_rate([10, -5, 15, -5]) == pytest.approx(0.5)
    assert win_rate([1, 2, 3]) == 1.0
    assert win_rate([]) == 0.0  # no trades -> 0, never a fabricated default


def test_profit_factor():
    assert profit_factor([10, -5, 15, -5]) == pytest.approx(25 / 10)  # 2.5
    assert profit_factor([10, 20]) == math.inf  # no losses
    assert profit_factor([]) == 0.0
    assert profit_factor([-5, -10]) == 0.0  # no gains


def test_sharpe_ratio_matches_independent_numpy():
    returns = [0.01, -0.005, 0.02, 0.0, 0.015]
    arr = np.array(returns)
    expected = (arr.mean() / arr.std(ddof=1)) * math.sqrt(252)
    assert sharpe_ratio(returns, periods_per_year=252) == pytest.approx(expected)


def test_sharpe_ratio_degenerate_cases():
    assert sharpe_ratio([], periods_per_year=252) == 0.0
    assert sharpe_ratio([0.01], periods_per_year=252) == 0.0  # need >=2 for std
    assert sharpe_ratio([0.01, 0.01, 0.01], periods_per_year=252) == 0.0  # zero variance


def test_compute_metrics_is_reproducible_and_correct():
    equity = [100.0, 110.0, 105.0, 120.0]
    trades = [10.0, -5.0, 15.0]
    m1 = compute_metrics(equity_curve=equity, trade_returns=trades, years=1.0)
    m2 = compute_metrics(equity_curve=equity, trade_returns=trades, years=1.0)

    # Reproducible
    assert m1 == m2
    # Correct (computed, not constant)
    assert m1.total_return == pytest.approx(0.20)
    assert m1.max_drawdown == pytest.approx(5 / 110)
    assert m1.trades == 3
    assert m1.win_rate == pytest.approx(2 / 3)
    assert m1.profit_factor == pytest.approx(25 / 5)
    # And explicitly NOT the old fabricated constants
    assert m1.sharpe_ratio != 1.75
    assert m1.win_rate != 0.5545
