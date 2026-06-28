import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from stocks.api.deps import get_db
from stocks.config import Config
from stocks.db.models import DailyPrice, Symbol
from stocks.services.market_structure import MarketStructureEngine

router = APIRouter(prefix="/charts", tags=["Charts"])

_mse = MarketStructureEngine(Config())


class CandleData(BaseModel):
    time: str  # YYYY-MM-DD
    open: float
    high: float
    low: float
    close: float
    volume: int


class RenkoData(BaseModel):
    brick_index: int
    time: str
    start_date: str
    open: float
    close: float
    direction: str
    brick_size: float


class LineBreakData(BaseModel):
    line_index: int
    time: str
    start_date: str
    open: float
    close: float
    direction: str


def _get_symbol_id_or_404(symbol: str, db: Session) -> int:
    from urllib.parse import unquote
    clean_sym = unquote(symbol).strip().upper()
    raw_sym = clean_sym.replace(".NS", "").replace(".BSE", "")
    if not clean_sym.endswith(".NS") and not clean_sym.startswith("^"):
        clean_sym = f"{raw_sym}.NS"

    symbol_id = db.scalar(
        select(Symbol.id).where(
            (Symbol.symbol == clean_sym) |
            (Symbol.symbol == raw_sym) |
            (Symbol.symbol == unquote(symbol).strip().upper())
        )
    )
    if not symbol_id:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' was not found in the database.")
    return symbol_id


def _price_df(symbol_id: int, db: Session) -> pd.DataFrame:
    rows = db.scalars(
        select(DailyPrice)
        .where(DailyPrice.symbol_id == symbol_id)
        .order_by(DailyPrice.trading_date.asc())
    ).all()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame([{
        "trading_date": r.trading_date,
        "open": float(r.open), "high": float(r.high),
        "low": float(r.low),  "close": float(r.close),
        "volume": int(r.volume),
    } for r in rows])
    df.set_index(pd.to_datetime(df["trading_date"]), inplace=True)
    return df


@router.get("/{symbol}/candles", response_model=list[CandleData])
def get_candlestick_data(symbol: str, db: Session = Depends(get_db)):
    symbol_id = _get_symbol_id_or_404(symbol, db)
    rows = db.scalars(
        select(DailyPrice).where(DailyPrice.symbol_id == symbol_id).order_by(DailyPrice.trading_date.asc())
    ).all()
    return [{"time": r.trading_date.strftime("%Y-%m-%d"), "open": float(r.open),
             "high": float(r.high), "low": float(r.low), "close": float(r.close),
             "volume": int(r.volume)} for r in rows]


@router.get("/{symbol}/heikin-ashi", response_model=list[CandleData])
def get_heikin_ashi_data(symbol: str, db: Session = Depends(get_db)):
    """Compute Heikin-Ashi on demand from daily prices (no stored table)."""
    symbol_id = _get_symbol_id_or_404(symbol, db)
    df = _price_df(symbol_id, db)
    if df.empty:
        return []
    candles = _mse.generate_heikin_ashi(df)
    return [{"time": c["trading_date"].strftime("%Y-%m-%d"), "open": round(c["open"], 4),
             "high": round(c["high"], 4), "low": round(c["low"], 4),
             "close": round(c["close"], 4), "volume": 0} for c in candles]


@router.get("/{symbol}/renko", response_model=list[RenkoData])
def get_renko_brick_data(symbol: str, db: Session = Depends(get_db)):
    """Compute Renko bricks on demand from daily prices (no stored table)."""
    symbol_id = _get_symbol_id_or_404(symbol, db)
    df = _price_df(symbol_id, db)
    if df.empty:
        return []
    bricks = _mse.generate_renko_bricks(df)
    return [{"brick_index": i + 1, "time": b["end_date"].strftime("%Y-%m-%d"),
             "start_date": b["start_date"].strftime("%Y-%m-%d"), "open": round(b["open"], 4),
             "close": round(b["close"], 4), "direction": b["direction"],
             "brick_size": round(b["brick_size"], 4)} for i, b in enumerate(bricks)]


@router.get("/{symbol}/line-break", response_model=list[LineBreakData])
def get_line_break_data(symbol: str, db: Session = Depends(get_db)):
    """Compute Line Break lines on demand from daily prices (no stored table)."""
    symbol_id = _get_symbol_id_or_404(symbol, db)
    df = _price_df(symbol_id, db)
    if df.empty:
        return []
    lines = _mse.generate_line_breaks(df)
    return [{"line_index": i + 1, "time": ln["end_date"].strftime("%Y-%m-%d"),
             "start_date": ln["start_date"].strftime("%Y-%m-%d"), "open": round(ln["open"], 4),
             "close": round(ln["close"], 4), "direction": ln["direction"]} for i, ln in enumerate(lines)]
