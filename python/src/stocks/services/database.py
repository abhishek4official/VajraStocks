import datetime
import uuid
from typing import Any

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from stocks.config import Config
from stocks.db.models import (
    DailyHeikinAshi,
    DailyIndicator,
    DailyPrice,
    LineBreakLine,
    RenkoBrick,
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

                # 4. Clean up orphaned Heikin-Ashi candles
                stmt_ha = delete(DailyHeikinAshi).where(
                    ~exists().where(
                        (DailyPrice.symbol_id == DailyHeikinAshi.symbol_id)
                        & (DailyPrice.trading_date == DailyHeikinAshi.trading_date)
                        & (DailyPrice.granularity == DailyHeikinAshi.granularity)
                    )
                )
                self.db.execute(stmt_ha)

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

    def get_latest_heikin_ashi(self, symbol_id: int) -> dict[str, Any] | None:
        """Queries the single latest Heikin-Ashi candle for a symbol."""
        row = self.db.scalar(
            select(DailyHeikinAshi)
            .filter_by(symbol_id=symbol_id)
            .order_by(DailyHeikinAshi.trading_date.desc())
            .limit(1)
        )
        if row:
            return {
                "trading_date": row.trading_date,
                "open": float(row.open),
                "high": float(row.high),
                "low": float(row.low),
                "close": float(row.close),
            }
        return None

    def get_latest_renko_brick(self, symbol_id: int) -> dict[str, Any] | None:
        """Queries the single latest Renko brick for a symbol (max brick_index)."""
        row = self.db.scalar(
            select(RenkoBrick).filter_by(symbol_id=symbol_id).order_by(RenkoBrick.brick_index.desc()).limit(1)
        )
        if row:
            return {
                "brick_index": row.brick_index,
                "start_date": row.start_date,
                "end_date": row.end_date,
                "open": float(row.open),
                "close": float(row.close),
                "direction": row.direction,
                "brick_size": float(row.brick_size),
            }
        return None

    def get_latest_line_break_lines(self, symbol_id: int, count: int = 3) -> list[dict[str, Any]]:
        """Queries the N latest Line Break lines for a symbol (ordered by line_index)."""
        rows = self.db.scalars(
            select(LineBreakLine).filter_by(symbol_id=symbol_id).order_by(LineBreakLine.line_index.desc()).limit(count)
        ).all()
        # Reverse them to be in ascending order for the engine
        return [
            {
                "line_index": r.line_index,
                "start_date": r.start_date,
                "end_date": r.end_date,
                "open": float(r.open),
                "close": float(r.close),
                "direction": r.direction,
            }
            for r in reversed(rows)
        ]

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

    def save_derived_structures(
        self,
        symbol_id: int,
        indicators: list[dict[str, Any]],
        ha_candles: list[dict[str, Any]],
        renko_bricks: list[dict[str, Any]],
        line_breaks: list[dict[str, Any]],
    ) -> None:
        """Saves calculated indicators and market structures within an isolated transaction.

        Overwrites existing indicator/HA candle records for the same dates to ensure idempotency.
        """
        from sqlalchemy import delete

        try:
            # 1. Save Indicators
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

            # 2. Save Heikin-Ashi Candles
            if ha_candles:
                dates = [ha["trading_date"] for ha in ha_candles]
                self.db.execute(
                    delete(DailyHeikinAshi).where(
                        DailyHeikinAshi.symbol_id == symbol_id, DailyHeikinAshi.trading_date.in_(dates)
                    )
                )
                for ha in ha_candles:
                    ha["symbol_id"] = symbol_id
                    ha["granularity"] = ha.get("granularity", "1d")
                self.db.bulk_insert_mappings(DailyHeikinAshi, ha_candles)

            # 3. Save Renko Bricks (Strictly Appends)
            if renko_bricks:
                max_brick_idx = (
                    self.db.scalar(select(func.max(RenkoBrick.brick_index)).filter_by(symbol_id=symbol_id)) or 0
                )
                bricks_to_insert = []
                for brick in renko_bricks:
                    if brick["brick_index"] > max_brick_idx:
                        brick["symbol_id"] = symbol_id
                        bricks_to_insert.append(brick)
                if bricks_to_insert:
                    self.db.bulk_insert_mappings(RenkoBrick, bricks_to_insert)

            # 4. Save Line Break Lines (Strictly Appends)
            if line_breaks:
                max_line_idx = (
                    self.db.scalar(select(func.max(LineBreakLine.line_index)).filter_by(symbol_id=symbol_id)) or 0
                )
                lines_to_insert = []
                for lb in line_breaks:
                    if lb["line_index"] > max_line_idx:
                        lb["symbol_id"] = symbol_id
                        lines_to_insert.append(lb)
                if lines_to_insert:
                    self.db.bulk_insert_mappings(LineBreakLine, lines_to_insert)

            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to save derived structures for symbol_id {symbol_id}: {e}")
            raise e
