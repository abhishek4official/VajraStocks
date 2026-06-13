"""ML Training API — start / cancel / status / SSE stream / history."""

import asyncio
import json
import queue as stdlib_queue
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, select, text
from sqlalchemy.orm import Session

from stocks.db.models import MLTrainingRun

router = APIRouter(prefix="/ml", tags=["ML Training"])


# ── Helpers ────────────────────────────────────────────────────────────────────

def _next_version(engine) -> str:
    """Generate version string: v2026.06.13.001 (date + daily counter)."""
    today = datetime.now().strftime("%Y.%m.%d")
    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM ml_training_runs WHERE version LIKE :p"),
            {"p": f"v{today}.%"},
        ).scalar() or 0
    return f"v{today}.{int(count) + 1:03d}"


def _serialise(row: MLTrainingRun) -> dict:
    fm = None
    if row.fold_metrics:
        try:
            fm = json.loads(row.fold_metrics)
        except Exception:
            pass
    return {
        "id":               row.id,
        "version":          row.version,
        "status":           row.status,
        "device":           row.device,
        "num_folds":        row.num_folds,
        "dataset_rows":     row.dataset_rows,
        "date_range_start": row.date_range_start.isoformat() if row.date_range_start else None,
        "date_range_end":   row.date_range_end.isoformat()   if row.date_range_end   else None,
        "mean_ic":          row.mean_ic,
        "fold_metrics":     fm,
        "error_message":    row.error_message,
        "started_at":       row.started_at.isoformat()   if row.started_at   else None,
        "completed_at":     row.completed_at.isoformat() if row.completed_at else None,
    }


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/train")
def start_training(request: Request):
    """
    Start a background walk-forward training job.
    Returns 409 Conflict if a job is already running.
    """
    manager    = request.app.state.training_manager
    db_manager = request.app.state.db_manager
    engine     = db_manager.engine

    if manager.is_running():
        raise HTTPException(status_code=409, detail="A training job is already in progress.")

    import sys
    from pathlib import Path
    _root = str(Path(__file__).parents[6])
    if _root not in sys.path:
        sys.path.insert(0, _root)

    version = _next_version(engine)
    session: Session = db_manager.get_session()
    try:
        run = MLTrainingRun(
            version=version,
            status="RUNNING",
            started_at=datetime.now(timezone.utc),
        )
        session.add(run)
        session.commit()
        run_id = run.id
    finally:
        session.close()

    manager.start(engine, run_id)
    return {"run_id": run_id, "version": version, "status": "started"}


@router.delete("/train")
def cancel_training(request: Request):
    """Request cancellation of the running training job."""
    manager = request.app.state.training_manager
    if not manager.is_running():
        raise HTTPException(status_code=404, detail="No training job is currently running.")
    manager.cancel()
    return {"status": "cancelling"}


@router.get("/train/status")
def training_status(request: Request):
    """Returns whether training is running and the active run_id."""
    manager = request.app.state.training_manager
    if manager.is_running():
        return {"status": "running", "run_id": manager.current_run_id()}
    return {"status": "idle", "run_id": None}


@router.get("/train/stream")
async def stream_training(request: Request):
    """
    SSE stream of training progress events.
    Each event is a JSON object on a `data:` line.

    Event types: stage | device | dataset | fold_start | tree |
                 fold_done | complete | cancelled | error | heartbeat | stream_end
    """
    manager = request.app.state.training_manager
    job     = manager.current_job()

    if job is None:
        raise HTTPException(status_code=404, detail="No training job is currently running.")

    progress_q = job.progress_q
    loop       = asyncio.get_event_loop()

    async def generator():
        while True:
            if await request.is_disconnected():
                break
            try:
                event = await loop.run_in_executor(
                    None,
                    lambda: progress_q.get(timeout=1.5),
                )
                if event is None:                                  # sentinel
                    yield f"data: {json.dumps({'type': 'stream_end'})}\n\n"
                    break
                yield f"data: {json.dumps(event)}\n\n"
            except stdlib_queue.Empty:
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":        "keep-alive",
        },
    )


@router.get("/history")
def training_history(request: Request):
    """Returns the last 20 training runs, most recent first."""
    db_manager = request.app.state.db_manager
    session: Session = db_manager.get_session()
    try:
        rows = session.scalars(
            select(MLTrainingRun).order_by(desc(MLTrainingRun.id)).limit(20)
        ).all()
        return [_serialise(r) for r in rows]
    finally:
        session.close()


@router.get("/latest")
def latest_model_info(request: Request):
    """Returns the most recent COMPLETED training run, or null."""
    db_manager = request.app.state.db_manager
    session: Session = db_manager.get_session()
    try:
        row = session.scalars(
            select(MLTrainingRun)
            .where(MLTrainingRun.status == "COMPLETED")
            .order_by(desc(MLTrainingRun.id))
            .limit(1)
        ).first()
        return _serialise(row) if row else None
    finally:
        session.close()
