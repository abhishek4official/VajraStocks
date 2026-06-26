"""Tests for single-name setup signal generators (V2.0 spec M2 #1)."""

import datetime as dt

import pandas as pd

from stocks.services.quant.backtest.signals import sma_crossover_signals

D = dt.date


def _bars(closes):
    return pd.DataFrame(
        [
            {"trading_date": D(2023, 1, 1) + dt.timedelta(days=i), "open": c, "high": c, "low": c, "close": c}
            for i, c in enumerate(closes)
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
