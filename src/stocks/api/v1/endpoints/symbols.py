from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from stocks.api.deps import get_db
from stocks.db.models import Symbol, SymbolSyncState

router = APIRouter(prefix="/symbols", tags=["Symbols"])

# Pydantic Response Schema
class SymbolDetailResponse(BaseModel):
    id: int
    symbol: str
    company_name: str
    isin: str
    series: str
    is_active: bool
    last_successful_sync_date: Optional[str] = None
    last_attempt_status: Optional[str] = None
    last_error_message: Optional[str] = None

    class Config:
        from_attributes = True

@router.get("", response_model=List[SymbolDetailResponse])
def get_all_symbols(active_only: bool = True, db: Session = Depends(get_db)):
    """Queries all registered NSE stock symbols, including their latest sync state metadata."""
    stmt = select(Symbol, SymbolSyncState).outerjoin(
        SymbolSyncState, Symbol.id == SymbolSyncState.symbol_id
    )
    if active_only:
        stmt = stmt.where(Symbol.is_active == True)
        
    results = db.execute(stmt).all()
    
    symbols_list = []
    for sym, state in results:
        symbols_list.append({
            "id": sym.id,
            "symbol": sym.symbol,
            "company_name": sym.company_name,
            "isin": sym.isin,
            "series": sym.series,
            "is_active": sym.is_active,
            "last_successful_sync_date": state.last_successful_sync_date.strftime("%Y-%m-%d") if state and state.last_successful_sync_date else None,
            "last_attempt_status": state.last_attempt_status if state else None,
            "last_error_message": state.last_error_message if state else None
        })
    return symbols_list

@router.get("/{symbol}", response_model=SymbolDetailResponse)
def get_symbol_by_ticker(symbol: str, db: Session = Depends(get_db)):
    """Retrieves detailed profile metadata for a single requested stock ticker."""
    clean_sym = symbol.strip().upper()
    raw_sym = clean_sym.replace(".NS", "")
    
    stmt = select(Symbol, SymbolSyncState).outerjoin(
        SymbolSyncState, Symbol.id == SymbolSyncState.symbol_id
    ).where((Symbol.symbol == clean_sym) | (Symbol.symbol == raw_sym))
    
    result = db.execute(stmt).first()
    if not result:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' was not found in the database.")
        
    sym, state = result
    return {
        "id": sym.id,
        "symbol": sym.symbol,
        "company_name": sym.company_name,
        "isin": sym.isin,
        "series": sym.series,
        "is_active": sym.is_active,
        "last_successful_sync_date": state.last_successful_sync_date.strftime("%Y-%m-%d") if state and state.last_successful_sync_date else None,
        "last_attempt_status": state.last_attempt_status if state else None,
        "last_error_message": state.last_error_message if state else None
    }
