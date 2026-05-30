from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List, Optional
from pydantic import BaseModel

from stocks.api.deps import get_db
from stocks.db.models import Symbol, DailyIndicator

router = APIRouter(prefix="/indicators", tags=["Technical Indicators"])

# Pydantic Response Schema
class IndicatorRow(BaseModel):
    time: str  # trading_date YYYY-MM-DD
    rsi_14: Optional[float] = None
    atr_14: Optional[float] = None
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    ema_9: Optional[float] = None
    ema_21: Optional[float] = None
    macd_line: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None

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

@router.get("/{symbol}", response_model=List[IndicatorRow])
def get_indicators_history(symbol: str, db: Session = Depends(get_db)):
    """Retrieves full historical technical indicators (RSI, Moving Averages, MACD, Bollinger Bands) for a stock."""
    symbol_id = _get_symbol_id_or_404(symbol, db)
    
    rows = db.scalars(
        select(DailyIndicator)
        .where(DailyIndicator.symbol_id == symbol_id)
        .order_by(DailyIndicator.trading_date.asc())
    ).all()
    
    return [
        {
            "time": r.trading_date.strftime("%Y-%m-%d"),
            "rsi_14": r.rsi_14,
            "atr_14": r.atr_14,
            "sma_20": r.sma_20,
            "sma_50": r.sma_50,
            "sma_200": r.sma_200,
            "ema_9": r.ema_9,
            "ema_21": r.ema_21,
            "macd_line": r.macd_line,
            "macd_signal": r.macd_signal,
            "macd_histogram": r.macd_histogram,
            "bb_upper": r.bb_upper,
            "bb_middle": r.bb_middle,
            "bb_lower": r.bb_lower
        }
        for r in rows
    ]

@router.get("/{symbol}/{indicator}")
def get_specific_indicator_history(symbol: str, indicator: str, db: Session = Depends(get_db)):
    """Retrieves chronological EOD historical values for a single requested indicator name."""
    symbol_id = _get_symbol_id_or_404(symbol, db)
    ind_name = indicator.strip().lower()
    
    # Verify the requested indicator exists as an attribute
    if not hasattr(DailyIndicator, ind_name):
        raise HTTPException(
            status_code=400,
            detail=f"Indicator '{indicator}' is not valid. Choose from standard indicator attributes."
        )
        
    rows = db.scalars(
        select(DailyIndicator)
        .where(DailyIndicator.symbol_id == symbol_id)
        .order_by(DailyIndicator.trading_date.asc())
    ).all()
    
    return [
        {
            "time": r.trading_date.strftime("%Y-%m-%d"),
            "value": getattr(r, ind_name)
        }
        for r in rows
    ]
