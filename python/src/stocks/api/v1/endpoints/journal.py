"""Trade Journal API (V2.0 spec M3).

Log trades, close them, and get a per-setup auto-review. Computed fields (realized P&L,
return, R-multiple) are derived on read from the logged values — never stored fabricated.
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from stocks.api.deps import get_db
from stocks.db.models import JournalTrade
from stocks.services.journal.analytics import (
    ClosedTrade,
    r_multiple,
    realized_pnl,
    return_pct,
)
from stocks.services.journal.repository import JournalRepository

router = APIRouter(prefix="/journal", tags=["Trade Journal"])


# ── Schemas ───────────────────────────────────────────────────────────────────
class TradeIn(BaseModel):
    symbol: str
    entry_date: dt.date
    entry_price: float
    qty: float
    setup: str = ""
    side: str = "LONG"
    stop_price: float | None = None
    target_price: float | None = None
    thesis: str | None = None
    exit_date: dt.date | None = None
    exit_price: float | None = None
    fees: float = 0.0


class CloseIn(BaseModel):
    exit_date: dt.date
    exit_price: float
    fees: float | None = None
    mistake_tags: str | None = None


class TradeOut(BaseModel):
    id: int
    symbol: str
    setup: str
    side: str
    status: str
    entry_date: str
    entry_price: float
    qty: float
    stop_price: float | None
    target_price: float | None
    exit_date: str | None
    exit_price: float | None
    fees: float
    thesis: str | None
    mistake_tags: str | None
    pnl: float | None
    return_pct: float | None
    r_multiple: float | None


class SetupStatsOut(BaseModel):
    setup: str
    trades: int
    wins: int
    win_rate: float
    total_pnl: float
    avg_pnl: float
    avg_r: float
    expectancy_r: float


# ── helpers ───────────────────────────────────────────────────────────────────
def _out(t: JournalTrade) -> TradeOut:
    pnl = ret = rr = None
    if t.status == "CLOSED" and t.exit_price is not None:
        ct = ClosedTrade(
            setup=t.setup, side=t.side, entry=float(t.entry_price),
            stop=float(t.stop_price) if t.stop_price is not None else float(t.entry_price),
            exit=float(t.exit_price), qty=float(t.qty), fees=float(t.fees or 0.0),
        )
        pnl, ret = realized_pnl(ct), return_pct(ct)
        rr = r_multiple(ct) if t.stop_price is not None else None
    return TradeOut(
        id=t.id, symbol=t.symbol, setup=t.setup, side=t.side, status=t.status,
        entry_date=t.entry_date.isoformat(), entry_price=float(t.entry_price), qty=float(t.qty),
        stop_price=t.stop_price, target_price=t.target_price,
        exit_date=t.exit_date.isoformat() if t.exit_date else None,
        exit_price=t.exit_price, fees=float(t.fees or 0.0),
        thesis=t.thesis, mistake_tags=t.mistake_tags,
        pnl=pnl, return_pct=ret, r_multiple=rr,
    )


# ── routes ────────────────────────────────────────────────────────────────────
@router.post("/trades", response_model=TradeOut)
def log_trade(body: TradeIn, db: Session = Depends(get_db)):
    """Log a trade (CLOSED if an exit is supplied, else OPEN)."""
    t = JournalRepository(db).log_trade(**body.model_dump())
    return _out(t)


@router.post("/trades/{trade_id}/close", response_model=TradeOut)
def close_trade(trade_id: int, body: CloseIn, db: Session = Depends(get_db)):
    """Record the exit for an open trade."""
    try:
        t = JournalRepository(db).close_trade(trade_id, **body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return _out(t)


@router.get("/trades", response_model=list[TradeOut])
def list_trades(symbol: str | None = None, status: str | None = None, db: Session = Depends(get_db)):
    """List journal trades, newest first (optional symbol/status filters)."""
    return [_out(t) for t in JournalRepository(db).list_trades(symbol=symbol, status=status)]


@router.get("/trades/{trade_id}", response_model=TradeOut)
def get_trade(trade_id: int, db: Session = Depends(get_db)):
    t = JournalRepository(db).get(trade_id)
    if t is None:
        raise HTTPException(status_code=404, detail=f"No journal trade {trade_id}")
    return _out(t)


@router.delete("/trades/{trade_id}")
def delete_trade(trade_id: int, db: Session = Depends(get_db)):
    if not JournalRepository(db).delete(trade_id):
        raise HTTPException(status_code=404, detail=f"No journal trade {trade_id}")
    return {"deleted": trade_id}


@router.get("/review", response_model=list[SetupStatsOut])
def review(db: Session = Depends(get_db)):
    """Per-setup auto-review over closed trades (win rate / expectancy-in-R / P&L)."""
    review = JournalRepository(db).review()
    return [
        SetupStatsOut(
            setup=s.setup, trades=s.trades, wins=s.wins, win_rate=s.win_rate,
            total_pnl=s.total_pnl, avg_pnl=s.avg_pnl, avg_r=s.avg_r, expectancy_r=s.expectancy_r,
        )
        for s in sorted(review.values(), key=lambda x: x.total_pnl, reverse=True)
    ]
