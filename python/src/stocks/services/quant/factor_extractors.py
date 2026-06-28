"""Raw academic factor extractors (V2.0 spec M6).

Pure functions over a close-price series, returning a single raw factor value per symbol
(or None when there isn't enough history). Cross-sectional z-scoring/ranking is done by
quant.factors over the universe of these raw values.

Factors:
- momentum: trailing return over ``lookback`` bars, skipping the most recent ``skip`` bars
  (the classic 12-1 style that avoids short-term reversal).
- low_volatility: negative stdev of daily returns over ``window`` (higher = calmer = better).
- high_proximity: last close / highest close over ``window`` (nearness to the 52-wk high).
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import pandas as pd


def _closes(values: Sequence[float]) -> list[float]:
    return [float(v) for v in values if v is not None]


def momentum(closes: Sequence[float], lookback: int = 126, skip: int = 21) -> float | None:
    """Trailing return over ``lookback`` bars ending ``skip`` bars ago."""
    c = _closes(closes)
    need = skip + lookback + 1
    if len(c) < need:
        return None
    recent = c[-1 - skip]
    past = c[-1 - skip - lookback]
    if past <= 0:
        return None
    return recent / past - 1.0


def low_volatility(closes: Sequence[float], window: int = 63) -> float | None:
    """Negative sample-stdev of daily returns over the last ``window`` returns."""
    c = _closes(closes)
    if len(c) < window + 1:
        return None
    rets = [c[i] / c[i - 1] - 1.0 for i in range(len(c) - window, len(c)) if c[i - 1] > 0]
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    variance = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return -math.sqrt(variance)


def high_proximity(closes: Sequence[float], window: int = 252) -> float | None:
    """Last close divided by the highest close over the last ``window`` bars (0–1)."""
    c = _closes(closes)
    if not c:
        return None
    recent = c[-window:]
    peak = max(recent)
    if peak <= 0:
        return None
    return c[-1] / peak


def symbol_factors(
    bars: pd.DataFrame,
    momentum_lookback: int = 126,
    momentum_skip: int = 21,
    vol_window: int = 63,
    high_window: int = 252,
) -> dict[str, float | None]:
    """Compute all raw factors for one symbol from its bars (needs a ``close`` column)."""
    closes = bars["close"].tolist() if "close" in bars.columns else []
    return {
        "momentum": momentum(closes, momentum_lookback, momentum_skip),
        "low_volatility": low_volatility(closes, vol_window),
        "high_proximity": high_proximity(closes, high_window),
    }
