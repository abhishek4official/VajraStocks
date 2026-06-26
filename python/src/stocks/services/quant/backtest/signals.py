"""Single-name setup signal generators for the backtest engine (V2.0 spec M2 #1).

A signal generator takes a bars DataFrame (with a ``close`` column) and returns
``(entries, exits)`` — two equal-length boolean lists aligned 1:1 with the bars, ready to
feed ``run_backtest``. Pure functions, no I/O.
"""

from __future__ import annotations

import pandas as pd


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
