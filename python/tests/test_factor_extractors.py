"""Tests for raw factor extractors (V2.0 spec M6).

Pure functions computing academic factor values from a close-price series: price momentum
(trailing return skipping the most recent days), low-volatility (negative return stdev so
higher = calmer = better), and 52-week-high proximity. Insufficient history -> None.
"""

import numpy as np
import pandas as pd
import pytest

from stocks.services.quant.factor_extractors import (
    high_proximity,
    low_volatility,
    momentum,
    symbol_factors,
)


def test_momentum():
    # lookback=2, skip=1: closes[-2]/closes[-4] - 1 = 30/10 - 1 = 2.0
    assert momentum([10, 20, 30, 40], lookback=2, skip=1) == pytest.approx(2.0)


def test_momentum_insufficient_history():
    assert momentum([10, 20], lookback=2, skip=1) is None


def test_low_volatility_matches_numpy():
    closes = [100, 110, 99, 108]
    rets = np.diff(closes) / np.array(closes[:-1])
    expected = -float(np.std(rets, ddof=1))
    assert low_volatility(closes, window=3) == pytest.approx(expected)


def test_low_volatility_higher_is_calmer():
    calm = low_volatility([100, 101, 100, 101, 100], window=4)
    wild = low_volatility([100, 130, 90, 140, 80], window=4)
    assert calm > wild  # less volatile -> higher (less negative) score


def test_high_proximity():
    assert high_proximity([10, 20, 15, 18], window=4) == pytest.approx(0.9)  # 18 / max(20)


def test_high_proximity_insufficient():
    assert high_proximity([], window=4) is None


def test_symbol_factors_from_bars():
    bars = pd.DataFrame({"close": [10, 20, 30, 40]})
    f = symbol_factors(bars, momentum_lookback=2, momentum_skip=1, vol_window=3, high_window=4)
    assert f["momentum"] == pytest.approx(2.0)
    assert f["high_proximity"] == pytest.approx(1.0)  # last is the max
    assert isinstance(f["low_volatility"], float)
