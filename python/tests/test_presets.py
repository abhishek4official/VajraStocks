"""Tests for screener setup presets (V2.0 spec M4).

Pure predicates over a snapshot row (dict) — the "8-10 setups I actually trade" the spec
wants, instead of 40 sliders. Each preset is a boolean function robust to missing fields.
"""

import pytest

from stocks.services.quant.presets import get_preset, list_presets, passes


def test_list_presets_nonempty():
    names = [p["name"] for p in list_presets()]
    for expected in ("stage2_uptrend", "pullback_20ema", "nr7_coil", "momentum_leader"):
        assert expected in names


def test_unknown_preset_raises():
    with pytest.raises(ValueError):
        get_preset("does_not_exist")


def test_stage2_uptrend():
    fn = get_preset("stage2_uptrend")
    assert fn({"weinstein_stage": 2, "sma_200_cross_direction": "ABOVE"}) is True
    assert fn({"weinstein_stage": 1, "sma_200_cross_direction": "ABOVE"}) is False
    assert fn({"weinstein_stage": 2, "sma_200_cross_direction": "BELOW"}) is False


def test_pullback_20ema():
    fn = get_preset("pullback_20ema")
    assert fn({"sma_200_cross_direction": "ABOVE", "rsi_14": 48}) is True
    assert fn({"sma_200_cross_direction": "ABOVE", "rsi_14": 72}) is False   # not a pullback
    assert fn({"sma_200_cross_direction": "BELOW", "rsi_14": 48}) is False   # not an uptrend


def test_nr7_coil():
    fn = get_preset("nr7_coil")
    assert fn({"is_nr7": True}) is True
    assert fn({"is_nr7": False}) is False
    assert fn({}) is False                                                    # missing -> False


def test_momentum_leader():
    fn = get_preset("momentum_leader")
    assert fn({"rs_score_val": 80, "ret_4w": 0.05, "sma_200_cross_direction": "ABOVE"}) is True
    assert fn({"rs_score_val": 40, "ret_4w": 0.05, "sma_200_cross_direction": "ABOVE"}) is False
    assert fn({"rs_score_val": 80, "ret_4w": -0.02, "sma_200_cross_direction": "ABOVE"}) is False


def test_oversold_reversal():
    fn = get_preset("oversold_reversal")
    assert fn({"rsi_14": 28, "stochrsi_bullish_xover_days_ago": 1}) is True
    assert fn({"rsi_14": 55, "stochrsi_bullish_xover_days_ago": 1}) is False
    assert fn({"rsi_14": 28, "stochrsi_bullish_xover_days_ago": None}) is False


def test_passes_helper():
    assert passes("nr7_coil", {"is_nr7": True}) is True
