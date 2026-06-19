import datetime
from typing import Any

from loguru import logger

from stocks.config import Config
from stocks.db.connection import DatabaseManager
from stocks.services.database import DatabaseService
from stocks.services.downloader import DownloaderService
from stocks.services.symbol import SymbolService
from stocks.services.validation import ValidationService


# ── Pure worker function ───────────────────────────────────────────────────────
# Module-level so it is picklable for ProcessPoolExecutor.
# All heavy imports are lazy (inside the body) so spawned worker processes do
# not trigger DB-connection imports during module initialisation.

def calculate_derived_data_in_memory(
    symbol_id: int,
    symbol: str,
    prices: list[dict[str, Any]],
) -> dict[str, Any]:
    """CPU-bound indicator calculation with zero DB access.

    Inputs and outputs are standard Python types (dict, list, float, str,
    datetime.date) so they are fully picklable across process boundaries.

    Returns:
        {
            "symbol_id": int,
            "symbol": str,
            "indicators": [...],    # list of indicator row dicts
            "ha_candles": [...],    # list of Heikin-Ashi row dicts
            "renko_bricks": [...],
            "line_breaks":  [...],
        }
    """
    import pandas as pd
    from stocks.config import Config as _Config
    from stocks.services.indicator_engine import IndicatorEngine
    from stocks.services.market_structure import MarketStructureEngine

    empty: dict[str, Any] = {
        "symbol_id": symbol_id, "symbol": symbol,
        "indicators": [], "ha_candles": [], "renko_bricks": [], "line_breaks": [],
    }
    if not prices:
        return empty

    # Engines store config but do not read any config values in their methods
    _cfg = _Config()
    indicator_engine = IndicatorEngine(_cfg)
    market_structure_engine = MarketStructureEngine(_cfg)

    df = pd.DataFrame(prices)
    df.set_index(pd.to_datetime(df["trading_date"]), inplace=True)
    df.sort_index(inplace=True)

    try:
        df_ind = indicator_engine.calculate_indicators(df)
    except Exception as exc:
        raise RuntimeError(f"[{symbol}] Indicator calculation failed: {exc}") from exc

    def _f(val: Any) -> float | None:
        return None if pd.isna(val) else float(val)

    def _b(val: Any) -> bool | None:
        try:
            return None if pd.isna(val) else bool(val)
        except (TypeError, ValueError):
            return None

    def _s(val: Any) -> str | None:
        if val is None:
            return None
        try:
            return None if pd.isna(val) else str(val)
        except (TypeError, ValueError):
            return str(val)

    indicators: list[dict[str, Any]] = []
    for idx, row in df_ind.iterrows():
        indicators.append({
            "trading_date":           idx.date(),
            "rsi_14":                 _f(row.get("rsi_14")),
            "atr_14":                 _f(row.get("atr_14")),
            "sma_20":                 _f(row.get("sma_20")),
            "sma_50":                 _f(row.get("sma_50")),
            "sma_200":                _f(row.get("sma_200")),
            "ema_9":                  _f(row.get("ema_9")),
            "ema_20":                 _f(row.get("ema_20")),
            "ema_21":                 _f(row.get("ema_21")),
            "macd_line":              _f(row.get("macd_line")),
            "macd_signal":            _f(row.get("macd_signal")),
            "macd_histogram":         _f(row.get("macd_histogram")),
            "bb_upper":               _f(row.get("bb_upper")),
            "bb_middle":              _f(row.get("bb_middle")),
            "bb_lower":               _f(row.get("bb_lower")),
            "adx_14":                 _f(row.get("adx_14")),
            "plus_di":                _f(row.get("plus_di")),
            "minus_di":               _f(row.get("minus_di")),
            "obv":                    _f(row.get("obv")),
            "supertrend":             _f(row.get("supertrend")),
            "supertrend_dir":         _s(row.get("supertrend_dir")),
            "stoch_k":                _f(row.get("stoch_k")),
            "stoch_d":                _f(row.get("stoch_d")),
            "cmf_20":                 _f(row.get("cmf_20")),
            "stochrsi_k":             _f(row.get("stochrsi_k")),
            "stochrsi_d":             _f(row.get("stochrsi_d")),
            "stochrsi_bullish_xover": _b(row.get("stochrsi_bullish_xover")),
            "stochrsi_bearish_xover": _b(row.get("stochrsi_bearish_xover")),
        })

    # Cold-start: full historical price series is always passed for recalculate
    ha_candles:   list[dict[str, Any]] = market_structure_engine.generate_heikin_ashi(df)
    renko_bricks: list[dict[str, Any]] = market_structure_engine.generate_renko_bricks(df)
    line_breaks:  list[dict[str, Any]] = market_structure_engine.generate_line_breaks(df)

    return {
        "symbol_id":    symbol_id,
        "symbol":       symbol,
        "indicators":   indicators,
        "ha_candles":   ha_candles,
        "renko_bricks": renko_bricks,
        "line_breaks":  line_breaks,
    }


