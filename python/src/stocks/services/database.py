import datetime
import uuid
from typing import Any

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from stocks.config import Config
from stocks.db.models import (
    DailyIndicator,
    DailyPrice,
    Symbol,
    SymbolSyncState,
    SyncJob,
)


class DatabaseService:
    """Service to handle core database write/read operations, transactions, and state management."""

    def __init__(self, config: Config, db_session: Session):
        self.config = config
        self.db = db_session

    def get_active_symbols(self) -> list[Symbol]:
        """Queries all active symbols stored in the database."""
        return list(self.db.scalars(select(Symbol).filter_by(is_active=True)).all())

    def get_sync_state(self, symbol_id: int) -> SymbolSyncState | None:
        """Queries the synchronization state record for a symbol."""
        return self.db.scalar(select(SymbolSyncState).filter_by(symbol_id=symbol_id))

    def get_latest_price_date(self, symbol_id: int) -> datetime.date | None:
        """Queries the latest trading date available in daily_prices for a symbol."""
        return self.db.scalar(select(func.max(DailyPrice.trading_date)).filter_by(symbol_id=symbol_id))

    def get_global_latest_price_date(self) -> datetime.date | None:
        """Queries the maximum trading date available in daily_prices across all symbols."""
        return self.db.scalar(select(func.max(DailyPrice.trading_date)))

    def prune_zero_volume_records(self) -> int:
        """Prunes price records with zero or negative volume and cleans up orphaned indicators/Heikin-Ashi candles."""
        from sqlalchemy import delete, exists

        try:
            # 1. Count rows to prune
            count_query = select(func.count(DailyPrice.id)).where(DailyPrice.volume <= 0)
            pruned_count = self.db.scalar(count_query) or 0

            if pruned_count > 0:
                logger.info(f"Pruning {pruned_count} zero/negative volume records from daily_prices.")

                # 2. Delete zero/negative volume daily prices
                self.db.execute(delete(DailyPrice).where(DailyPrice.volume <= 0))

                # 3. Clean up orphaned indicators
                stmt_ind = delete(DailyIndicator).where(
                    ~exists().where(
                        (DailyPrice.symbol_id == DailyIndicator.symbol_id)
                        & (DailyPrice.trading_date == DailyIndicator.trading_date)
                        & (DailyPrice.granularity == DailyIndicator.granularity)
                    )
                )
                self.db.execute(stmt_ind)

                self.db.commit()
                logger.info("Database pruning and orphaned records cleanup completed successfully.")
            return pruned_count
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to prune zero-volume records: {e}")
            return 0

    def update_symbol_sync_failure(self, symbol_id: int, error_message: str) -> None:
        """Explicitly updates the synchronization state for a symbol to FAILED with an error message."""
        try:
            state = self.get_sync_state(symbol_id)
            if state is None:
                state = SymbolSyncState(
                    symbol_id=symbol_id,
                    last_successful_sync_date=datetime.date(1970, 1, 1),
                    last_attempt_status="FAILED",
                    last_error_message=error_message[:500],
                )
                self.db.add(state)
            else:
                state.last_attempt_status = "FAILED"
                state.last_error_message = error_message[:500]
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update sync failure state for symbol_id {symbol_id}: {e}")

    def save_stock_data(
        self, symbol_id: int, prices: list[dict[str, Any]], actions: list[dict[str, Any]], sync_date: datetime.date
    ) -> int:
        """Saves price and corporate action records using high-performance bulk repository operations.

        Guarantees that failures are isolated to this specific stock, updating its sync state record accordingly.
        """
        from stocks.db.repositories.price_repo import PriceRepository

        repo = PriceRepository(self.db)

        try:
            return repo.bulk_save_stock_data(symbol_id, prices, actions, sync_date)
        except Exception as e:
            logger.error(f"Failed to save stock data for symbol_id {symbol_id}: {e}")

            # Save failure status to the sync state so we have audit trails
            try:
                state = self.get_sync_state(symbol_id)
                if state is None:
                    state = SymbolSyncState(
                        symbol_id=symbol_id,
                        last_successful_sync_date=datetime.date(1970, 1, 1),  # Default placeholder epoch
                        last_attempt_status="FAILED",
                        last_error_message=str(e)[:500],
                    )
                    self.db.add(state)
                else:
                    state.last_attempt_status = "FAILED"
                    state.last_error_message = str(e)[:500]
                self.db.commit()
            except Exception as inner_e:
                self.db.rollback()
                logger.error(f"Critical error updating sync state failure status for symbol_id {symbol_id}: {inner_e}")

            raise e

    def create_sync_job(self) -> SyncJob:
        """Logs a new sync job record in the database."""
        job = SyncJob(
            run_id=str(uuid.uuid4()),
            start_time=datetime.datetime.now(),
            status="RUNNING",
            total_symbols=0,
            processed_symbols=0,
            failed_symbols=0,
            records_inserted=0,
        )
        self.db.add(job)
        self.db.commit()
        return job

    def update_sync_job_progress(self, job_id: int, processed: int, failed: int, inserted: int) -> None:
        """Saves current job progress metrics without closing the job."""
        try:
            job = self.db.get(SyncJob, job_id)
            if job:
                job.processed_symbols = processed
                job.failed_symbols = failed
                job.records_inserted += inserted
                self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update sync job progress: {e}")

    def finalize_sync_job(
        self, job_id: int, total: int, processed: int, failed: int, status: str, error_summary: str | None = None
    ) -> None:
        """Completes and finalizes a sync job record with final stats."""
        try:
            job = self.db.get(SyncJob, job_id)
            if job:
                job.end_time = datetime.datetime.now()
                job.total_symbols = total
                job.processed_symbols = processed
                job.failed_symbols = failed
                job.status = status
                job.error_summary = error_summary
                self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to finalize sync job: {e}")

    def is_sync_job_cancelled(self, job_id: int) -> bool:
        """Checks if the sync job has been marked as CANCELLED."""
        try:
            job = self.db.get(SyncJob, job_id)
            if job:
                self.db.refresh(job)
                return job.status == "CANCELLED"
        except Exception as e:
            logger.error(f"Failed to check if sync job is cancelled: {e}")
        return False

    def get_prices_for_window(self, symbol_id: int, start_date: datetime.date) -> list[dict[str, Any]]:
        """Queries the EOD prices starting from a specific date for a symbol, sorted by date."""
        rows = self.db.scalars(
            select(DailyPrice)
            .filter(DailyPrice.symbol_id == symbol_id, DailyPrice.trading_date >= start_date)
            .order_by(DailyPrice.trading_date.asc())
        ).all()
        return [
            {
                "trading_date": r.trading_date,
                "open": float(r.open),
                "high": float(r.high),
                "low": float(r.low),
                "close": float(r.close),
                "adj_close": float(r.adj_close),
                "volume": int(r.volume),
                "granularity": r.granularity,
            }
            for r in rows
        ]

    def get_prices_for_symbols_batch(
        self, symbol_ids: list[int], start_date: datetime.date
    ) -> dict[int, list[dict[str, Any]]]:
        """Fetches EOD prices for multiple symbols in ONE query, grouped by symbol_id.

        Reduces N individual SELECTs to a single IN() query — used by the
        pipelined chunk recalculate to avoid per-symbol round-trips.
        """
        if not symbol_ids:
            return {}
        rows = self.db.scalars(
            select(DailyPrice)
            .where(DailyPrice.symbol_id.in_(symbol_ids), DailyPrice.trading_date >= start_date)
            .order_by(DailyPrice.symbol_id, DailyPrice.trading_date.asc())
        ).all()
        result: dict[int, list[dict[str, Any]]] = {sid: [] for sid in symbol_ids}
        for r in rows:
            result[r.symbol_id].append({
                "trading_date": r.trading_date,
                "open":         float(r.open),
                "high":         float(r.high),
                "low":          float(r.low),
                "close":        float(r.close),
                "adj_close":    float(r.adj_close),
                "volume":       int(r.volume),
                "granularity":  r.granularity,
            })
        return result

    def save_derived_structures(
        self,
        symbol_id: int,
        indicators: list[dict[str, Any]],
        commit: bool = True,
    ) -> None:
        """Saves calculated indicators within an isolated transaction.

        Overwrites existing indicator records for the same dates to ensure idempotency.
        Pass commit=False when the caller manages batch commits for throughput.
        """
        from sqlalchemy import delete

        try:
            if indicators:
                dates = [ind["trading_date"] for ind in indicators]
                self.db.execute(
                    delete(DailyIndicator).where(
                        DailyIndicator.symbol_id == symbol_id, DailyIndicator.trading_date.in_(dates)
                    )
                )
                for ind in indicators:
                    ind["symbol_id"] = symbol_id
                    ind["granularity"] = ind.get("granularity", "1d")
                self.db.bulk_insert_mappings(DailyIndicator, indicators)

            if commit:
                self.db.commit()
        except Exception as e:
            if commit:
                self.db.rollback()
            logger.error(f"Failed to save derived structures for symbol_id {symbol_id}: {e}")
            raise e
