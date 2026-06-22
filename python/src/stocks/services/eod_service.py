"""NSE EOD file import service.

Workflow (Yahoo-first, EOD-as-fallback):
  1. Parse & validate PD{DDMMYYYY}.csv
  2. Stage parsed rows to eod_staging_data
  3. Detect data gaps per symbol
  4. Run scoped Yahoo sync to fill all gaps (including today)
  5. Diff — find symbols Yahoo still couldn't provide for file_date
  6. Patch those symbols from staged EOD data
  7. Run calculations only for EOD-patched symbols
  8. Full screening refresh (picks up all changes)
"""

import csv
import datetime
import io
import json
import re
import uuid
from typing import Any

from loguru import logger
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from stocks.config import Config
from stocks.db.connection import DatabaseManager
from stocks.db.models import (
    DailyPrice,
    EodImportJob,
    EodStagingData,
    Symbol,
    SymbolSyncState,
)


class EodImportService:
    """Orchestrates the NSE EOD CSV import pipeline."""

    def __init__(self, config: Config, db_manager: DatabaseManager):
        self.config = config
        self.db_manager = db_manager

    # ── Public API ─────────────────────────────────────────────────────────────

    def create_job(self, filename: str) -> tuple[str, str]:
        """Validates filename, creates a job record, returns (job_id, error_or_none)."""
        session = self.db_manager.get_session()
        try:
            file_date, err = self._parse_filename(filename)
            if err:
                return "", err

            if file_date > datetime.date.today():
                return "", f"File date {file_date} is in the future."

            existing = session.scalar(
                select(EodImportJob).where(EodImportJob.file_date == file_date)
            )
            if existing:
                return "", (
                    f"Data for {file_date} was already imported "
                    f"(job {existing.job_id}, status {existing.status}). "
                    "Delete the existing job first to re-import."
                )

            job_id = str(uuid.uuid4())
            job = EodImportJob(job_id=job_id, filename=filename, file_date=file_date, status="PENDING")
            session.add(job)
            session.commit()
            return job_id, ""
        finally:
            session.close()

    def run_import(self, job_id: str, file_bytes: bytes) -> None:
        """Full import pipeline — intended to run inside a FastAPI BackgroundTask."""
        session = self.db_manager.get_session()
        try:
            job = session.scalar(select(EodImportJob).where(EodImportJob.job_id == job_id))
            if not job:
                logger.error(f"[EOD] Job {job_id} not found.")
                return

            self._set_status(session, job, "VALIDATING")
            file_date = job.file_date

            # ── Phase 1: Parse ──────────────────────────────────────────────
            try:
                text = file_bytes.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = file_bytes.decode("latin-1", errors="ignore")

            all_rows, equity_rows = self._parse_csv(text)
            if not equity_rows:
                self._fail(session, job, "No valid N,EQ rows found in the file.")
                return

            job.total_rows = all_rows
            job.equity_rows = len(equity_rows)
            session.commit()

            # ── Phase 2: Resolve symbols ────────────────────────────────────
            resolved, unresolved = self._resolve_symbols(equity_rows, session)
            job.unresolved_symbols = json.dumps(unresolved) if unresolved else None
            session.commit()

            if not resolved:
                self._fail(session, job, "No symbols could be resolved against the database.")
                return

            # ── Phase 3: Stage parsed data ──────────────────────────────────
            self._set_status(session, job, "STAGING")
            staged_count = self._stage_data(job_id, file_date, resolved, session)
            job.staged_count = staged_count
            session.commit()

            # ── Phase 4: Gap detection + Yahoo fill ─────────────────────────
            nse_symbols = [r["symbol_nse"] for r in resolved]
            gap_info = self._compute_gap_info(resolved, file_date, session)
            job.gap_info = json.dumps(gap_info)
            session.commit()
            session.close()   # release before long Yahoo sync
            session = None

            self._update_status_detached(job_id, "GAP_FILLING")
            logger.info(f"[EOD {job_id}] Running Yahoo sync for {len(nse_symbols)} symbols to fill gaps...")
            self._run_yahoo_gap_fill(nse_symbols)
            logger.info(f"[EOD {job_id}] Yahoo sync complete.")

            # ── Phase 5: Diff — what did Yahoo miss for file_date? ──────────
            session = self.db_manager.get_session()
            self._update_status_detached(job_id, "PATCHING")
            diff_records = self._compute_diff(job_id, file_date, session)
            logger.info(f"[EOD {job_id}] Yahoo missed {len(diff_records)} symbols for {file_date}. Patching from EOD.")

            # ── Phase 6: Patch from EOD ─────────────────────────────────────
            patched_symbol_ids: list[int] = []
            if diff_records:
                patched_symbol_ids = self._patch_from_eod(diff_records, file_date, session)
            job = session.scalar(select(EodImportJob).where(EodImportJob.job_id == job_id))
            job.eod_patched_count = len(patched_symbol_ids)
            session.commit()

            # ── Phase 7: Calculations for patched symbols ───────────────────
            if patched_symbol_ids:
                self._update_status_detached(job_id, "CALCULATING")
                logger.info(f"[EOD {job_id}] Running derived calculations for {len(patched_symbol_ids)} patched symbols.")
                self._calculate_for_symbols(patched_symbol_ids, file_date, session)

                # ── Phase 8: Screening refresh for patched symbols ──────────
                self._update_status_detached(job_id, "REFRESHING")
                self._refresh_screening(patched_symbol_ids, session)

            # ── Finalize ────────────────────────────────────────────────────
            job = session.scalar(select(EodImportJob).where(EodImportJob.job_id == job_id))
            job.status = "SUCCESS"
            job.completed_at = datetime.datetime.now()
            session.commit()
            logger.info(f"[EOD {job_id}] Import complete. Patched {len(patched_symbol_ids)} symbols from EOD file.")

        except Exception as exc:
            logger.exception(f"[EOD {job_id}] Import failed: {exc}")
            try:
                if session:
                    self._fail(session, session.scalar(select(EodImportJob).where(EodImportJob.job_id == job_id)), str(exc))
                else:
                    self._update_status_detached(job_id, "FAILED", str(exc))
            except Exception:
                pass
        finally:
            if session:
                session.close()

    def get_job(self, job_id: str) -> EodImportJob | None:
        session = self.db_manager.get_session()
        try:
            return session.scalar(select(EodImportJob).where(EodImportJob.job_id == job_id))
        finally:
            session.close()

    def list_jobs(self, limit: int = 20) -> list[EodImportJob]:
        session = self.db_manager.get_session()
        try:
            return list(
                session.scalars(
                    select(EodImportJob).order_by(EodImportJob.file_date.desc()).limit(limit)
                ).all()
            )
        finally:
            session.close()

    def delete_job(self, job_id: str) -> bool:
        """Deletes a job and its staging data (allows re-import of same date)."""
        session = self.db_manager.get_session()
        try:
            job = session.scalar(select(EodImportJob).where(EodImportJob.job_id == job_id))
            if not job:
                return False
            session.execute(delete(EodStagingData).where(EodStagingData.job_id == job_id))
            session.delete(job)
            session.commit()
            return True
        finally:
            session.close()

    def retry_calculations(self, job_id: str) -> None:
        """Re-runs calculations and screening for symbols that were EOD-patched in a previous import."""
        session = self.db_manager.get_session()
        try:
            job = session.scalar(select(EodImportJob).where(EodImportJob.job_id == job_id))
            if not job:
                raise ValueError(f"Job {job_id} not found.")

            patched_rows = session.execute(
                select(EodStagingData.symbol_id)
                .where(EodStagingData.job_id == job_id, EodStagingData.used_for_patch == True)
            ).all()
            symbol_ids = [r[0] for r in patched_rows if r[0] is not None]

            if not symbol_ids:
                raise ValueError("No EOD-patched symbols found for this job.")

            self._set_status(session, job, "CALCULATING")
            self._calculate_for_symbols(symbol_ids, job.file_date, session)
            self._refresh_screening(symbol_ids, session)
            job.status = "SUCCESS"
            job.completed_at = datetime.datetime.now()
            session.commit()
        finally:
            session.close()

    # ── Private helpers ─────────────────────────────────────────────────────────

    def _parse_filename(self, filename: str) -> tuple[datetime.date | None, str]:
        """Parses PD22062026.csv → date(2026, 6, 22). Returns (date, error_string)."""
        name = filename.upper().replace(".CSV", "")
        m = re.match(r"^PD(\d{2})(\d{2})(\d{4})$", name)
        if not m:
            return None, (
                f"Invalid filename '{filename}'. Expected format: PD{'{DDMMYYYY}'}.csv "
                "(e.g. PD22062026.csv)"
            )
        dd, mm, yyyy = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return datetime.date(yyyy, mm, dd), ""
        except ValueError as e:
            return None, f"Invalid date in filename: {e}"

    def _parse_csv(self, text: str) -> tuple[int, list[dict]]:
        """Returns (total_row_count, equity_rows_only)."""
        reader = csv.DictReader(io.StringIO(text))
        all_rows = 0
        equity_rows: list[dict] = []
        for row in reader:
            all_rows += 1
            mkt = (row.get("MKT") or "").strip()
            series = (row.get("SERIES") or "").strip()
            if mkt != "N" or series != "EQ":
                continue
            symbol = (row.get("SYMBOL") or "").strip()
            if not symbol:
                continue
            try:
                close = float(row.get("CLOSE_PRICE", 0) or 0)
                volume = int(float(row.get("NET_TRDQTY", 0) or 0))
                open_ = float(row.get("OPEN_PRICE", 0) or 0)
                high = float(row.get("HIGH_PRICE", 0) or 0)
                low = float(row.get("LOW_PRICE", 0) or 0)
            except (ValueError, TypeError):
                continue
            if close <= 0 or volume <= 0:
                continue
            equity_rows.append({
                "symbol_nse": symbol,
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            })
        return all_rows, equity_rows

    def _resolve_symbols(self, equity_rows: list[dict], session: Session) -> tuple[list[dict], list[str]]:
        """Maps NSE symbol names to symbol_id. Returns (resolved_records, unresolved_symbols)."""
        all_symbols = session.execute(
            select(Symbol.id, Symbol.symbol).where(Symbol.is_active == True)
        ).all()
        # NSE symbols in DB are stored as "RELIANCE.NS"; EOD file has plain "RELIANCE"
        symbol_map: dict[str, int] = {}
        for sym_id, sym_str in all_symbols:
            key = sym_str.replace(".NS", "").replace("^", "")
            symbol_map[key] = sym_id

        resolved: list[dict] = []
        unresolved: list[str] = []
        for row in equity_rows:
            sym_id = symbol_map.get(row["symbol_nse"])
            if sym_id is None:
                unresolved.append(row["symbol_nse"])
                continue
            resolved.append({**row, "symbol_id": sym_id})
        return resolved, unresolved

    def _stage_data(self, job_id: str, file_date: datetime.date, records: list[dict], session: Session) -> int:
        """Bulk-inserts resolved records into eod_staging_data."""
        session.execute(delete(EodStagingData).where(EodStagingData.job_id == job_id))
        rows = [
            {
                "job_id": job_id,
                "symbol_nse": r["symbol_nse"],
                "symbol_id": r["symbol_id"],
                "file_date": file_date,
                "open": r["open"],
                "high": r["high"],
                "low": r["low"],
                "close": r["close"],
                "volume": r["volume"],
                "used_for_patch": False,
            }
            for r in records
        ]
        session.bulk_insert_mappings(EodStagingData, rows)
        session.commit()
        return len(rows)

    def _compute_gap_info(self, resolved: list[dict], file_date: datetime.date, session: Session) -> dict:
        """Returns a summary of how many symbols have gap days before file_date."""
        symbol_ids = [r["symbol_id"] for r in resolved]
        rows = session.execute(
            select(DailyPrice.symbol_id, func.max(DailyPrice.trading_date))
            .where(
                DailyPrice.symbol_id.in_(symbol_ids),
                DailyPrice.trading_date < file_date,
            )
            .group_by(DailyPrice.symbol_id)
        ).all()

        last_date_map: dict[int, datetime.date] = {r[0]: r[1] for r in rows}
        has_gap = sum(
            1 for sid in symbol_ids
            if sid in last_date_map and (file_date - last_date_map[sid]).days > 1
        )
        no_history = sum(1 for sid in symbol_ids if sid not in last_date_map)
        return {
            "symbols_with_gap": has_gap,
            "symbols_with_no_history": no_history,
            "file_date": str(file_date),
        }

    def _run_yahoo_gap_fill(self, nse_symbols: list[str]) -> None:
        """Runs a scoped Yahoo Finance sync for the given symbols, filling all gaps up to today."""
        from stocks.services.sync_engine import SyncEngine
        engine = SyncEngine(self.config, self.db_manager)
        engine.run_sync(specific_symbols=nse_symbols)

    def _compute_diff(self, job_id: str, file_date: datetime.date, session: Session) -> list[dict]:
        """Returns staged records for symbols Yahoo did NOT fill for file_date."""
        staged = session.execute(
            select(
                EodStagingData.symbol_id,
                EodStagingData.symbol_nse,
                EodStagingData.open,
                EodStagingData.high,
                EodStagingData.low,
                EodStagingData.close,
                EodStagingData.volume,
            ).where(
                EodStagingData.job_id == job_id,
                EodStagingData.symbol_id != None,
            )
        ).all()

        # Which symbol_ids already have daily_prices for file_date (filled by Yahoo)?
        staged_ids = [r[0] for r in staged]
        if not staged_ids:
            return []

        yahoo_filled = set(
            session.scalars(
                select(DailyPrice.symbol_id).where(
                    DailyPrice.symbol_id.in_(staged_ids),
                    DailyPrice.trading_date == file_date,
                )
            ).all()
        )

        return [
            {
                "symbol_id": r[0],
                "symbol_nse": r[1],
                "open": float(r[2]),
                "high": float(r[3]),
                "low": float(r[4]),
                "close": float(r[5]),
                "volume": int(r[6]),
            }
            for r in staged
            if r[0] not in yahoo_filled
        ]

    def _patch_from_eod(
        self, diff_records: list[dict], file_date: datetime.date, session: Session
    ) -> list[int]:
        """Inserts EOD data into daily_prices for symbols Yahoo missed. Returns patched symbol_ids."""
        patched_ids: list[int] = []
        for rec in diff_records:
            sid = rec["symbol_id"]
            # Delete any existing row for this symbol+date (safety)
            session.execute(
                delete(DailyPrice).where(
                    DailyPrice.symbol_id == sid,
                    DailyPrice.trading_date == file_date,
                )
            )
            session.flush()
            session.bulk_insert_mappings(DailyPrice, [{
                "symbol_id": sid,
                "trading_date": file_date,
                "open": rec["open"],
                "high": rec["high"],
                "low": rec["low"],
                "close": rec["close"],
                "adj_close": rec["close"],   # EOD has no adj_close; Yahoo will correct on next sync
                "volume": rec["volume"],
                "granularity": "1d",
                "data_source": "EOD_NSE",
            }])

            # Update symbol_sync_state
            state = session.scalar(select(SymbolSyncState).filter_by(symbol_id=sid))
            if state is None:
                session.add(SymbolSyncState(
                    symbol_id=sid,
                    last_successful_sync_date=file_date,
                    last_attempt_status="SUCCESS",
                ))
            else:
                if state.last_successful_sync_date is None or file_date > state.last_successful_sync_date:
                    state.last_successful_sync_date = file_date
                state.last_attempt_status = "SUCCESS"
                state.last_error_message = None

            patched_ids.append(sid)

        if patched_ids:
            session.commit()

        # Mark staging rows as used
        if patched_ids:
            used_ids = {r["symbol_id"] for r in diff_records}
            staged_rows = session.execute(
                select(EodStagingData).where(
                    EodStagingData.symbol_id.in_(list(used_ids))
                )
            ).scalars().all()
            for row in staged_rows:
                row.used_for_patch = True
            session.commit()

        return patched_ids

    def _calculate_for_symbols(
        self, symbol_ids: list[int], file_date: datetime.date, session: Session
    ) -> None:
        """Runs incremental indicator + market-structure calculations for each patched symbol."""
        from stocks.services.database import DatabaseService
        from stocks.services.sync_engine import SyncEngine

        db_service = DatabaseService(self.config, session)
        engine = SyncEngine(self.config, self.db_manager)

        for sid in symbol_ids:
            sym = session.scalar(select(Symbol).where(Symbol.id == sid))
            if not sym:
                continue
            try:
                clean_prices = [{"trading_date": file_date}]   # min_date anchor only
                # Load actual price dict from DB so calculate_and_save_derived_data has real data
                price_row = session.scalar(
                    select(DailyPrice).where(
                        DailyPrice.symbol_id == sid,
                        DailyPrice.trading_date == file_date,
                    )
                )
                if price_row:
                    clean_prices = [{
                        "trading_date": price_row.trading_date,
                        "open": float(price_row.open),
                        "high": float(price_row.high),
                        "low": float(price_row.low),
                        "close": float(price_row.close),
                        "adj_close": float(price_row.adj_close),
                        "volume": int(price_row.volume),
                    }]
                engine.calculate_and_save_derived_data(db_service, sym, clean_prices)
            except Exception as exc:
                logger.error(f"[EOD] Calculation failed for symbol_id={sid}: {exc}")

    def _refresh_screening(self, symbol_ids: list[int], session: Session) -> None:
        """Refreshes screening snapshots, strategy signals, and trendlines."""
        try:
            from stocks.services.screening import ScreeningService
            ScreeningService(self.config, session).refresh_all_snapshots()
        except Exception as exc:
            logger.error(f"[EOD] Screening refresh failed: {exc}")
        try:
            from stocks.services.strategy_screener import StrategyScreenerService
            StrategyScreenerService(self.config, session).refresh_all_strategies()
        except Exception as exc:
            logger.error(f"[EOD] Strategy refresh failed: {exc}")
        try:
            from stocks.services.trendline_service import TrendlineService
            TrendlineService(session).refresh_all()
        except Exception as exc:
            logger.error(f"[EOD] Trendline refresh failed: {exc}")

    # ── Status helpers ──────────────────────────────────────────────────────────

    def _set_status(self, session: Session, job: EodImportJob, status: str, error: str = "") -> None:
        job.status = status
        if status == "VALIDATING":
            job.started_at = datetime.datetime.now()
        if error:
            job.error_message = error
        session.commit()

    def _fail(self, session: Session, job: EodImportJob | None, error: str) -> None:
        if job:
            job.status = "FAILED"
            job.error_message = error
            job.completed_at = datetime.datetime.now()
            session.commit()

    def _update_status_detached(self, job_id: str, status: str, error: str = "") -> None:
        """Updates job status using a fresh session (for use after session.close())."""
        s = self.db_manager.get_session()
        try:
            job = s.scalar(select(EodImportJob).where(EodImportJob.job_id == job_id))
            if job:
                job.status = status
                if error:
                    job.error_message = error
                s.commit()
        finally:
            s.close()
