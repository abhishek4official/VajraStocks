from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from stocks.api.deps import get_db, db_manager, config
from stocks.db.models import SyncJob, SymbolSyncState, Symbol
from stocks.services.sync_engine import SyncEngine
from stocks.services.database import DatabaseService

router = APIRouter(prefix="/sync", tags=["Synchronization Monitoring"])

# Pydantic Response Schemas
class SyncJobResponse(BaseModel):
    id: int
    run_id: str
    start_time: str
    end_time: Optional[str] = None
    status: str
    total_symbols: int
    processed_symbols: int
    failed_symbols: int
    records_inserted: int
    error_summary: Optional[str] = None

    class Config:
        from_attributes = True

class SymbolSyncStatusResponse(BaseModel):
    symbol: str
    last_successful_sync_date: str
    last_attempt_status: str
    last_error_message: Optional[str] = None

def _execute_async_sync(symbols: Optional[List[str]] = None):
    """Worker task executed in a background thread."""
    engine = SyncEngine(config, db_manager)
    try:
        engine.run_sync(specific_symbols=symbols)
    except Exception as e:
        # Logged internally inside SyncEngine, catch to prevent crash
        pass

def _execute_async_recalculate(symbol_ticker: Optional[str] = None):
    """Worker task to recalculate indicators and market structures for symbols in the background."""
    from stocks.db.models import DailyIndicator, DailyHeikinAshi, RenkoBrick, LineBreakLine
    from sqlalchemy import delete
    
    session = db_manager.get_session()
    db_service = DatabaseService(config, session)
    sync_engine = SyncEngine(config, db_manager)
    
    try:
        active_symbols = db_service.get_active_symbols()
        if symbol_ticker:
            clean_sym = symbol_ticker.strip().upper()
            if not clean_sym.endswith(".NS") and not clean_sym.startswith("^"):
                clean_sym = f"{clean_sym}.NS"
            active_symbols = [s for s in active_symbols if s.symbol == clean_sym]
            
        for symbol_obj in active_symbols:
            # Clear all existing derived data to guarantee clean cold start calculations
            session.execute(delete(DailyIndicator).where(DailyIndicator.symbol_id == symbol_obj.id))
            session.execute(delete(DailyHeikinAshi).where(DailyHeikinAshi.symbol_id == symbol_obj.id))
            session.execute(delete(RenkoBrick).where(RenkoBrick.symbol_id == symbol_obj.id))
            session.execute(delete(LineBreakLine).where(LineBreakLine.symbol_id == symbol_obj.id))
            session.commit()
            
            # Fetch all prices in DB
            prices = db_service.get_prices_for_window(symbol_obj.id, datetime.strptime("1970-01-01", "%Y-%m-%d").date())
            if prices:
                sync_engine.calculate_and_save_derived_data(db_service, symbol_obj, prices)
                
        # Rebuild snapshots
        from stocks.services.screening import ScreeningService
        screening_service = ScreeningService(config, session)
        screening_service.refresh_all_snapshots()
    except Exception as e:
        pass
    finally:
        session.close()

@router.post("/full")
def run_full_synchronization(background_tasks: BackgroundTasks):
    """Triggers an asynchronous full EOD downloader and incremental sync run in the background."""
    background_tasks.add_task(_execute_async_sync)
    return {"message": "Full synchronization job triggered successfully in the background."}

@router.post("/symbol/{symbol}")
def run_symbol_synchronization(symbol: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Triggers an asynchronous sync run for a single requested symbol in the background."""
    # Verify symbol exists
    clean_sym = symbol.strip().upper()
    raw_sym = clean_sym.replace(".NS", "")
    if not clean_sym.endswith(".NS") and not clean_sym.startswith("^"):
        clean_sym = f"{clean_sym}.NS"
        
    exist = db.scalar(select(Symbol.id).where((Symbol.symbol == clean_sym) | (Symbol.symbol == raw_sym)))
    if not exist:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' is not registered.")
        
    background_tasks.add_task(_execute_async_sync, [symbol])
    return {"message": f"Sync job for symbol '{symbol}' triggered successfully in the background."}

@router.post("/recalculate")
def run_derived_recalculations(background_tasks: BackgroundTasks, symbol: Optional[str] = None):
    """Triggers a background manual rebuild of technical indicators, HA, Renko, and Line Break structures."""
    background_tasks.add_task(_execute_async_recalculate, symbol)
    return {"message": "Derived data recalculation job triggered successfully in the background."}

@router.get("/jobs", response_model=List[SyncJobResponse])
def get_sync_jobs_history(limit: int = 10, db: Session = Depends(get_db)):
    """Retrieves EOD sync jobs history records."""
    jobs = db.scalars(
        select(SyncJob).order_by(SyncJob.start_time.desc()).limit(limit)
    ).all()
    
    return [
        {
            "id": r.id,
            "run_id": r.run_id,
            "start_time": r.start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": r.end_time.strftime("%Y-%m-%d %H:%M:%S") if r.end_time else None,
            "status": r.status,
            "total_symbols": r.total_symbols,
            "processed_symbols": r.processed_symbols,
            "failed_symbols": r.failed_symbols,
            "records_inserted": r.records_inserted,
            "error_summary": r.error_summary
        }
        for r in jobs
    ]

@router.get("/status", response_model=List[SymbolSyncStatusResponse])
def get_symbols_sync_status(status_filter: Optional[str] = None, db: Session = Depends(get_db)):
    """Retrieves current synchronization health status per stock symbol."""
    stmt = select(SymbolSyncState, Symbol).join(
        Symbol, SymbolSyncState.symbol_id == Symbol.id
    )
    if status_filter:
        stmt = stmt.where(SymbolSyncState.last_attempt_status == status_filter.strip().upper())
        
    results = db.execute(stmt).all()
    return [
        {
            "symbol": sym.symbol,
            "last_successful_sync_date": state.last_successful_sync_date.strftime("%Y-%m-%d"),
            "last_attempt_status": state.last_attempt_status,
            "last_error_message": state.last_error_message
        }
        for state, sym in results
    ]
