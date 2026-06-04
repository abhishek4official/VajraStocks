import asyncio
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
    """Returns the local naive datetime corresponding to 05:15 (5:15 AM) of the latest daily milestone
    relative to the given local naive datetime `dt`.
    """
    temp = dt.replace(second=0, microsecond=0)
    
    is_after_milestone = temp.time() >= datetime.time(5, 15)
    
    if is_after_milestone:
        return temp.replace(hour=5, minute=15)
    else:
        return (temp - datetime.timedelta(days=1)).replace(hour=5, minute=15)


async def check_and_run_sync(db_manager) -> None:
    """Checks if the daily sync for the latest EOD milestone (threshold: 05:15 IST) has been run.
    If not, runs it.
    """
    logger.info("Scheduler: Checking if daily sync is missed...")
    
    now_local = datetime.datetime.now()
    threshold = get_latest_eod_threshold(now_local)
    
    session = db_manager.get_session()
    try:
        stmt = select(SyncJob).where(
            SyncJob.status.in_(["SUCCESS", "PARTIAL"]),
            SyncJob.start_time >= threshold
        )
        job = session.scalar(stmt)
        if job is None:
            logger.info(f"Scheduler: Missed sync detected for latest trading day EOD (threshold: {threshold}). Auto-triggering EOD sync...")
            
            # Run sync in threadpool so it doesn't block the asyncio event loop
            loop = asyncio.get_running_loop()
            
            def run():
                req = SimpleRequest(db_manager)
                cfg = get_config(req)
                engine = SyncEngine(cfg, db_manager)
                engine.run_sync()
                
            await loop.run_in_executor(None, run)
            logger.info("Scheduler: EOD sync completed successfully.")
        else:
            logger.info(f"Scheduler: Daily sync for EOD (threshold: {threshold}) already completed at {job.start_time}.")
    except Exception as e:
        logger.error(f"Scheduler: Error during check and run: {e}")
    finally:
        session.close()


async def run_scheduler(db_manager) -> None:
    """Main scheduler background task loop."""
    logger.info("Scheduler: Background scheduler task started.")
    
    # 1. Run check immediately on startup (handles missed syncs when app was closed)
    try:
        await check_and_run_sync(db_manager)
    except Exception as e:
        logger.error(f"Scheduler: Startup check failed: {e}")
        
    # 2. Loop forever, checking for next milestone
    while True:
        try:
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            # Find the next 00:00 UTC milestone (tomorrow 00:00 UTC)
            next_milestone_utc = (now_utc + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Calculate sleep duration in seconds
            sleep_duration = (next_milestone_utc - now_utc).total_seconds()
            logger.info(f"Scheduler: Next sync scheduled at {next_milestone_utc} UTC (sleeping for {sleep_duration:.1f}s)")
            
            # Periodic check every 60 seconds to handle laptop sleep/resume and timezone/time adjustments robustly
            while True:
                await asyncio.sleep(60)
                current_now_utc = datetime.datetime.now(datetime.timezone.utc)
                if current_now_utc >= next_milestone_utc:
                    break
            
            # Time to run!
            await check_and_run_sync(db_manager)
            
        except asyncio.CancelledError:
            logger.info("Scheduler: Background scheduler task cancelled.")
            break
        except Exception as e:
            logger.error(f"Scheduler: Error in loop: {e}")
            await asyncio.sleep(60)  # Wait 60 seconds before retrying
