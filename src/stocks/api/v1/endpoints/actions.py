from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List, Optional
from pydantic import BaseModel

from stocks.api.deps import get_db
from stocks.db.models import Symbol, CorporateAction

router = APIRouter(prefix="/corporate-actions", tags=["Corporate Actions"])

# Pydantic Response Schema
class CorporateActionResponse(BaseModel):
    id: int
    symbol: str
    action_date: str  # YYYY-MM-DD
    action_type: str  # 'DIVIDEND', 'SPLIT', etc.
    value: float

    class Config:
        from_attributes = True

@router.get("", response_model=List[CorporateActionResponse])
def get_all_corporate_actions(limit: int = 100, db: Session = Depends(get_db)):
    """Retrieves EOD corporate events (splits, dividends) sorted chronologically."""
    stmt = select(CorporateAction, Symbol).join(
        Symbol, CorporateAction.symbol_id == Symbol.id
    ).order_by(CorporateAction.action_date.desc()).limit(limit)
    
    results = db.execute(stmt).all()
    
    return [
        {
            "id": act.id,
            "symbol": sym.symbol,
            "action_date": act.action_date.strftime("%Y-%m-%d"),
            "action_type": act.action_type,
            "value": float(act.value)
        }
        for act, sym in results
    ]

@router.get("/{symbol}", response_model=List[CorporateActionResponse])
def get_corporate_actions_by_symbol(symbol: str, db: Session = Depends(get_db)):
    """Retrieves all corporate event timeline records for a specific requested ticker."""
    clean_sym = symbol.strip().upper()
    raw_sym = clean_sym.replace(".NS", "")
    if not clean_sym.endswith(".NS") and not clean_sym.startswith("^"):
        clean_sym = f"{clean_sym}.NS"
        
    stmt = select(CorporateAction, Symbol).join(
        Symbol, CorporateAction.symbol_id == Symbol.id
    ).where((Symbol.symbol == clean_sym) | (Symbol.symbol == raw_sym)).order_by(CorporateAction.action_date.desc())
    
    results = db.execute(stmt).all()
    
    return [
        {
            "id": act.id,
            "symbol": sym.symbol,
            "action_date": act.action_date.strftime("%Y-%m-%d"),
            "action_type": act.action_type,
            "value": float(act.value)
        }
        for act, sym in results
    ]
