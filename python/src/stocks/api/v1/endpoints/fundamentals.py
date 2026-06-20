"""Fundamentals API — fetch and return yfinance fundamental data per symbol."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from stocks.api.deps import get_db
from stocks.db.models import Symbol
from stocks.services.fundamentals_service import FundamentalsService

router = APIRouter(prefix="/fundamentals", tags=["Fundamentals"])


def _resolve_symbol(db: Session, raw: str):
    """Return (Symbol row, bare_name) for a symbol regardless of .NS suffix in DB."""
    clean = raw.replace(".NS", "").upper()
    # DB stores symbols with .NS suffix (e.g. RELIANCE.NS)
    row = db.scalar(select(Symbol).where(Symbol.symbol == f"{clean}.NS"))
    if row is None:
        row = db.scalar(select(Symbol).where(Symbol.symbol == clean))
    return row, clean


@router.get("/{symbol}")
def get_fundamentals(symbol: str, db: Session = Depends(get_db)):
    """Return cached fundamental data for a symbol. Fetches from yfinance if missing or stale."""
    sym_row, clean = _resolve_symbol(db, symbol)
    if sym_row is None:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol.upper()}' not found.")

    svc = FundamentalsService(db)
    data = svc.get_or_fetch(sym_row.id, clean)
    if data is None:
        raise HTTPException(status_code=503, detail="Fundamentals unavailable (yfinance returned no data).")
    return data


@router.post("/{symbol}/refresh")
def refresh_fundamentals(symbol: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Force-refresh fundamentals from yfinance for a single symbol."""
    sym_row, clean = _resolve_symbol(db, symbol)
    if sym_row is None:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol.upper()}' not found.")

    svc = FundamentalsService(db)
    data = svc.fetch_and_store(sym_row.id, clean)
    if data is None:
        raise HTTPException(status_code=503, detail="yfinance returned no data for this symbol.")
    return data


@router.post("/refresh-all")
def refresh_all_fundamentals(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Trigger background refresh of fundamentals for all active symbols (top 200)."""
    def _run():
        from stocks.services.fundamentals_service import FundamentalsService as _S
        from stocks.db.connection import DatabaseManager
        svc = _S(db)
        svc.refresh_all(limit=200)

    background_tasks.add_task(_run)
    return {"status": "started", "message": "Fundamentals refresh running in background for top 200 symbols."}
