"""Background jobs API (V2.0 spec M1) — enqueue, poll progress, cancel, retry."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from stocks.api.deps import get_db
from stocks.db.models import Job
from stocks.services.jobs.runner import JobRunner

router = APIRouter(prefix="/jobs", tags=["Jobs"])


class EnqueueIn(BaseModel):
    kind: str
    params: dict[str, Any] = {}


class JobOut(BaseModel):
    id: int
    kind: str
    status: str
    progress_current: int
    progress_total: int
    cancel_requested: bool
    error: str | None
    created_at: str | None
    started_at: str | None
    finished_at: str | None


def _out(j: Job) -> JobOut:
    return JobOut(
        id=j.id, kind=j.kind, status=j.status,
        progress_current=j.progress_current, progress_total=j.progress_total,
        cancel_requested=j.cancel_requested, error=j.error,
        created_at=j.created_at.isoformat() if j.created_at else None,
        started_at=j.started_at.isoformat() if j.started_at else None,
        finished_at=j.finished_at.isoformat() if j.finished_at else None,
    )


@router.post("", response_model=JobOut)
def enqueue(body: EnqueueIn, db: Session = Depends(get_db)):
    """Enqueue a background job (runs on the worker, off the request thread)."""
    return _out(JobRunner(db).enqueue(body.kind, body.params))


@router.get("", response_model=list[JobOut])
def list_jobs(status: str | None = None, db: Session = Depends(get_db)):
    return [_out(j) for j in JobRunner(db).list(status=status)]


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_db)):
    j = JobRunner(db).get(job_id)
    if j is None:
        raise HTTPException(status_code=404, detail=f"No job {job_id}")
    return _out(j)


@router.post("/{job_id}/cancel", response_model=JobOut)
def cancel_job(job_id: int, db: Session = Depends(get_db)):
    runner = JobRunner(db)
    if not runner.cancel(job_id):
        raise HTTPException(status_code=409, detail="Job not cancellable (missing or already finished)")
    return _out(runner.get(job_id))


@router.post("/{job_id}/retry", response_model=JobOut)
def retry_job(job_id: int, db: Session = Depends(get_db)):
    runner = JobRunner(db)
    if not runner.retry(job_id):
        raise HTTPException(status_code=409, detail="Job not retryable (missing or running)")
    return _out(runner.get(job_id))
