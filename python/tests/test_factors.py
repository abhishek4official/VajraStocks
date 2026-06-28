"""Tests for cross-sectional factor ranking (V2.0 spec M4/M6).

Pure functions turning per-symbol raw factor values into *relative* ranks across the
universe — z-scores, percentile ranks, and a weighted composite. This is the missing
piece the screener needs: rank stocks against each other, not against absolute thresholds.
"""


import numpy as np
import pytest

from stocks.services.quant.factors import composite_z, percentile_rank, zscore


def test_zscore_basic_matches_numpy():
    out = zscore({"a": 1.0, "b": 2.0, "c": 3.0})
    arr = np.array([1.0, 2.0, 3.0])
    expected = (arr - arr.mean()) / arr.std(ddof=1)
    assert out["a"] == pytest.approx(expected[0])
    assert out["b"] == pytest.approx(expected[1])
    assert out["c"] == pytest.approx(expected[2])


def test_zscore_constant_is_zero():
    assert zscore({"a": 5.0, "b": 5.0}) == {"a": 0.0, "b": 0.0}


def test_zscore_excludes_none():
    out = zscore({"a": 1.0, "b": None, "c": 3.0})
    assert "b" not in out
    assert set(out) == {"a", "c"}


def test_zscore_single_value():
    assert zscore({"a": 7.0}) == {"a": 0.0}


def test_percentile_rank():
    out = percentile_rank({"a": 10.0, "b": 20.0, "c": 30.0, "d": 40.0})
    assert out["a"] == pytest.approx(0.0)
    assert out["b"] == pytest.approx(100 / 3)
    assert out["c"] == pytest.approx(200 / 3)
    assert out["d"] == pytest.approx(100.0)


def test_percentile_rank_ties():
    out = percentile_rank({"a": 10.0, "b": 20.0, "c": 20.0, "d": 40.0})
    assert out["b"] == out["c"]            # ties share the same percentile
    assert out["a"] == 0.0 and out["d"] == 100.0


def test_composite_z_weighted():
    factors = {
        "momentum": {"a": 1.0, "b": -1.0},
        "value":    {"a": 0.5, "b": -0.5},
    }
    out = composite_z(factors, {"momentum": 0.6, "value": 0.4})
    assert out["a"] == pytest.approx(0.6 * 1.0 + 0.4 * 0.5)
    assert out["b"] == pytest.approx(-(0.6 * 1.0 + 0.4 * 0.5))


def test_composite_z_normalizes_weights_and_skips_missing():
    # 'b' is missing the value factor -> composite uses only the factors it has, reweighted.
    factors = {
        "momentum": {"a": 2.0, "b": 1.0},
        "value":    {"a": 1.0},
    }
    out = composite_z(factors, {"momentum": 1.0, "value": 1.0})
    assert out["a"] == pytest.approx((2.0 + 1.0) / 2)   # both factors, equal weight
    assert out["b"] == pytest.approx(1.0)               # only momentum available
