"""Cross-sectional ranking API (V2.0 spec M4) — relative-strength ranking of the universe."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from stocks.api.deps import get_bar_store, get_db
from stocks.data.bar_store import BarStore
from stocks.services.quant.factor_ranking import rank_symbols_by_factors
from stocks.services.quant.ranking import DEFAULT_WEIGHTS, FACTOR_COLUMNS, compute_ranking

router = APIRouter(prefix="/ranking", tags=["Ranking"])


class RankRow(BaseModel):
    symbol: str
    composite_z: float
    percentile: float | None
    factors: dict[str, float | None]


@router.get("", response_model=list[RankRow])
def get_ranking(limit: int = 100, db: Session = Depends(get_db)):
    """Rank the universe by a composite of cross-sectional factor z-scores (relative strength)."""
    return compute_ranking(db, limit=limit)


@router.get("/factors")
def get_factors():
    """The factors used in the composite and their default weights."""
    return {"factors": list(FACTOR_COLUMNS), "weights": DEFAULT_WEIGHTS}


class ByFactorsRequest(BaseModel):
    symbols: list[str]
    weights: dict[str, float] | None = None
    adjusted: bool = False


@router.post("/by-factors")
def rank_by_factors(
    body: ByFactorsRequest,
    store: BarStore = Depends(get_bar_store),
) -> list[dict[str, Any]]:
    """Rank a provided symbol set by raw academic factors (momentum / low-vol / 52wk-high)."""
    syms = [s if s.endswith(".NS") or s.startswith("^") else f"{s.strip().upper()}.NS" for s in body.symbols]
    return rank_symbols_by_factors(store, syms, weights=body.weights, adjusted=body.adjusted)
