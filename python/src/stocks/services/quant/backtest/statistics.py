"""Statistical guards against backtest overfitting (V2.0 spec M2).

Probabilistic Sharpe Ratio (PSR) and Deflated Sharpe Ratio (DSR), per Bailey & López de
Prado. PSR answers "how confident are we the true Sharpe beats a benchmark, given the
sample length and the return distribution's shape?". DSR raises that benchmark to the
expected maximum Sharpe across N independent trials — the multiple-testing correction that
exposes strategies that only look good because many were tried.

The ``sharpe`` arguments here are **per-observation** (non-annualised) Sharpe ratios.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from scipy.stats import norm

_EULER_MASCHERONI = 0.5772156649015329


def probabilistic_sharpe_ratio(
    sharpe: float,
    n_obs: int,
    skew: float = 0.0,
    kurtosis: float = 3.0,
    benchmark_sharpe: float = 0.0,
) -> float:
    """Probability that the true Sharpe exceeds ``benchmark_sharpe``.

    ``kurtosis`` is the non-excess kurtosis (3 for a normal distribution). Returns 0.5 when
    the observed Sharpe equals the benchmark; 0.0/1.0 in the limits.
    """
    if n_obs < 2:
        return 0.0
    denom = math.sqrt(1.0 - skew * sharpe + (kurtosis - 1.0) / 4.0 * sharpe**2)
    if denom <= 0:
        return 0.0
    z = (sharpe - benchmark_sharpe) * math.sqrt(n_obs - 1) / denom
    return float(norm.cdf(z))


def expected_max_sharpe(n_trials: int, sharpe_variance: float) -> float:
    """Expected maximum Sharpe across ``n_trials`` independent strategies (mean 0).

    Uses the standard extreme-value approximation; grows with both the number of trials and
    the cross-trial variance of Sharpe ratios.
    """
    if n_trials < 2 or sharpe_variance <= 0:
        return 0.0
    e = math.e
    quantile = (
        (1.0 - _EULER_MASCHERONI) * norm.ppf(1.0 - 1.0 / n_trials)
        + _EULER_MASCHERONI * norm.ppf(1.0 - 1.0 / (n_trials * e))
    )
    return float(math.sqrt(sharpe_variance) * quantile)


def probabilistic_sharpe_from_equity(
    equity_curve: Sequence[float],
    periods_per_year: int = 252,
) -> float:
    """Convenience: PSR (vs a 0 benchmark) computed from a backtest equity curve.

    Confidence that the strategy's true (per-period) Sharpe is positive given the sample
    length. 0.5 means indistinguishable from zero; higher is more confident.
    """
    returns = [
        equity_curve[i] / equity_curve[i - 1] - 1.0
        for i in range(1, len(equity_curve))
        if equity_curve[i - 1] > 0
    ]
    n = len(returns)
    if n < 2:
        return 0.0
    mean = sum(returns) / n
    variance = sum((r - mean) ** 2 for r in returns) / (n - 1)
    if variance <= 0:
        return 0.5  # zero variance and zero excess -> indistinguishable from the benchmark
    per_period_sr = mean / math.sqrt(variance)
    return probabilistic_sharpe_ratio(per_period_sr, n_obs=n)


def deflated_sharpe_ratio(
    sharpe: float,
    n_obs: int,
    n_trials: int,
    sharpe_variance: float,
    skew: float = 0.0,
    kurtosis: float = 3.0,
) -> float:
    """PSR evaluated against the expected-maximum Sharpe across ``n_trials`` (multiple-testing).

    With more trials the benchmark rises, so the deflated probability falls — a strategy
    found by searching many candidates must clear a higher bar.
    """
    benchmark = expected_max_sharpe(n_trials, sharpe_variance)
    return probabilistic_sharpe_ratio(sharpe, n_obs, skew, kurtosis, benchmark_sharpe=benchmark)
