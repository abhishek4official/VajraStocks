"""Screener presets API (V2.0 spec M4) — one-click tradable setups over the snapshot."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from stocks.api.deps import get_db
from stocks.db.models import ScreeningSnapshot
from stocks.services.quant.presets import get_preset, list_presets

router = APIRouter(prefix="/presets", tags=["Screener Presets"])

# Compact, useful display fields for a preset hit.
_DISPLAY = [
    "symbol", "company_name", "close_price", "rsi_14", "adx_14",
    "weinstein_stage", "rs_score_val", "composite_score", "ret_4w", "atr_pct",
]


@router.get("")
def get_presets():
    """List the available setup presets (name + description)."""
    return list_presets()


@router.get("/{name}")
def run_preset(name: str, limit: int = 200, db: Session = Depends(get_db)):
    """Return snapshot rows matching the named preset, best composite first."""
    try:
        predicate = get_preset(name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None

    hits = []
    for r in db.execute(select(ScreeningSnapshot)).scalars():
        row = {c.name: getattr(r, c.name) for c in r.__table__.columns}
        if predicate(row):
            hits.append({k: _coerce(row.get(k)) for k in _DISPLAY})

    hits.sort(key=lambda x: (x.get("composite_score") or 0), reverse=True)
    return {"preset": name, "count": len(hits), "rows": hits[:limit]}


def _coerce(v):
    # Numeric (Decimal) -> float for clean JSON; pass through everything else.
    try:
        from decimal import Decimal
        if isinstance(v, Decimal):
            return float(v)
    except Exception:
        pass
    return v
