import asyncio
import concurrent.futures
import datetime
from loguru import logger
from sqlalchemy import select
from stocks.db.models import SyncJob
from stocks.services.sync_engine import SyncEngine
from stocks.api.deps import get_config

class SimpleState:
    def __init__(self, db_manager):
        self.db_manager = db_manager

class SimpleApp:
    def __init__(self, db_manager):
        self.state = SimpleState(db_manager)

class SimpleRequest:
    def __init__(self, db_manager):
        self.app = SimpleApp(db_manager)


def get_latest_eod_threshold(dt: datetime.datetime) -> datetime.datetime:
    """Returns the local naive datetime for 05:15 of the latest daily EOD milestone."""
    temp = dt.replace(second=0, microsecond=0)
    if temp.time() >= datetime.time(5, 15):
        return temp.replace(hour=5, minute=15)
    return (temp - datetime.timedelta(days=1)).replace(hour=5, minute=15)


# Tracks the running sync future so shutdown can wait for it to finish
# and the DB engine is not disposed while the thread still holds connections.
_active_sync_future: concurrent.futures.Future | None = None


async def check_and_run_sync(db_manager) -> None:
    """Checks if the daily sync for the latest EOD milestone has been run; triggers it if not."""
    global _active_sync_future
    logger.info("Scheduler: Checking if daily sync is missed...")

    now_local = datetime.datetime.now()
    threshold = get_latest_eod_threshold(now_local)

    session = db_manager.get_session()
    try:
        job = session.scalar(
            select(SyncJob).where(
                SyncJob.status.in_(["SUCCESS", "PARTIAL"]),
                SyncJob.start_time >= threshold,
            )
        )
        if job is None:
            logger.info(
                f"Scheduler: Missed sync detected (threshold: {threshold}). Auto-triggering EOD sync..."
            )
            loop = asyncio.get_running_loop()

            def run():
                req = SimpleRequest(db_manager)
                cfg = get_config(req)
                engine = SyncEngine(cfg, db_manager)
                engine.run_sync()
                # Evaluate alerts post-sync
                try:
                    from stocks.services.alert_service import AlertService
                    session = db_manager.get_session()
                    try:
                        AlertService(session).evaluate_all()
                    finally:
                        session.close()
                except Exception as ae:
                    logger.warning(f"Scheduler: Alert evaluation failed (non-fatal): {ae}")
                # Weekly ML retraining on Sunday
                if datetime.datetime.now().weekday() == 6:
                    _maybe_retrain_ml(db_manager)

            future = loop.run_in_executor(None, run)
            _active_sync_future = asyncio.ensure_future(future)
            await _active_sync_future
            logger.info("Scheduler: EOD sync completed successfully.")
        else:
            logger.info(
                f"Scheduler: Daily sync for EOD already completed at {job.start_time}."
            )
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.error(f"Scheduler: Error during check and run: {e}")
    finally:
        session.close()
        _active_sync_future = None


async def shutdown_scheduler() -> None:
    """Called during app shutdown — waits up to 5 s for any in-flight sync to finish."""
    global _active_sync_future
    if _active_sync_future is not None and not _active_sync_future.done():
        logger.info("Scheduler: Waiting for in-flight sync to finish before shutdown (max 5s)...")
        try:
            await asyncio.wait_for(_active_sync_future, timeout=5.0)
        except (asyncio.TimeoutError, asyncio.CancelledError, Exception):
            pass
        _active_sync_future = None


def _maybe_retrain_ml(db_manager) -> None:
    """Triggers ML walk-forward retraining once per week. Non-fatal on any error."""
    try:
        import sys
        from datetime import datetime, timedelta, timezone
        from pathlib import Path
        from sqlalchemy import desc, select
        from stocks.db.models import MLTrainingRun

        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        session = db_manager.get_session()
        try:
            recent = session.scalar(
                select(MLTrainingRun)
                .where(MLTrainingRun.status == "COMPLETED", MLTrainingRun.completed_at >= week_ago)
                .limit(1)
            )
            running = session.scalar(
                select(MLTrainingRun).where(MLTrainingRun.status == "RUNNING").limit(1)
            )
        finally:
            session.close()

        if recent:
            logger.info(f"Scheduler: Weekly ML retraining skipped — last run completed {recent.completed_at}")
            return
        if running:
            logger.info("Scheduler: Weekly ML retraining skipped — a job is already running")
            return

        logger.info("Scheduler: Triggering weekly ML retraining...")
        _root = str(Path(__file__).resolve().parents[4])
        if _root not in sys.path:
            sys.path.insert(0, _root)

        version = f"v{datetime.now(timezone.utc).strftime('%Y.%m.%d')}.weekly"
        session = db_manager.get_session()
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

        from VajraML.train_service import TrainingJobManager
        TrainingJobManager().start(db_manager.engine, run_id)
        logger.info(f"Scheduler: Weekly ML retraining started — run_id={run_id}, version={version}")
    except Exception as exc:
        logger.warning(f"Scheduler: Weekly ML retraining failed (non-fatal): {exc}")


async def run_scheduler(db_manager) -> None:
    """Main scheduler background task loop."""
    logger.info("Scheduler: Background scheduler task started.")

    # Run check immediately on startup (handles missed syncs when app was closed)
    try:
        await check_and_run_sync(db_manager)
    except asyncio.CancelledError:
        logger.info("Scheduler: Startup sync cancelled during shutdown.")
        return
    except Exception as e:
        logger.error(f"Scheduler: Startup check failed: {e}")

    # Loop, waking every 60 s to check if the next daily milestone has passed
    while True:
        try:
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            next_milestone_utc = (now_utc + datetime.timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            logger.info(f"Scheduler: Next sync at {next_milestone_utc} UTC")

            while True:
                await asyncio.sleep(60)
                if datetime.datetime.now(datetime.timezone.utc) >= next_milestone_utc:
                    break

            await check_and_run_sync(db_manager)

        except asyncio.CancelledError:
            logger.info("Scheduler: Background scheduler task cancelled.")
            break
        except Exception as e:
            logger.error(f"Scheduler: Error in loop: {e}")
            await asyncio.sleep(60)