class SyncEngine:
    """Orchestrator to run, monitor, and resume stock data sync jobs using distinct sub-services."""

    def __init__(self, config: Config, db_manager: DatabaseManager):
        self.config = config
        self.db_manager = db_manager
        self.downloader = DownloaderService(config)
        self.validator = ValidationService(config)

    def run_sync(self, specific_symbols: list[str] = None) -> dict[str, Any]:
        """Runs a complete historical download sync, with resumable incremental updates."""
        session = self.db_manager.get_session()
        db_service = DatabaseService(self.config, session)

        # 1. Prune existing zero-volume (holiday/halt) records and clean up orphaned indicators/HA candles
        db_service.prune_zero_volume_records()

        symbol_service = SymbolService(self.config, session)

        # 2. Initialize Sync Job in database
        job = db_service.create_sync_job()
        logger.info(f"Started synchronization job. Run ID: {job.run_id}")

        total_symbols = 0
        processed_symbols = 0
        failed_symbols = 0
        records_inserted = 0
        err_summary_list = []

        try:
            # 2. Bootstrap Symbol Universe if database is empty
            active_symbols = db_service.get_active_symbols()
            if not active_symbols:
                logger.info("Database is empty. Bootstrapping symbol universe from active equities list...")
                parsed_nse_symbols = symbol_service.fetch_active_symbols_from_nse()
                symbol_service.sync_symbols(parsed_nse_symbols)
                # Re-query active symbols
                active_symbols = db_service.get_active_symbols()

            # Ensure all configured index symbols (^NSEI, ^NSEBANK, etc.) exist in the DB.
            # Indices are never in the NSE equities CSV so they must be seeded separately.
            symbol_service.ensure_indices_registered()
            # Re-query so newly registered indices are visible
            active_symbols = db_service.get_active_symbols()

            # Filter by specific symbols if provided (useful for manual runs/testing/CLI arguments)
            if specific_symbols:
                # Standardize symbols to append .NS if they are raw (e.g. RELIANCE -> RELIANCE.NS)
                target_symbols = []
                for s in specific_symbols:
                    s_clean = s.strip().upper()
                    if not s_clean.endswith(".NS") and not s_clean.startswith("^"):
                        s_clean = f"{s_clean}.NS"
                    target_symbols.append(s_clean)
                active_symbols = [s for s in active_symbols if s.symbol in target_symbols]
                logger.info(f"Manual override: Restricting sync to {len(active_symbols)} requested symbols.")

            total_symbols = len(active_symbols)
            if total_symbols == 0:
                logger.info("No active symbols to sync.")
                db_service.finalize_sync_job(job.id, 0, 0, 0, "SUCCESS", "No symbols provided.")
                return {"status": "SUCCESS", "job_id": job.run_id}

            logger.info(f"Beginning sync process for {total_symbols} active symbols...")

            # Query ground truth latest global trading date before incremental update logic
            global_max_date = db_service.get_global_latest_price_date()
            logger.info(f"Verified global market database benchmark trading date: {global_max_date}")

            # 3. Determine dynamic date ranges and collect symbols requiring updates
            symbols_to_sync = []  # List of tuples: (Symbol, start_date, end_date)
            today = datetime.date.today()
            history_start = today - datetime.timedelta(days=365 * self.config.downloader.history_years)

            for symbol_obj in active_symbols:
                latest_price_date = db_service.get_latest_price_date(symbol_obj.id)

                # Check for existing prices in the database
                if latest_price_date:
                    # Warm Sync (Incremental) - start from the last price date (inclusive)
                    # to force overwrite and fill in missing/partial EOD prices
                    start_date = latest_price_date
                else:
                    # Cold Start - full history backfill
                    start_date = history_start

                end_date = today

                # If already up to date, skip downloading
                if start_date >= end_date:
                    logger.debug(
                        f"[{symbol_obj.symbol}] Already up to date (latest price date: "
                        f"{latest_price_date}). Skipping download."
                    )
                    processed_symbols += 1
                    continue

                symbols_to_sync.append((symbol_obj, start_date, end_date))

            total_pending = len(symbols_to_sync)
            logger.info(
                f"Incremental Sync Check: {total_symbols - total_pending} symbols already up-to-date. "
                f"{total_pending} symbols require sync."
            )

            if total_pending == 0:
                logger.info("All active symbols are fully up-to-date. Sync process completed.")
                db_service.finalize_sync_job(job.id, total_symbols, processed_symbols, 0, "SUCCESS")
                return {
                    "status": "SUCCESS",
                    "job_id": job.run_id,
                    "total_symbols": total_symbols,
                    "processed_symbols": processed_symbols,
                    "failed_symbols": 0,
                    "records_inserted": 0,
                }

            # 4. Group symbols requiring sync by their target date bounds to optimize batching.
            range_groups = {}
            for item in symbols_to_sync:
                key = (item[1], item[2])
                if key not in range_groups:
                    range_groups[key] = []
                range_groups[key].append(item[0])

            # 5. Process each date range group in batches
            batch_size = min(50, self.config.downloader.batch_size)

            for (start_date, end_date), symbols_list in range_groups.items():
                logger.info(
                    f"Processing group with date window {start_date} to {end_date} "
                    f"containing {len(symbols_list)} symbols..."
                )

                # Split this group's symbols into downloader batches
                for chunk_idx in range(0, len(symbols_list), batch_size):
                    # Check for job cancellation
                    if db_service.is_sync_job_cancelled(job.id):
                        logger.warning(f"Sync job {job.run_id} cancelled by user.")
                        db_service.finalize_sync_job(
                            job.id, total_symbols, processed_symbols, failed_symbols, "CANCELLED", "Cancelled by user request."
                        )
                        return {
                            "status": "CANCELLED",
                            "job_id": job.run_id,
                            "total_symbols": total_symbols,
                            "processed_symbols": processed_symbols,
                            "failed_symbols": failed_symbols,
                            "records_inserted": records_inserted,
                        }
                    chunk = symbols_list[chunk_idx : chunk_idx + batch_size]
                    tickers_chunk = [s.symbol for s in chunk]
                    symbols_by_ticker = {s.symbol: s for s in chunk}

                    try:
                        # Attempt bulk batch download
                        batch_df = self.downloader.fetch_batch_data(tickers_chunk, start_date, end_date)
                        batch_results = self.downloader.parse_downloaded_data(batch_df, tickers_chunk)

                        # Process individual ticker data from the batch response
                        for ticker, (prices, actions) in batch_results.items():
                            symbol_obj = symbols_by_ticker[ticker]

                            try:
                                # Data quality validation
                                clean_prices = self.validator.validate_prices(ticker, prices, actions)

                                # Ingestion within isolated transaction
                                inserted = db_service.save_stock_data(symbol_obj.id, clean_prices, actions, end_date)

                                # Post-sync resilient downloader verification
                                is_valid = self._verify_and_update_symbol_sync_state(
                                    db_service, symbol_obj, ticker, global_max_date
                                )

                                if is_valid:
                                    records_inserted += inserted
                                    processed_symbols += 1
                                    logger.info(f"[{ticker}] Synced successfully. {inserted} rows added.")

                                    # Post-sync hook: Incremental Indicator & Market Structure recalculations
                                    try:
                                        self.calculate_and_save_derived_data(db_service, symbol_obj, clean_prices)
                                    except Exception as derived_err:
                                        logger.error(
                                            f"[{ticker}] Failed to calculate or save derived data: {derived_err}"
                                        )

                                    # Post-sync hook: Option B conditional news/fundamentals
                                    self.sync_news_and_fundamentals_if_stale(session, symbol_obj, ticker)
                                else:
                                    failed_symbols += 1
                                    err_summary_list.append(
                                        f"[{ticker}] Yahoo Finance returned no data (behind global market date)."
                                    )

                            except Exception as e:
                                failed_symbols += 1
                                err_summary_list.append(f"[{ticker}] Ingestion failed: {e}")

                    except Exception as batch_err:
                        logger.error(
                            f"Bulk batch download failed for tickers {tickers_chunk}: {batch_err}. "
                            f"Falling back to individual downloads..."
                        )

                        # Resilient Fallback: Download each ticker in the chunk individually
                        for symbol_obj in chunk:
                            if db_service.is_sync_job_cancelled(job.id):
                                logger.warning(f"Sync job {job.run_id} cancelled by user during fallback.")
                                db_service.finalize_sync_job(
                                    job.id, total_symbols, processed_symbols, failed_symbols, "CANCELLED", "Cancelled by user request."
                                )
                                return {
                                    "status": "CANCELLED",
                                    "job_id": job.run_id,
                                    "total_symbols": total_symbols,
                                    "processed_symbols": processed_symbols,
                                    "failed_symbols": failed_symbols,
                                    "records_inserted": records_inserted,
                                }
                            ticker = symbol_obj.symbol
                            try:
                                # Fetch individually
                                single_df = self.downloader.fetch_batch_data([ticker], start_date, end_date)
                                single_results = self.downloader.parse_downloaded_data(single_df, [ticker])
                                prices, actions = single_results.get(ticker, ([], []))

                                # Validate & Save
                                clean_prices = self.validator.validate_prices(ticker, prices, actions)
                                inserted = db_service.save_stock_data(symbol_obj.id, clean_prices, actions, end_date)

                                # Post-sync resilient downloader verification
                                is_valid = self._verify_and_update_symbol_sync_state(
                                    db_service, symbol_obj, ticker, global_max_date
                                )

                                if is_valid:
                                    records_inserted += inserted
                                    processed_symbols += 1
                                    logger.info(
                                        f"[{ticker}] Synced successfully (via fallback). {inserted} rows added."
                                    )

                                    # Post-sync hook: Incremental Indicator & Market Structure recalculations
                                    try:
                                        self.calculate_and_save_derived_data(db_service, symbol_obj, clean_prices)
                                    except Exception as derived_err:
                                        logger.error(
                                            f"[{ticker}] Failed to calculate or save derived data: {derived_err}"
                                        )

                                    # Post-sync hook: Option B conditional news/fundamentals
                                    self.sync_news_and_fundamentals_if_stale(session, symbol_obj, ticker)
                                else:
                                    failed_symbols += 1
                                    err_summary_list.append(
                                        f"[{ticker}] Fallback failed: Yahoo Finance returned no data (behind global market date)."
                                    )
                            except Exception as single_err:
                                failed_symbols += 1
                                err_summary_list.append(f"[{ticker}] Individual fallback failed: {single_err}")
                                logger.error(f"[{ticker}] Fallback sync failed: {single_err}")

                    # Update progress in database after each batch
                    db_service.update_sync_job_progress(job.id, processed_symbols, failed_symbols, records_inserted)

            # Post-Sync Hook: Refresh Screening Snapshots for high-speed dashboards/screening
            try:
                from stocks.services.screening import ScreeningService

                screening_service = ScreeningService(self.config, session)
                screening_service.refresh_all_snapshots()
            except Exception as snap_err:
                logger.error(f"Failed to refresh screening snapshots post-sync: {snap_err}")

            # Post-Sync Hook: Materialize strategy signals (Pre-Breakout) for the Strategy screen.
            # Runs after snapshots so market-breadth (% above 200DMA) is available.
            try:
                from stocks.services.strategy_screener import StrategyScreenerService

                StrategyScreenerService(self.config, session).refresh_all_strategies()
            except Exception as strat_err:
                logger.error(f"Failed to materialize strategy signals post-sync: {strat_err}")

            # Post-Sync Hook: Run VajraML2 (triple-barrier) predictions.
            # V2 is the primary ML signal — writes ml2_* AND the shared ml_label/ml_rank/ml_prediction columns.
            try:
                import sys
                from pathlib import Path as _Path

                _vajra_root = str(_Path(__file__).parents[4])
                if _vajra_root not in sys.path:
                    sys.path.insert(0, _vajra_root)

                from VajraML2.predict import run_ml2_snapshot_update

                run_ml2_snapshot_update(self.db_manager.engine)
            except Exception as ml2_err:
                logger.error(f"Failed to run VajraML2 V2 snapshot update post-sync: {ml2_err}")

            # 6. Finalize Sync Job status
            final_status = "SUCCESS"
            if failed_symbols > 0:
                final_status = "PARTIAL" if processed_symbols > 0 else "FAILED"

            error_summary = "\n".join(err_summary_list[:20])  # Cap summary size in database
            if len(err_summary_list) > 20:
                error_summary += f"\n... and {len(err_summary_list) - 20} more errors."

            db_service.finalize_sync_job(
                job.id, total_symbols, processed_symbols, failed_symbols, final_status, error_summary or None
            )

            logger.info(
                f"Sync Job finalized. Status: {final_status}. "
                f"Total active symbols: {total_symbols}, Synced/Skipped: {processed_symbols}, Failed: {failed_symbols}, "
                f"Total Rows Inserted: {records_inserted}."
            )

            return {
                "status": final_status,
                "job_id": job.run_id,
                "total_symbols": total_symbols,
                "processed_symbols": processed_symbols,
                "failed_symbols": failed_symbols,
                "records_inserted": records_inserted,
            }

        except Exception as e:
            logger.critical(f"Critical failure in sync engine: {e}")
            db_service.finalize_sync_job(
                job.id, total_symbols, processed_symbols, failed_symbols, "FAILED", f"Critical engine crash: {e}"
            )
            raise e
        finally:
            session.close()

    def calculate_and_save_derived_data(
        self, db_service: DatabaseService, symbol_obj: Any, clean_prices: list[dict[str, Any]],
        commit: bool = True,
    ) -> None:
        """Calculates indicators and market structures incrementally and saves them in isolated transactions."""
        if not clean_prices:
            return

        import pandas as pd

        from stocks.services.indicator_engine import IndicatorEngine
        from stocks.services.market_structure import MarketStructureEngine

        # Initialize engines
        indicator_engine = IndicatorEngine(self.config)
        market_structure_engine = MarketStructureEngine(self.config)

        # 1. Determine date boundaries for sliding window
        new_dates = [p["trading_date"] for p in clean_prices]
        min_date = min(new_dates)

        # Load sliding window from DB: min_date - 300 days
        sliding_start = min_date - datetime.timedelta(days=300)
        db_prices = db_service.get_prices_for_window(symbol_obj.id, sliding_start)

        if not db_prices:
            logger.warning(f"[{symbol_obj.symbol}] No prices found in sliding window to calculate derived data.")
            return

        # Convert to DataFrame
        df_prices = pd.DataFrame(db_prices)
        df_prices.set_index(pd.to_datetime(df_prices["trading_date"]), inplace=True)
        df_prices.sort_index(inplace=True)

        # 2. Technical Indicators
        df_indicators = indicator_engine.calculate_indicators(df_prices)

        # Slice only the newly synced dates to save
        df_new_indicators = df_indicators[df_indicators.index.date >= min_date]
        indicators_to_save = []
        for idx, row in df_new_indicators.iterrows():
            t_date = idx.date()
            ind_dict = {
                "trading_date": t_date,
                "rsi_14": None if pd.isna(row.get("rsi_14")) else float(row["rsi_14"]),
                "atr_14": None if pd.isna(row.get("atr_14")) else float(row["atr_14"]),
                "sma_20": None if pd.isna(row.get("sma_20")) else float(row["sma_20"]),
                "sma_50": None if pd.isna(row.get("sma_50")) else float(row["sma_50"]),
                "sma_200": None if pd.isna(row.get("sma_200")) else float(row["sma_200"]),
                "ema_9":  None if pd.isna(row.get("ema_9"))  else float(row["ema_9"]),
                "ema_20": None if pd.isna(row.get("ema_20")) else float(row["ema_20"]),
                "ema_21": None if pd.isna(row.get("ema_21")) else float(row["ema_21"]),
                "macd_line": None if pd.isna(row.get("macd_line")) else float(row["macd_line"]),
                "macd_signal": None if pd.isna(row.get("macd_signal")) else float(row["macd_signal"]),
                "macd_histogram": None if pd.isna(row.get("macd_histogram")) else float(row["macd_histogram"]),
                "bb_upper": None if pd.isna(row.get("bb_upper")) else float(row["bb_upper"]),
                "bb_middle": None if pd.isna(row.get("bb_middle")) else float(row["bb_middle"]),
                "bb_lower": None if pd.isna(row.get("bb_lower")) else float(row["bb_lower"]),
                "adx_14":   None if pd.isna(row.get("adx_14"))   else float(row["adx_14"]),
                "plus_di":  None if pd.isna(row.get("plus_di"))   else float(row["plus_di"]),
                "minus_di": None if pd.isna(row.get("minus_di"))  else float(row["minus_di"]),
                "obv":      None if pd.isna(row.get("obv"))       else float(row["obv"]),
                "supertrend":     None if pd.isna(row.get("supertrend"))     else float(row["supertrend"]),
                "supertrend_dir": None if (row.get("supertrend_dir") is None or (isinstance(row.get("supertrend_dir"), float) and pd.isna(row.get("supertrend_dir")))) else str(row["supertrend_dir"]),
                "stoch_k":  None if pd.isna(row.get("stoch_k"))   else float(row["stoch_k"]),
                "stoch_d":  None if pd.isna(row.get("stoch_d"))   else float(row["stoch_d"]),
                "cmf_20":   None if pd.isna(row.get("cmf_20"))    else float(row["cmf_20"]),
                "stochrsi_k": None if pd.isna(row.get("stochrsi_k")) else float(row["stochrsi_k"]),
                "stochrsi_d": None if pd.isna(row.get("stochrsi_d")) else float(row["stochrsi_d"]),
                "stochrsi_bullish_xover": None if pd.isna(row.get("stochrsi_bullish_xover")) else bool(row["stochrsi_bullish_xover"]),
                "stochrsi_bearish_xover": None if pd.isna(row.get("stochrsi_bearish_xover")) else bool(row["stochrsi_bearish_xover"]),
            }
            indicators_to_save.append(ind_dict)

        # 3. Heikin-Ashi Candles
        # Load previous candle seed
        prev_ha_candle = db_service.get_latest_heikin_ashi(symbol_obj.id)
        # We calculate HA for only the new prices.
        # But wait! If we have a seed, we pass only the new prices to generate_heikin_ashi.
        # If we DO NOT have a seed, we should pass the entire historical prices to get standard Heikin-Ashi.
        if prev_ha_candle:
            df_new_prices = df_prices[df_prices.index.date >= min_date]
            ha_candles_to_save = market_structure_engine.generate_heikin_ashi(df_new_prices, prev_candle=prev_ha_candle)
        else:
            ha_candles_to_save = market_structure_engine.generate_heikin_ashi(df_prices)

        # 4. Renko Bricks
        last_brick = db_service.get_latest_renko_brick(symbol_obj.id)
        if last_brick:
            df_new_prices = df_prices[df_prices.index.date >= min_date]
            renko_bricks_to_save = market_structure_engine.generate_renko_bricks(df_new_prices, last_brick=last_brick)
        else:
            # Cold start: calculate Renko bricks for the full historical prices
            renko_bricks_to_save = market_structure_engine.generate_renko_bricks(df_prices)

        # 5. Line Break Lines
        last_lines = db_service.get_latest_line_break_lines(symbol_obj.id, count=3)
        if last_lines:
            df_new_prices = df_prices[df_prices.index.date >= min_date]
            line_breaks_to_save = market_structure_engine.generate_line_breaks(df_new_prices, last_lines=last_lines)
        else:
            # Cold start: calculate Line Break lines for the full historical prices
            line_breaks_to_save = market_structure_engine.generate_line_breaks(df_prices)

        # Save everything to the database in an isolated transaction
        db_service.save_derived_structures(
            symbol_id=symbol_obj.id,
            indicators=indicators_to_save,
            ha_candles=ha_candles_to_save,
            renko_bricks=renko_bricks_to_save,
            line_breaks=line_breaks_to_save,
            commit=commit,
        )
        logger.info(
            f"[{symbol_obj.symbol}] Calculated and saved derived data: "
            f"{len(indicators_to_save)} indicators, {len(ha_candles_to_save)} HA candles, "
            f"{len(renko_bricks_to_save)} Renko bricks, {len(line_breaks_to_save)} Line Break lines."
        )

        try:
            from stocks.services.quant.confluence_service import ConfluenceService
            confluence_service = ConfluenceService(db_service.db)
            confluence_service.calculate_and_save_levels(symbol_obj.id)
        except Exception as confluence_err:
            logger.error(f"[{symbol_obj.symbol}] Failed to calculate or save confluence levels: {confluence_err}")

    def _verify_and_update_symbol_sync_state(
        self, db_service: DatabaseService, symbol_obj: Any, ticker: str, global_max_date: datetime.date | None
    ) -> bool:
        """Verifies if the sync successfully fetched data up to the global market date.

        If the symbol remains behind the global benchmark date (or has no price data at all),
        it updates the SymbolSyncState to FAILED with a clear warning/audit triage message.

        Returns True if successful/valid, False if failed.
        """
        post_sync_latest = db_service.get_latest_price_date(symbol_obj.id)

        # 1. Cold Start failure (No data fetched at all)
        if post_sync_latest is None:
            err_msg = "Yahoo Finance returned absolutely no pricing data for history setup."
            logger.warning(f"[{ticker}] Sync verification failed: {err_msg}")
            db_service.update_symbol_sync_failure(symbol_obj.id, err_msg)
            return False

        # 2. Gap/Lag failure (Stock is behind the global market latest trading date)
        if global_max_date is not None and post_sync_latest < global_max_date:
            err_msg = (
                f"Yahoo Finance returned no new data. Ticker remains at {post_sync_latest}, "
                f"which is behind the global benchmark date {global_max_date}."
            )
            logger.warning(f"[{ticker}] Sync verification failed: {err_msg}")
            db_service.update_symbol_sync_failure(symbol_obj.id, err_msg)
            return False

        return True

    def sync_news_and_fundamentals_if_stale(
        self, session, symbol_obj: Any, ticker: str
    ) -> None:
        """Fetch and store news and fundamentals only if missing or stale (Option B)."""
        try:
            import sys
            if "pytest" in sys.modules:
                return

            from sqlalchemy import select
            from sqlalchemy.orm import Session
            from stocks.db.models import NewsItem
            from stocks.services.fundamentals_service import FundamentalsService
            from stocks.services.news_service import NewsService

            clean_symbol = ticker.replace(".NS", "").upper()

            # 1. Fundamentals (get_or_fetch automatically caches for 7 days)
            fundamentals_svc = FundamentalsService(session)
            fundamentals_svc.get_or_fetch(symbol_obj.id, clean_symbol)

            # 2. News (fetch if missing or if the latest fetch is older than 24 hours)
            latest_news = session.scalar(
                select(NewsItem)
                .where(NewsItem.symbol == clean_symbol)
                .order_by(NewsItem.fetched_at.desc())
                .limit(1)
            )

            should_fetch_news = True
            if latest_news:
                age_hours = (datetime.datetime.now() - latest_news.fetched_at).total_seconds() / 3600.0
                if age_hours < 24.0:
                    should_fetch_news = False

            if should_fetch_news:
                NewsService(session).fetch_and_store(clean_symbol)

        except Exception as info_err:
            logger.error(f"[{ticker}] Failed to sync news/fundamentals: {info_err}")
