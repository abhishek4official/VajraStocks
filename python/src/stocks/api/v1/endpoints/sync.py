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
    """Pipelined chunking recalculate.

    For each chunk of CHUNK_SIZE symbols:
      1. FETCH   — main thread reads raw prices from DB (sequential, no locks held)
      2. COMPUTE — parallel CPU work via ProcessPoolExecutor (zero DB access)
      3. WRITE   — main thread writes all results + snapshots in ONE transaction,
                   then commits once; rolls back the entire chunk on any error.
    """
    import multiprocessing
    from concurrent.futures import ProcessPoolExecutor, as_completed
    from loguru import logger
    from sqlalchemy import delete
    from stocks.db.models import DailyIndicator
    from stocks.services.sync_engine import calculate_derived_data_in_memory

    CHUNK_SIZE = 50
    EPOCH = datetime.strptime("1970-01-01", "%Y-%m-%d").date()

    cfg = get_config(request)
    db_manager = request.app.state.db_manager
    session = db_manager.get_session()
    db_service = DatabaseService(cfg, session)

    try:
        request.app.state.cancel_recalculate = False
        active_symbols = db_service.get_active_symbols()
        if symbol_ticker:
            clean_sym = symbol_ticker.strip().upper()
            if not clean_sym.endswith(".NS") and not clean_sym.startswith("^"):
                clean_sym = f"{clean_sym}.NS"
            active_symbols = [s for s in active_symbols if s.symbol == clean_sym]

        total = len(active_symbols)
        request.app.state.recalc_progress = {
            "status": "RUNNING", "total": total, "processed": 0, "failed": 0,
        }

        from stocks.services.screening import ScreeningService
        screening_svc = ScreeningService(cfg, session)
        nifty_21d_return = screening_svc._get_nifty_21d_return()

        processed = 0
        failed = 0
        max_workers = min(10, multiprocessing.cpu_count())

        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            for chunk_start in range(0, total, CHUNK_SIZE):
                if getattr(request.app.state, "cancel_recalculate", False):
                    logger.warning("Recalculation cancelled by user request.")
                    break

                chunk = active_symbols[chunk_start:chunk_start + CHUNK_SIZE]
                symbol_map = {sym.id: sym.symbol for sym in chunk}

                # ── 1. FETCH (1 query for the whole chunk) ───────────────────
                prices_batch = db_service.get_prices_for_symbols_batch(
                    list(symbol_map.keys()), EPOCH
                )
                chunk_inputs: list[tuple[int, str, list]] = []
                for sid, sym_str in symbol_map.items():
                    prices = prices_batch.get(sid, [])
                    if prices:
                        chunk_inputs.append((sid, sym_str, prices))
                    else:
                        logger.warning(f"[{sym_str}] No prices found, skipping.")
                        failed += 1

                if not chunk_inputs:
                    request.app.state.recalc_progress["failed"] = failed
                    continue

                # ── 2. COMPUTE (parallel across CPU cores) ───────────────────
                futures = {
                    executor.submit(calculate_derived_data_in_memory, sid, sym_str, prices): sym_str
                    for sid, sym_str, prices in chunk_inputs
                }

                chunk_results: list[dict] = []
                for future in as_completed(futures):
                    sym_str = futures[future]
                    try:
                        chunk_results.append(future.result())
                    except Exception as calc_err:
                        logger.error(f"[{sym_str}] Calculation failed: {calc_err}")
                        failed += 1

                if not chunk_results:
                    request.app.state.recalc_progress["failed"] = failed
                    continue

                # ── 3. WRITE (4 DELETEs + 4 bulk INSERTs for the whole chunk)
                # All writes happen inside one transaction; commit once at the end.
                try:
                    result_ids = [r["symbol_id"] for r in chunk_results]

                    session.execute(delete(DailyIndicator).where(DailyIndicator.symbol_id.in_(result_ids)))

                    all_indicators: list[dict] = []
                    for result in chunk_results:
                        sid = result["symbol_id"]
                        for ind in result["indicators"]:
                            ind["symbol_id"] = sid
                            ind["granularity"] = "1d"
                        all_indicators.extend(result["indicators"])

                    if all_indicators:
                        session.bulk_insert_mappings(DailyIndicator, all_indicators)

                    # Confluence S/R levels — per-symbol with savepoints.
                    # Runs after bulk inserts so DailyIndicator rows (ATR, SMAs) are
                    # already visible in the open transaction for the confluence reads.
                    from stocks.services.quant.confluence_service import ConfluenceService
                    confluence_svc = ConfluenceService(session)
                    for result in chunk_results:
                        try:
                            with session.begin_nested():
                                confluence_svc.calculate_and_save_levels(result["symbol_id"], commit=False)
                        except Exception as conf_err:
                            logger.error(f"[{result['symbol']}] Confluence calculation failed: {conf_err}")

                    # Snapshot refresh — per-symbol with savepoints so one bad symbol
                    # cannot abort the chunk's transaction.
                    for result in chunk_results:
                        try:
                            with session.begin_nested():
                                screening_svc.refresh_snapshot_for_symbol(
                                    result["symbol_id"],
                                    nifty_21d_return=nifty_21d_return,
                                    commit=False,
                                )
                        except Exception as snap_err:
                            logger.error(f"[{result['symbol']}] Snapshot refresh failed: {snap_err}")

                    session.commit()
                    processed += len(chunk_results)

                except Exception as write_err:
                    logger.error(
                        f"Chunk write failed (symbols {chunk_start}–{chunk_start + CHUNK_SIZE}): {write_err}"
                    )
                    try:
                        session.rollback()
                    except Exception:
                        pass
                    failed += len(chunk_results)

                request.app.state.recalc_progress["processed"] = processed
                request.app.state.recalc_progress["failed"] = failed

        from stocks.services.strategy_screener import StrategyScreenerService
        StrategyScreenerService(cfg, session).refresh_all_strategies()

        request.app.state.recalc_progress["status"] = "DONE"

    except Exception as err:
        logger.error(f"Recalculate job failed: {err}")
        try:
            session.rollback()
        except Exception:
            pass
        if hasattr(request.app.state, "recalc_progress"):
            request.app.state.recalc_progress["status"] = "ERROR"
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


@router.get("/recalculate/progress")
def get_recalculate_progress(request: Request):
    """Returns live progress of the currently running (or last completed) recalculation job."""
    prog = getattr(request.app.state, "recalc_progress", None)
    if prog is None:
        return {"status": "IDLE", "total": 0, "processed": 0, "failed": 0}
    return prog


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
