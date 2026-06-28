"""Single-name "setup replay": BarStore -> signals -> engine (V2.0 spec M2 #1).

Reads (optionally back-adjusted) bars for one symbol from the columnar data plane, applies
a signal generator, and runs the deterministic engine. This is the swing trader's
"has this setup actually worked on this stock?" answer — over real, adjusted history.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Sequence
from typing import Any

import pandas as pd

from stocks.data.bar_store import BarStore
from stocks.services.quant.backtest.engine import BacktestConfig, BacktestResult, run_backtest
from stocks.services.quant.backtest.signals import get_signal

# A signal generator: bars -> (entries, exits), each aligned 1:1 with the bars.
SignalFn = Callable[[pd.DataFrame], tuple[Sequence[bool], Sequence[bool]]]


def run_symbol_backtest(
    store: BarStore,
    symbol: str,
    signal_fn: SignalFn | str,
    *,
    start: dt.date | None = None,
    end: dt.date | None = None,
    granularity: str = "1d",
    adjusted: bool = False,
    actions: Sequence[dict[str, Any]] | None = None,
    stop_pct: float | None = None,
    target_pct: float | None = None,
    config: BacktestConfig | None = None,
) -> BacktestResult:
    """Replay ``signal_fn`` against ``symbol``'s bars from the store and return the result.

    ``signal_fn`` may be a callable or the name of a registered signal (see signals.py).
    A symbol with no stored bars yields an empty result (no trades, empty equity curve) —
    never a fabricated outcome.
    """
    if isinstance(signal_fn, str):
        signal_fn = get_signal(signal_fn)

    bars = store.read_bars(
        symbol,
        start=start,
        end=end,
        granularity=granularity,
        adjusted=adjusted,
        actions=actions,
    )
    entries, exits = signal_fn(bars)
    return run_backtest(
        bars,
        entries,
        stop_pct=stop_pct,
        target_pct=target_pct,
        exits=exits,
        config=config,
    )
