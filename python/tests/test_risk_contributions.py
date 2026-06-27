"""Tests for portfolio contribution-to-risk (V2.0 spec M5 gap)."""

import pytest

from stocks.services.quant.portfolio_risk import risk_contributions


def test_higher_vol_asset_contributes_more():
    # Equal weights; A is 4x the variance of B; uncorrelated.
    weights = {"A": 0.5, "B": 0.5}
    cov = {"A": {"A": 0.04, "B": 0.0}, "B": {"A": 0.0, "B": 0.01}}
    rc = risk_contributions(weights, cov)
    assert rc["A"] == pytest.approx(0.8)
    assert rc["B"] == pytest.approx(0.2)
    assert sum(rc.values()) == pytest.approx(1.0)


def test_contributions_sum_to_one():
    weights = {"A": 0.6, "B": 0.4}
    cov = {"A": {"A": 0.05, "B": 0.01}, "B": {"A": 0.01, "B": 0.02}}
    rc = risk_contributions(weights, cov)
    assert sum(rc.values()) == pytest.approx(1.0)


def test_zero_variance_returns_empty():
    weights = {"A": 0.5, "B": 0.5}
    cov = {"A": {"A": 0.0, "B": 0.0}, "B": {"A": 0.0, "B": 0.0}}
    assert risk_contributions(weights, cov) == {}
