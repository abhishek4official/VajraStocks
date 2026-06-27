"""Tests for backtest statistical guards (V2.0 spec M2): probabilistic & deflated Sharpe.

Bailey & López de Prado: the Probabilistic Sharpe Ratio (PSR) is the confidence that a
strategy's true Sharpe exceeds a benchmark given sample length and return shape; the
Deflated Sharpe Ratio (DSR) raises that benchmark to the expected-maximum Sharpe across
many trials, guarding against multiple-testing / backtest overfitting.
"""

import math

import pytest
from scipy.stats import norm

from stocks.services.quant.backtest.statistics import (
    deflated_sharpe_ratio,
    probabilistic_sharpe_from_equity,
    probabilistic_sharpe_ratio,
)


def test_psr_zero_sharpe_is_half():
    assert probabilistic_sharpe_ratio(0.0, n_obs=100) == pytest.approx(0.5)


def test_psr_positive_sharpe_above_half():
    assert probabilistic_sharpe_ratio(0.2, n_obs=100) > 0.5


def test_psr_more_data_more_confident():
    assert probabilistic_sharpe_ratio(0.1, n_obs=500) > probabilistic_sharpe_ratio(0.1, n_obs=50)


def test_psr_matches_closed_form():
    sr, n = 0.1, 50
    z = sr * math.sqrt(n - 1) / math.sqrt(1.0)  # skew=0, kurtosis=3 -> denom 1.0 at sr small? compute exact
    denom = math.sqrt(1 - 0.0 * sr + (3.0 - 1) / 4 * sr**2)
    z = sr * math.sqrt(n - 1) / denom
    assert probabilistic_sharpe_ratio(sr, n_obs=n) == pytest.approx(norm.cdf(z))


def test_psr_in_unit_interval():
    for sr in (-0.5, 0.0, 0.5, 2.0):
        p = probabilistic_sharpe_ratio(sr, n_obs=200)
        assert 0.0 <= p <= 1.0


def test_dsr_deflates_below_psr():
    sr, n = 0.15, 250
    psr = probabilistic_sharpe_ratio(sr, n_obs=n)
    dsr = deflated_sharpe_ratio(sr, n_obs=n, n_trials=20, sharpe_variance=0.04)
    assert dsr < psr          # raising the benchmark lowers the confidence
    assert 0.0 <= dsr <= 1.0


def test_psr_from_equity_rising_is_confident():
    psr = probabilistic_sharpe_from_equity([100, 101, 102, 103, 104, 105])
    assert psr > 0.5


def test_psr_from_equity_flat_is_half():
    assert probabilistic_sharpe_from_equity([100, 100, 100, 100]) == pytest.approx(0.5)


def test_psr_from_equity_too_short():
    assert probabilistic_sharpe_from_equity([100]) == 0.0


def test_dsr_more_trials_more_deflation():
    few = deflated_sharpe_ratio(0.15, n_obs=250, n_trials=5, sharpe_variance=0.04)
    many = deflated_sharpe_ratio(0.15, n_obs=250, n_trials=200, sharpe_variance=0.04)
    assert many < few         # more trials -> higher expected-max benchmark -> lower DSR
