"""Cross-sectional factor ranking (V2.0 spec M4/M6).

Pure functions that turn per-symbol raw factor values into *relative* ranks across the
universe — z-scores, percentile ranks, and a weighted composite. The screener can then
rank stocks against each other (relative strength) instead of against absolute thresholds.

All functions take/return ``dict[symbol -> value]``; ``None`` inputs are treated as
"missing this factor" and excluded (so a name still ranks on the factors it does have).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import TypeVar

K = TypeVar("K")


def _present(values: Mapping[K, float | None]) -> dict[K, float]:
    return {k: float(v) for k, v in values.items() if v is not None}


def zscore(values: Mapping[K, float | None]) -> dict[K, float]:
    """Cross-sectional z-score (sample std). Constant or single-value inputs map to 0.0."""
    present = _present(values)
    n = len(present)
    if n == 0:
        return {}
    mean = sum(present.values()) / n
    if n < 2:
        return dict.fromkeys(present, 0.0)
    variance = sum((v - mean) ** 2 for v in present.values()) / (n - 1)
    if variance <= 0:
        return dict.fromkeys(present, 0.0)
    std = math.sqrt(variance)
    return {k: (v - mean) / std for k, v in present.items()}


def percentile_rank(values: Mapping[K, float | None]) -> dict[K, float]:
    """Percentile rank in [0, 100]: ``100 * (#strictly-less) / (n - 1)``. Ties share a rank."""
    present = _present(values)
    n = len(present)
    if n == 0:
        return {}
    if n == 1:
        return dict.fromkeys(present, 50.0)
    items = list(present.values())
    return {
        k: 100.0 * sum(1 for o in items if o < v) / (n - 1)
        for k, v in present.items()
    }


def composite_z(
    factor_scores: Mapping[str, Mapping[K, float]],
    weights: Mapping[str, float],
) -> dict[K, float]:
    """Weighted average of per-factor z-scores per symbol.

    Each symbol is scored over the factors it has values for, with weights renormalised to
    those present — so a missing factor reweights rather than penalises.
    """
    # Collect, per symbol, the (weight, score) pairs of the factors it has.
    per_symbol: dict[K, list[tuple[float, float]]] = {}
    for factor, scores in factor_scores.items():
        w = float(weights.get(factor, 0.0))
        if w == 0.0:
            continue
        for sym, score in scores.items():
            if score is None:
                continue
            per_symbol.setdefault(sym, []).append((w, float(score)))

    out: dict[K, float] = {}
    for sym, pairs in per_symbol.items():
        total_w = sum(w for w, _ in pairs)
        if total_w <= 0:
            continue
        out[sym] = sum(w * s for w, s in pairs) / total_w
    return out
