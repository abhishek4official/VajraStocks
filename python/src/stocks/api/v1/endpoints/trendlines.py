from urllib.parse import unquote

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from stocks.api.deps import get_db
from stocks.db.models import Symbol, SymbolTrendline

router = APIRouter(prefix="/trendlines", tags=["Trendlines"])


def _resolve_symbol(symbol: str, db: Session) -> Symbol:
    clean = unquote(symbol).strip().upper()
    raw = clean.replace(".NS", "").replace(".BSE", "")
    if not clean.endswith(".NS") and not clean.startswith("^"):
        clean = f"{raw}.NS"
    sym = db.scalar(select(Symbol).where((Symbol.symbol == clean) | (Symbol.symbol == raw)))
    if not sym:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found.")
    return sym


class TrendlineResponse(BaseModel):
    id: int
    symbol: str
    trendline_type: str
    anchor1_date: str
    anchor1_price: float
    anchor2_date: str
    anchor2_price: float
    touch_count: int
    score: float
    slope_pct_per_day: float
    is_broken: bool
    break_date: str | None

    model_config = {"from_attributes": True}


@router.post("/refresh-all")
def refresh_all_trendlines(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Trigger a background recompute of trendlines for all active symbols."""
    def _run():
        from stocks.services.trendline_service import TrendlineService
        TrendlineService(db).refresh_all()

    background_tasks.add_task(_run)
    return {"status": "started", "message": "Trendline refresh running in background."}


@router.get("/{symbol}", response_model=list[TrendlineResponse])
def get_trendlines(symbol: str, db: Session = Depends(get_db)):
    """Return the precomputed trendlines for a symbol."""
    sym = _resolve_symbol(symbol, db)
    rows = db.scalars(
        select(SymbolTrendline)
        .where(SymbolTrendline.symbol_id == sym.id)
        .order_by(SymbolTrendline.score.desc())
    ).all()
    return [
        TrendlineResponse(
            id=r.id,
            symbol=r.symbol,
            trendline_type=r.trendline_type,
            anchor1_date=r.anchor1_date.isoformat(),
            anchor1_price=float(r.anchor1_price),
            anchor2_date=r.anchor2_date.isoformat(),
            anchor2_price=float(r.anchor2_price),
            touch_count=r.touch_count,
            score=float(r.score),
            slope_pct_per_day=float(r.slope_pct_per_day),
            is_broken=r.is_broken,
            break_date=r.break_date.isoformat() if r.break_date else None,
        )
        for r in rows
    ]
