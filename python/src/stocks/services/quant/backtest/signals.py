"""Single-name setup signal generators for the backtest engine (V2.0 spec M2 #1).

A signal generator takes a bars DataFrame (with a ``close`` column) and returns
``(entries, exits)`` — two equal-length boolean lists aligned 1:1 with the bars, ready to
feed ``run_backtest``. Pure functions, no I/O.
"""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd

# A signal generator: bars -> (entries, exits), each aligned 1:1 with the bars.
SignalFn = Callable[[pd.DataFrame], "tuple[list[bool], list[bool]]"]


def sma_crossover_signals(
    bars: pd.DataFrame,
    fast: int = 20,
    slow: int = 50,
) -> tuple[list[bool], list[bool]]:
    """Classic SMA crossover: enter when the fast SMA crosses above the slow SMA, exit on
    the cross below. Bars without enough history (SMA undefined) produce no signal.
    """
    if bars.empty:
        return [], []

    close = bars["close"].astype(float)
    fast_ma = close.rolling(fast).mean()
    slow_ma = close.rolling(slow).mean()

    above = fast_ma > slow_ma
    below = fast_ma < slow_ma
    cross_up = above & ~above.shift(1, fill_value=False)
    cross_down = below & ~below.shift(1, fill_value=False)

    return cross_up.tolist(), cross_down.tolist()


def breakout_signals(
    bars: pd.DataFrame,
    entry_lookback: int = 20,
    exit_lookback: int = 10,
) -> tuple[list[bool], list[bool]]:
    """Donchian channel breakout: enter when close exceeds the highest high of the prior
    ``entry_lookback`` bars; exit when close falls below the lowest low of the prior
    ``exit_lookback`` bars. The prior window excludes the current bar (no lookahead).
    """
    if bars.empty:
        return [], []

    close = bars["close"].astype(float)
    prior_high = bars["high"].astype(float).rolling(entry_lookback).max().shift(1)
    prior_low = bars["low"].astype(float).rolling(exit_lookback).min().shift(1)

    entries = (close > prior_high).fillna(False)
    exits = (close < prior_low).fillna(False)
    return entries.tolist(), exits.tolist()


# ── signal registry ──────────────────────────────────────────────────────────
# Maps a setup name to a default-parameter signal generator, so backtests/screeners can
# reference setups by name. Call the underlying function directly for custom parameters.

_SIGNAL_REGISTRY: dict[str, SignalFn] = {
    "sma_crossover": sma_crossover_signals,
    "breakout": breakout_signals,
}


def register_signal(name: str, fn: SignalFn) -> None:
    """Register a named signal generator (used by built-ins and plugins)."""
    _SIGNAL_REGISTRY[name] = fn


def get_signal(name: str) -> SignalFn:
    """Return the signal generator registered under ``name`` (ValueError if unknown)."""
    try:
        return _SIGNAL_REGISTRY[name]
    except KeyError:
        raise ValueError(
            f"Unknown signal '{name}'. Known signals: {', '.join(list_signals())}"
        ) from None


def list_signals() -> list[str]:
    """Return the sorted names of all registered signal generators."""
    return sorted(_SIGNAL_REGISTRY)
