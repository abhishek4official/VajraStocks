from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from stocks.api.deps import get_config, get_db
from stocks.db.models import Symbol, SymbolSyncState, SyncJob
from stocks.services.database import DatabaseService
from stocks.services.sync_engine import SyncEngine

router = APIRouter(prefix="/sync", tags=["Synchronization Monitoring"])


# ── Pydantic schemas ───────────────────────────────────────────────────────────

class SyncJobResponse(BaseModel):
    id: int
    run_id: str
    start_time: str
    end_time: str | None = None
    status: str
    total_symbols: int
    processed_symbols: int
    failed_symbols: int
    records_inserted: int
    error_summary: str | None = None

    class Config:
        from_attributes = True


class SymbolSyncStatusResponse(BaseModel):
    symbol: str
    last_successful_sync_date: str
    last_attempt_status: str
    last_error_message: str | None = None


# ── Background workers ────────────────────────────────────────────────────────

def _execute_async_sync(request: Request, symbols: list[str] | None = None):
    """Runs a full or partial sync using config values read from the DB."""
    cfg = get_config(request)
    db_manager = request.app.state.db_manager
    engine = SyncEngine(cfg, db_manager)
    try:
        engine.run_sync(specific_symbols=symbols)
    except Exception:
        pass


def _execute_async_recalculate(request: Request, symbol_ticker: str | None = None):
    """Recalculates all derived data (indicators, HA, Renko, snapshots) from raw prices."""
    from sqlalchemy import delete
    from stocks.db.models import DailyHeikinAshi, DailyIndicator, LineBreakLine, RenkoBrick

    cfg = get_config(request)
    db_manager = request.app.state.db_manager
    session = db_manager.get_session()
    db_service = DatabaseService(cfg, session)
    sync_engine = SyncEngine(cfg, db_manager)

    try:
        request.app.state.cancel_recalculate = False
        active_symbols = db_service.get_active_symbols()
        if symbol_ticker:
            clean_sym = symbol_ticker.strip().upper()
            if not clean_sym.endswith(".NS") and not clean_sym.startswith("^"):
                clean_sym = f"{clean_sym}.NS"
            active_symbols = [s for s in active_symbols if s.symbol == clean_sym]

        for symbol_obj in active_symbols:
            if getattr(request.app.state, "cancel_recalculate", False):
                from loguru import logger
                logger.warning("Recalculation cancelled by user request.")
                break
            session.execute(delete(DailyIndicator).where(DailyIndicator.symbol_id == symbol_obj.id))
            session.execute(delete(DailyHeikinAshi).where(DailyHeikinAshi.symbol_id == symbol_obj.id))
            session.execute(delete(RenkoBrick).where(RenkoBrick.symbol_id == symbol_obj.id))
            session.execute(delete(LineBreakLine).where(LineBreakLine.symbol_id == symbol_obj.id))
            session.commit()

            prices = db_service.get_prices_for_window(symbol_obj.id, datetime.strptime("1970-01-01", "%Y-%m-%d").date())
            if prices:
                sync_engine.calculate_and_save_derived_data(db_service, symbol_obj, prices)

        from stocks.services.screening import ScreeningService
        ScreeningService(cfg, session).refresh_all_snapshots()
    except Exception:
        pass
    finally:
        session.close()


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/full")
def run_full_synchronization(request: Request, background_tasks: BackgroundTasks):
    """Triggers an asynchronous full EOD sync in the background."""
    background_tasks.add_task(_execute_async_sync, request, None)
    return {"message": "Full synchronization job triggered successfully in the background."}


@router.post("/symbol/{symbol}")
def run_symbol_synchronization(symbol: str, request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Triggers an asynchronous sync for a single symbol."""
    clean_sym = symbol.strip().upper()
    raw_sym = clean_sym.replace(".NS", "")
    if not clean_sym.endswith(".NS") and not clean_sym.startswith("^"):
        clean_sym = f"{clean_sym}.NS"
    exist = db.scalar(select(Symbol.id).where((Symbol.symbol == clean_sym) | (Symbol.symbol == raw_sym)))
    if not exist:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' is not registered.")
    background_tasks.add_task(_execute_async_sync, request, [symbol])
    return {"message": f"Sync job for '{symbol}' triggered successfully in the background."}


@router.post("/recalculate")
def run_derived_recalculations(request: Request, background_tasks: BackgroundTasks, symbol: str | None = None):
    """Triggers a background rebuild of technical indicators and market structures."""
    background_tasks.add_task(_execute_async_recalculate, request, symbol)
    return {"message": "Derived data recalculation job triggered successfully in the background."}


@router.get("/jobs", response_model=list[SyncJobResponse])
def get_sync_jobs_history(limit: int = 10, db: Session = Depends(get_db)):
    """Retrieves EOD sync job history."""
    jobs = db.scalars(select(SyncJob).order_by(SyncJob.start_time.desc()).limit(limit)).all()
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
            "error_summary": r.error_summary,
        }
        for r in jobs
    ]


@router.get("/status", response_model=list[SymbolSyncStatusResponse])
def get_symbols_sync_status(status_filter: str | None = None, db: Session = Depends(get_db)):
    """Retrieves per-symbol sync health status."""
    stmt = select(SymbolSyncState, Symbol).join(Symbol, SymbolSyncState.symbol_id == Symbol.id)
    if status_filter:
        stmt = stmt.where(SymbolSyncState.last_attempt_status == status_filter.strip().upper())
    results = db.execute(stmt).all()
    return [
        {
            "symbol": sym.symbol,
            "last_successful_sync_date": state.last_successful_sync_date.strftime("%Y-%m-%d"),
            "last_attempt_status": state.last_attempt_status,
            "last_error_message": state.last_error_message,
        }
        for state, sym in results
    ]


@router.post("/cancel")
def cancel_active_sync_jobs(request: Request, db: Session = Depends(get_db)):
    """Cancels any currently running sync or recalculation jobs."""
    # 1. Set recalculate cancellation flag
    request.app.state.cancel_recalculate = True

    # 2. Mark active database sync jobs as CANCELLED
    running_jobs = db.scalars(select(SyncJob).where(SyncJob.status == "RUNNING")).all()
    if not running_jobs:
        return {"status": "ok", "message": "No active sync jobs found. Recalculation cancellation signal sent."}

    for job in running_jobs:
        job.status = "CANCELLED"
        job.end_time = datetime.now()
        job.error_summary = "Cancelled by user request."

    db.commit()
    return {"status": "ok", "message": f"Cancelled {len(running_jobs)} active sync job(s) and sent recalculation stop signal."}
