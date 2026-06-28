"""DB-backed job runner: enqueue, claim, execute, progress, cancel, retry.

Handlers register by ``kind``. A handler has the signature::

    handler(job, session, set_progress, is_cancelled) -> dict | None

- ``set_progress(current, total)`` records progress on the job.
- ``is_cancelled()`` re-reads the cancel flag from the DB (set by another request).
- raise ``JobCancelled`` to stop cooperatively → the job is marked CANCELLED.
- return a JSON-serialisable dict (or None) → stored as the result, job SUCCESS.
- any other exception → job FAILED with the error message.

``run_next()`` is the deterministic unit (claim oldest PENDING, run one job). The threaded
worker (worker.py) simply loops on it.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from stocks.db.models import Job

PENDING, RUNNING, SUCCESS, FAILED, CANCELLED = "PENDING", "RUNNING", "SUCCESS", "FAILED", "CANCELLED"

Handler = Callable[[Job, Session, Callable[[int, int], None], Callable[[], bool]], "dict | None"]
_HANDLERS: dict[str, Handler] = {}


class JobCancelled(Exception):
    """Raised by a handler to signal cooperative cancellation."""


def register_handler(kind: str) -> Callable[[Handler], Handler]:
    def deco(fn: Handler) -> Handler:
        _HANDLERS[kind] = fn
        return fn
    return deco


class JobRunner:
    def __init__(self, session: Session):
        self.session = session

    # ── queue management ───────────────────────────────────────────────────
    def enqueue(self, kind: str, params: dict[str, Any] | None = None) -> Job:
        job = Job(kind=kind, status=PENDING, params_json=json.dumps(params or {}))
        self.session.add(job)
        self.session.commit()
        return job

    def get(self, job_id: int) -> Job | None:
        return self.session.get(Job, job_id)

    def list(self, status: str | None = None, limit: int = 100) -> list[Job]:
        stmt = select(Job)
        if status is not None:
            stmt = stmt.where(Job.status == status.upper())
        stmt = stmt.order_by(Job.created_at.desc(), Job.id.desc()).limit(limit)
        return list(self.session.execute(stmt).scalars())

    def cancel(self, job_id: int) -> bool:
        job = self.session.get(Job, job_id)
        if job is None or job.status in (SUCCESS, FAILED, CANCELLED):
            return False
        job.cancel_requested = True
        self.session.commit()
        return True

    def retry(self, job_id: int) -> bool:
        """Re-queue a finished/failed job (clears error/result/progress)."""
        job = self.session.get(Job, job_id)
        if job is None or job.status == RUNNING:
            return False
        job.status = PENDING
        job.error = None
        job.result_json = None
        job.progress_current = 0
        job.progress_total = 0
        job.cancel_requested = False
        job.started_at = None
        job.finished_at = None
        self.session.commit()
        return True

    # ── execution ──────────────────────────────────────────────────────────
    def run_next(self) -> Job | None:
        """Claim the oldest PENDING job and run it. Returns the job, or None if idle."""
        job = self.session.execute(
            select(Job).where(Job.status == PENDING).order_by(Job.created_at, Job.id).limit(1)
        ).scalar_one_or_none()
        if job is None:
            return None

        job.status = RUNNING
        job.started_at = dt.datetime.now()
        self.session.commit()

        def set_progress(current: int, total: int) -> None:
            job.progress_current = current
            job.progress_total = total
            self.session.commit()

        def is_cancelled() -> bool:
            self.session.refresh(job, ["cancel_requested"])
            return bool(job.cancel_requested)

        handler = _HANDLERS.get(job.kind)
        try:
            if handler is None:
                raise RuntimeError(f"No handler registered for job kind '{job.kind}'")
            if is_cancelled():
                raise JobCancelled()
            result = handler(job, self.session, set_progress, is_cancelled)
            job.status = SUCCESS
            job.result_json = json.dumps(result) if result is not None else None
        except JobCancelled:
            job.status = CANCELLED
        except Exception as exc:  # noqa: BLE001 — any handler failure is recorded, not raised
            job.status = FAILED
            job.error = str(exc)
        finally:
            job.finished_at = dt.datetime.now()
            self.session.commit()
        return job
