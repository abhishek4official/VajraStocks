"""Cross-sectional ranking over the universe (V2.0 spec M4).

Turns the per-symbol factor component scores already stored on ScreeningSnapshot into
*relative* ranks: z-score each factor across the universe, combine into a weighted composite
z, and order by it. This is the relative-strength view the screener lacked.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from stocks.db.models import ScreeningSnapshot
from stocks.services.quant.factors import composite_z, percentile_rank, zscore

# Factor name -> ScreeningSnapshot column holding its per-symbol component score.
FACTOR_COLUMNS: dict[str, str] = {
    "trend": "trend_score_val",
    "momentum": "momentum_score_val",
    "rs": "rs_score_val",
    "volume": "volume_score_val",
    "cmf": "cmf_score_val",
    "breakout": "breakout_score_val",
}

DEFAULT_WEIGHTS: dict[str, float] = {
    "trend": 0.30, "momentum": 0.20, "rs": 0.20,
    "volume": 0.10, "cmf": 0.10, "breakout": 0.10,
}


def compute_ranking(
    session: Session,
    weights: dict[str, float] | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Rank the universe by a composite of cross-sectional factor z-scores (desc)."""
    weights = weights or DEFAULT_WEIGHTS
    rows = list(session.execute(select(ScreeningSnapshot)).scalars())

    factor_values: dict[str, dict[str, float | None]] = {f: {} for f in FACTOR_COLUMNS}
    for r in rows:
        for factor, col in FACTOR_COLUMNS.items():
            factor_values[factor][r.symbol] = getattr(r, col, None)

    factor_z = {f: zscore(vals) for f, vals in factor_values.items()}
    composite = composite_z(factor_z, weights)
    pct = percentile_rank(composite)

    ranked = sorted(
        (
            {
                "symbol": sym,
                "composite_z": z,
                "percentile": pct.get(sym),
                "factors": {f: factor_z[f].get(sym) for f in FACTOR_COLUMNS},
            }
            for sym, z in composite.items()
        ),
        key=lambda x: x["composite_z"],
        reverse=True,
    )
    return ranked[:limit] if limit else ranked
