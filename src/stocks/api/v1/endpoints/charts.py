from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List, Optional
from pydantic import BaseModel
from datetime import date

from stocks.api.deps import get_db
from stocks.db.models import Symbol, DailyPrice, DailyHeikinAshi, RenkoBrick, LineBreakLine

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
    """Helper to query the symbol_id or raise a 404 error if missing."""
    clean_sym = symbol.strip().upper()
    raw_sym = clean_sym.replace(".NS", "")
    if not clean_sym.endswith(".NS") and not clean_sym.startswith("^"):
        clean_sym = f"{clean_sym}.NS"
        
    symbol_id = db.scalar(
        select(Symbol.id).where((Symbol.symbol == clean_sym) | (Symbol.symbol == raw_sym))
    )
    if not symbol_id:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' was not found in the database.")
    return symbol_id

@router.get("/{symbol}/candles", response_model=List[CandleData])
def get_candlestick_data(symbol: str, db: Session = Depends(get_db)):
    """Retrieves standard daily EOD price candlestick data points sorted chronologically."""
    symbol_id = _get_symbol_id_or_404(symbol, db)
    
    rows = db.scalars(
        select(DailyPrice)
        .where(DailyPrice.symbol_id == symbol_id)
        .order_by(DailyPrice.trading_date.asc())
    ).all()
    
    return [
        {
            "time": r.trading_date.strftime("%Y-%m-%d"),
            "open": float(r.open),
            "high": float(r.high),
            "low": float(r.low),
            "close": float(r.close),
            "volume": int(r.volume)
        }
        for r in rows
    ]

@router.get("/{symbol}/heikin-ashi", response_model=List[CandleData])
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
            "volume": 0  # HA candles do not carry individual volume records
        }
        for r in rows
    ]

@router.get("/{symbol}/renko", response_model=List[RenkoData])
def get_renko_brick_data(symbol: str, db: Session = Depends(get_db)):
    """Retrieves path-dependent Renko brick sequences including start/end dates and directions."""
    symbol_id = _get_symbol_id_or_404(symbol, db)
    
    rows = db.scalars(
        select(RenkoBrick)
        .where(RenkoBrick.symbol_id == symbol_id)
        .order_by(RenkoBrick.brick_index.asc())
    ).all()
    
    return [
        {
            "brick_index": r.brick_index,
            "time": r.end_date.strftime("%Y-%m-%d"),
            "start_date": r.start_date.strftime("%Y-%m-%d"),
            "open": float(r.open),
            "close": float(r.close),
            "direction": r.direction,
            "brick_size": float(r.brick_size)
        }
        for r in rows
    ]

@router.get("/{symbol}/line-break", response_model=List[LineBreakData])
def get_line_break_data(symbol: str, db: Session = Depends(get_db)):
    """Retrieves path-dependent N-Line Break sequence structures including start/end dates."""
    symbol_id = _get_symbol_id_or_404(symbol, db)
    
    rows = db.scalars(
        select(LineBreakLine)
        .where(LineBreakLine.symbol_id == symbol_id)
        .order_by(LineBreakLine.line_index.asc())
    ).all()
    
    return [
        {
            "line_index": r.line_index,
            "time": r.end_date.strftime("%Y-%m-%d"),
            "start_date": r.start_date.strftime("%Y-%m-%d"),
            "open": float(r.open),
            "close": float(r.close),
            "direction": r.direction
        }
        for r in rows
    ]
