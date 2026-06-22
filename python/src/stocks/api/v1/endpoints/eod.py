"""NSE EOD file import endpoints."""

import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from stocks.api.deps import get_config, get_db
from stocks.services.eod_service import EodImportService

router = APIRouter(prefix="/eod", tags=["EOD Import"])


# ── Pydantic schemas ───────────────────────────────────────────────────────────

class EodJobResponse(BaseModel):
    job_id: str
    filename: str
    file_date: str
    status: str
    uploaded_at: str
    started_at: str | None = None
    completed_at: str | None = None
    total_rows: int | None = None
    equity_rows: int | None = None
    staged_count: int | None = None
    yahoo_filled_count: int | None = None
    eod_patched_count: int | None = None
    unresolved_symbols: list[str] | None = None
    gap_info: dict | None = None
    error_message: str | None = None


def _job_to_response(job) -> EodJobResponse:
    import json
    unresolved = None
    if job.unresolved_symbols:
        try:
            unresolved = json.loads(job.unresolved_symbols)
        except Exception:
            unresolved = []
    gap_info = None
    if job.gap_info:
        try:
            gap_info = json.loads(job.gap_info)
        except Exception:
            gap_info = None
    return EodJobResponse(
        job_id=job.job_id,
        filename=job.filename,
        file_date=str(job.file_date),
        status=job.status,
        uploaded_at=job.uploaded_at.isoformat() if job.uploaded_at else "",
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        total_rows=job.total_rows,
        equity_rows=job.equity_rows,
        staged_count=job.staged_count,
        yahoo_filled_count=job.yahoo_filled_count,
        eod_patched_count=job.eod_patched_count,
        unresolved_symbols=unresolved,
        gap_info=gap_info,
        error_message=job.error_message,
    )


def _get_service(request: Request) -> EodImportService:
    cfg = get_config(request)
    db_manager = request.app.state.db_manager
    return EodImportService(cfg, db_manager)


# ── Background worker ──────────────────────────────────────────────────────────

def _run_import_task(request: Request, job_id: str, file_bytes: bytes) -> None:
    svc = _get_service(request)
    svc.run_import(job_id, file_bytes)


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/upload", response_model=EodJobResponse, status_code=202)
async def upload_eod_file(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """
    Upload an NSE EOD Bhavcopy file (format: PD{DDMMYYYY}.csv).

    The file is validated and staged immediately; the import pipeline runs in
    the background. Poll GET /eod/jobs/{job_id} to track progress.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    svc = _get_service(request)
    job_id, err = svc.create_job(file.filename)
    if err:
        raise HTTPException(status_code=409 if "already imported" in err else 400, detail=err)

    file_bytes = await file.read()
    background_tasks.add_task(_run_import_task, request, job_id, file_bytes)

    job = svc.get_job(job_id)
    return _job_to_response(job)


@router.get("/jobs", response_model=list[EodJobResponse])
def list_eod_jobs(request: Request, limit: int = 30):
    """Returns recent EOD import jobs, newest first."""
    svc = _get_service(request)
    return [_job_to_response(j) for j in svc.list_jobs(limit=limit)]


@router.get("/jobs/{job_id}", response_model=EodJobResponse)
def get_eod_job(job_id: str, request: Request):
    """Returns the status of a specific EOD import job."""
    svc = _get_service(request)
    job = svc.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    return _job_to_response(job)


@router.post("/jobs/{job_id}/retry-calculations", response_model=EodJobResponse)
def retry_calculations(job_id: str, request: Request, background_tasks: BackgroundTasks):
    """
    Re-runs indicator/market-structure calculations and screening refresh for
    the symbols that were EOD-patched in a previous import. Use when calculations
    failed but raw price data was already saved.
    """
    svc = _get_service(request)
    job = svc.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    if job.status == "CALCULATING":
        raise HTTPException(status_code=409, detail="Calculations already in progress for this job.")
    background_tasks.add_task(_retry_calculations_task, request, job_id)
    job = svc.get_job(job_id)
    return _job_to_response(job)


def _retry_calculations_task(request: Request, job_id: str) -> None:
    svc = _get_service(request)
    try:
        svc.retry_calculations(job_id)
    except Exception as exc:
        from loguru import logger
        logger.error(f"[EOD] Retry calculations failed for {job_id}: {exc}")


@router.delete("/jobs/{job_id}", status_code=204)
def delete_eod_job(job_id: str, request: Request):
    """
    Deletes an import job and its staging data. This allows re-importing the
    same date's file. The imported price data in daily_prices is NOT deleted.
    """
    svc = _get_service(request)
    if not svc.delete_job(job_id):
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
