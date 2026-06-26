"""Tests for single-name setup signal generators (V2.0 spec M2 #1)."""

import datetime as dt

import pandas as pd
import pytest

from stocks.services.quant.backtest.signals import (
    breakout_signals,
    get_signal,
    list_signals,
    sma_crossover_signals,
)

D = dt.date


def _bars(closes):
    return pd.DataFrame(
        [
            {"trading_date": D(2023, 1, 1) + dt.timedelta(days=i), "open": c, "high": c, "low": c, "close": c}
            for i, c in enumerate(closes)
        ]
    )


def _ohlc(rows):
    """rows: list of (open, high, low, close)."""
    return pd.DataFrame(
        [
            {"trading_date": D(2023, 1, 1) + dt.timedelta(days=i), "open": o, "high": h, "low": low, "close": c}
            for i, (o, h, low, c) in enumerate(rows)
        ]
    )


def test_sma_crossover_entry_and_exit_indices():
    # closes rise then fall; fast=2, slow=3: fast crosses above slow at idx 3,
    # and back below at idx 6 (slow[5]=mean(12,14,12)=12.667, so fast 13 is still above at 5).
    bars = _bars([10, 10, 10, 12, 14, 12, 10, 9])
    entries, exits = sma_crossover_signals(bars, fast=2, slow=3)
    assert [i for i, e in enumerate(entries) if e] == [3]
    assert [i for i, x in enumerate(exits) if x] == [6]


def test_sma_crossover_short_series_no_signals():
    bars = _bars([10, 11])  # fewer bars than slow window -> no SMA, no signals
    entries, exits = sma_crossover_signals(bars, fast=2, slow=3)
    assert not any(entries)
    assert not any(exits)
    assert len(entries) == 2 and len(exits) == 2


def test_sma_crossover_empty_bars():
    entries, exits = sma_crossover_signals(_bars([]), fast=2, slow=3)
    assert entries == []
    assert exits == []


# ── Donchian breakout ───────────────────────────────────────────────────────


def test_breakout_entry_on_new_high_and_exit_on_new_low():
    bars = _ohlc([
        (10, 10, 9, 10),
        (11, 11, 10, 11),
        (12, 12, 11, 12),
        (11, 11, 10, 11),
        (14, 20, 18, 20),   # close 20 > prior 3-bar high (12) -> ENTRY at idx 4
        (10, 10, 8, 9),     # close 9 < prior 2-bar low (10) -> EXIT at idx 5
    ])
    entries, exits = breakout_signals(bars, entry_lookback=3, exit_lookback=2)
    assert [i for i, e in enumerate(entries) if e] == [4]
    assert [i for i, x in enumerate(exits) if x] == [5]


def test_breakout_empty_bars():
    entries, exits = breakout_signals(_bars([]), entry_lookback=3, exit_lookback=2)
    assert entries == []
    assert exits == []


# ── signal registry ─────────────────────────────────────────────────────────


def test_registry_lists_builtin_signals():
    names = list_signals()
    assert "sma_crossover" in names
    assert "breakout" in names


def test_registry_get_returns_callable():
    fn = get_signal("breakout")
    entries, exits = fn(_ohlc([(10, 10, 9, 10), (11, 12, 10, 11)]))
    assert len(entries) == 2


def test_registry_unknown_name_raises():
    with pytest.raises(ValueError):
        get_signal("does_not_exist")
