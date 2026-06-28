"""Rank a symbol set by raw academic factors (V2.0 spec M6).

Reads each symbol's bars from the BarStore, computes raw momentum / low-volatility /
52-wk-high factors, z-scores them across the provided set, and orders by a weighted
composite. Bounded by the caller's symbol list (e.g. a watchlist), so it stays fast.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from stocks.data.bar_store import BarStore
from stocks.services.quant.factor_extractors import symbol_factors
from stocks.services.quant.factors import composite_z, percentile_rank, zscore

FACTORS = ("momentum", "low_volatility", "high_proximity")
DEFAULT_WEIGHTS = {"momentum": 0.5, "low_volatility": 0.2, "high_proximity": 0.3}


def rank_symbols_by_factors(
    store: BarStore,
    symbols: Sequence[str],
    *,
    weights: dict[str, float] | None = None,
    adjusted: bool = False,
    momentum_lookback: int = 126,
    momentum_skip: int = 21,
    vol_window: int = 63,
    high_window: int = 252,
) -> list[dict[str, Any]]:
    """Rank ``symbols`` by a composite of cross-sectional raw-factor z-scores (desc)."""
    raw: dict[str, dict[str, float | None]] = {f: {} for f in FACTORS}
    for sym in symbols:
        bars = store.read_bars(sym, adjusted=adjusted)
        if bars.empty:
            continue
        f = symbol_factors(bars, momentum_lookback, momentum_skip, vol_window, high_window)
        for name in FACTORS:
            raw[name][sym] = f[name]

    factor_z = {name: zscore(vals) for name, vals in raw.items()}
    composite = composite_z(factor_z, weights or DEFAULT_WEIGHTS)
    pct = percentile_rank(composite)

    return sorted(
        (
            {
                "symbol": sym,
                "composite_z": z,
                "percentile": pct.get(sym),
                "factors": {name: factor_z[name].get(sym) for name in FACTORS},
                "raw": {name: raw[name].get(sym) for name in FACTORS},
            }
            for sym, z in composite.items()
        ),
        key=lambda x: x["composite_z"],
        reverse=True,
    )
