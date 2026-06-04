from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from stocks.api.deps import get_db
from stocks.db.models import DailyHeikinAshi, DailyPrice, LineBreakLine, RenkoBrick, Symbol

router = APIRouter(prefix="/charts", tags=["Charts"])


# Pydantic Schemas for JSON response validation
class CandleData(BaseModel):
    time: str  # YYYY-MM-DD
    open: float
    high: float
    low: float
    close: float
    volume: int


class RenkoData(BaseModel):
    brick_index: int
    time: str  # end_date YYYY-MM-DD
    start_date: str
    open: float
    close: float
    direction: str  # 'UP', 'DOWN'
    brick_size: float


class LineBreakData(BaseModel):
    line_index: int
    time: str  # end_date YYYY-MM-DD
    start_date: str
    open: float
    close: float
    direction: str  # 'UP', 'DOWN'


def _get_symbol_id_or_404(symbol: str, db: Session) -> int:
    """
    Resolves a symbol string to a DB id, handling all common formats:
      RELIANCE  →  RELIANCE.NS
      RELIANCE.NS  →  RELIANCE.NS
      ^NSEI  →  ^NSEI  (index, no .NS suffix)
      %5ENSEI (URL-encoded ^)  →  ^NSEI  (FastAPI decodes automatically,
                                          but we guard against edge cases)
    """
    from urllib.parse import unquote
    clean_sym = unquote(symbol).strip().upper()   # decode %5E → ^ just in case
    raw_sym = clean_sym.replace(".NS", "").replace(".BSE", "")
    if not clean_sym.endswith(".NS") and not clean_sym.startswith("^"):
        clean_sym = f"{raw_sym}.NS"

    symbol_id = db.scalar(
        select(Symbol.id).where(
            (Symbol.symbol == clean_sym) |
            (Symbol.symbol == raw_sym) |
            (Symbol.symbol == unquote(symbol).strip().upper())   # exact match fallback
        )
    )
    if not symbol_id:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' was not found in the database.")
    return symbol_id


@router.get("/{symbol}/candles", response_model=list[CandleData])
def get_candlestick_data(symbol: str, db: Session = Depends(get_db)):
    """Retrieves standard daily EOD price candlestick data points sorted chronologically."""
    symbol_id = _get_symbol_id_or_404(symbol, db)

    rows = db.scalars(
        select(DailyPrice).where(DailyPrice.symbol_id == symbol_id).order_by(DailyPrice.trading_date.asc())
    ).all()

    return [
        {
            "time": r.trading_date.strftime("%Y-%m-%d"),
            "open": float(r.open),
            "high": float(r.high),
            "low": float(r.low),
            "close": float(r.close),
            "volume": int(r.volume),
        }
        for r in rows
    ]


@router.get("/{symbol}/heikin-ashi", response_model=list[CandleData])
def get_heikin_ashi_data(symbol: str, db: Session = Depends(get_db)):
    """Retrieves computed daily Heikin-Ashi candlestick data points sorted chronologically."""
    symbol_id = _get_symbol_id_or_404(symbol, db)

    rows = db.scalars(
        select(DailyHeikinAshi)
        .where(DailyHeikinAshi.symbol_id == symbol_id)
        .order_by(DailyHeikinAshi.trading_date.asc())
    ).all()

    return [
        {
            "time": r.trading_date.strftime("%Y-%m-%d"),
            "open": float(r.open),
            "high": float(r.high),
            "low": float(r.low),
            "close": float(r.close),
            "volume": 0,  # HA candles do not carry individual volume records
        }
        for r in rows
    ]


@router.get("/{symbol}/renko", response_model=list[RenkoData])
def get_renko_brick_data(symbol: str, db: Session = Depends(get_db)):
    """Retrieves path-dependent Renko brick sequences including start/end dates and directions."""
    symbol_id = _get_symbol_id_or_404(symbol, db)

    rows = db.scalars(
        select(RenkoBrick).where(RenkoBrick.symbol_id == symbol_id).order_by(RenkoBrick.brick_index.asc())
    ).all()

    return [
        {
            "brick_index": r.brick_index,
            "time": r.end_date.strftime("%Y-%m-%d"),
            "start_date": r.start_date.strftime("%Y-%m-%d"),
            "open": float(r.open),
            "close": float(r.close),
            "direction": r.direction,
            "brick_size": float(r.brick_size),
        }
        for r in rows
    ]


@router.get("/{symbol}/line-break", response_model=list[LineBreakData])
def get_line_break_data(symbol: str, db: Session = Depends(get_db)):
    """Retrieves path-dependent N-Line Break sequence structures including start/end dates."""
    symbol_id = _get_symbol_id_or_404(symbol, db)

    rows = db.scalars(
        select(LineBreakLine).where(LineBreakLine.symbol_id == symbol_id).order_by(LineBreakLine.line_index.asc())
    ).all()

    return [
        {
            "line_index": r.line_index,
            "time": r.end_date.strftime("%Y-%m-%d"),
            "start_date": r.start_date.strftime("%Y-%m-%d"),
            "open": float(r.open),
            "close": float(r.close),
            "direction": r.direction,
        }
        for r in rows
    ]
