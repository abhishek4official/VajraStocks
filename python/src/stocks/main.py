import datetime
import sys
from pathlib import Path

import click
from loguru import logger
from sqlalchemy import select

from stocks.config import Config
from stocks.db.connection import DatabaseManager
from stocks.db.models import SyncJob
from stocks.services.database import DatabaseService
from stocks.services.symbol import SymbolService
from stocks.services.sync_engine import SyncEngine
from stocks.utils.logging import setup_logging


@click.group()
def cli():
    """NSE Historical Stock Data Downloader CLI."""
    pass


@cli.command()
@click.option("--config-path", default="config/config.yaml", help="Path to config.yaml configuration file.")
@click.option("--symbols", default=None, help="Comma-separated list of symbols to sync (e.g. RELIANCE,TCS).")
def sync(config_path: str, symbols: str):
    """Downloads historical stock data and syncs it incrementally with LocalDB."""
    config_file = Path(config_path)
    try:
        # 1. Load application config
        config = Config.load(config_file)

        # 2. Setup Logging
        setup_logging(config)
        logger.info("Initializing historical downloader synchronization...")

        # 3. Initialize Database Manager & Bootstrapper
        db_manager = DatabaseManager.from_config(config)
        db_manager.initialize()

        # 4. Parse override symbol list if provided
        specific_list = None
        if symbols:
            specific_list = [s.strip() for s in symbols.split(",") if s.strip()]

        # 5. Execute Sync Engine
        engine = SyncEngine(config, db_manager)
        result = engine.run_sync(specific_symbols=specific_list)

        logger.info(f"Sync engine run finished. Result status: {result['status']}")
        db_manager.dispose()

    except Exception as e:
        logger.critical(f"Synchronization process crashed: {e}")
        sys.exit(1)


@cli.command()
@click.option("--config-path", default="config/config.yaml", help="Path to config.yaml configuration file.")
def bootstrap_symbols(config_path: str):
    """Force refreshes the active stock symbols list from the official NSE India equities database."""
    config_file = Path(config_path)
    try:
        config = Config.load(config_file)
        setup_logging(config)
        logger.info("Bootstrapping symbol registry...")

        db_manager = DatabaseManager.from_config(config)
        db_manager.initialize()

        session = db_manager.get_session()
        symbol_service = SymbolService(config, session)

        logger.info("Requesting equities CSV list from NSE India...")
        parsed_symbols = symbol_service.fetch_active_symbols_from_nse()

        logger.info("Updating symbols table records...")
        synced = symbol_service.sync_symbols(parsed_symbols)
        logger.info(f"Bootstrap complete. {synced} active symbols are now registered in the database.")

        logger.info("Registering configured index symbols (^NSEI, ^NSEBANK, etc.)...")
        idx_count = symbol_service.ensure_indices_registered()
        if idx_count:
            logger.info(f"Registered {idx_count} new index symbol(s).")

        db_manager.dispose()
    except Exception as e:
        logger.critical(f"Symbol bootstrap operation failed: {e}")
        sys.exit(1)


@cli.command()
@click.option("--config-path", default="config/config.yaml", help="Path to config.yaml configuration file.")
@click.option("--limit", default=5, help="Number of historical sync jobs to display.")
def status(config_path: str, limit: int):
    """Displays the execution history and health of the historical data sync jobs."""
    config_file = Path(config_path)
    try:
        config = Config.load(config_file)
        setup_logging(config)

        db_manager = DatabaseManager.from_config(config)
        db_manager.initialize()

        session = db_manager.get_session()

        # Query execution history from sync_jobs
        jobs = session.scalars(select(SyncJob).order_by(SyncJob.start_time.desc()).limit(limit)).all()

        click.echo("\n" + "=" * 95)
        click.echo(f"{'Run Start Time':<22} | {'Run ID':<36} | {'Status':<10} | {'Synced Tickers':<15}")
        click.echo("=" * 95)

        for job in jobs:
            start_str = job.start_time.strftime("%Y-%m-%d %H:%M:%S")
            processed_str = f"{job.processed_symbols}/{job.total_symbols}"
            click.echo(f"{start_str:<22} | {job.run_id:<36} | {job.status:<10} | {processed_str:<15}")

        click.echo("=" * 95 + "\n")
        db_manager.dispose()

    except Exception as e:
        click.echo(f"Failed to query job execution status: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--config-path", default="config/config.yaml", help="Path to config.yaml configuration file.")
@click.option("--min-rsi", type=float, default=None, help="Filter stocks with RSI >= min-rsi.")
@click.option("--max-rsi", type=float, default=None, help="Filter stocks with RSI <= max-rsi.")
@click.option(
    "--sma-200-cross",
    type=click.Choice(["ABOVE", "BELOW"], case_sensitive=False),
    default=None,
    help="Filter by SMA 200 crossover direction.",
)
@click.option(
    "--ha-dir",
    type=click.Choice(["UP", "DOWN"], case_sensitive=False),
    default=None,
    help="Filter by Heikin-Ashi candle direction.",
)
@click.option(
    "--renko-dir",
    type=click.Choice(["UP", "DOWN"], case_sensitive=False),
    default=None,
    help="Filter by latest Renko brick direction.",
)
@click.option(
    "--lb-dir",
    type=click.Choice(["UP", "DOWN"], case_sensitive=False),
    default=None,
    help="Filter by latest Line Break line direction.",
)
@click.option("--limit", default=50, help="Maximum number of symbols to output.")
def screen(
    config_path: str,
    min_rsi: float,
    max_rsi: float,
    sma_200_cross: str,
    ha_dir: str,
    renko_dir: str,
    lb_dir: str,
    limit: int,
):
    """Executes high-speed screening sweeps directly against the pre-compiled snapshots."""
    config_file = Path(config_path)
    try:
        config = Config.load(config_file)
        setup_logging(config)

        db_manager = DatabaseManager.from_config(config)
        db_manager.initialize()

        session = db_manager.get_session()
        from stocks.services.screening import ScreeningService

        screening_service = ScreeningService(config, session)
        results = screening_service.query_screener(
            min_rsi=min_rsi,
            max_rsi=max_rsi,
            sma_200_cross=sma_200_cross,
            ha_dir=ha_dir,
            renko_dir=renko_dir,
            lb_dir=lb_dir,
            limit=limit,
        )

        click.echo("\n" + "=" * 115)
        click.echo(
            f"{'Symbol':<12} | {'Close':<10} | {'Change %':<10} | {'RSI 14':<8} | {'HA Candle':<9} | {'SMA 200':<8} | {'Renko':<7} | {'Line Break':<10}"
        )
        click.echo("=" * 115)

        for snap in results:
            change_str = f"{snap.price_pct_change:+.2f}%" if snap.price_pct_change is not None else "N/A"
            rsi_str = f"{snap.rsi_14:.2f}" if snap.rsi_14 is not None else "N/A"
            sma200_str = snap.sma_200_cross_direction if snap.sma_200_cross_direction else "N/A"
            renko_str = snap.renko_direction if snap.renko_direction else "N/A"
            lb_str = snap.line_break_direction if snap.line_break_direction else "N/A"

            click.echo(
                f"{snap.symbol:<12} | "
                f"{snap.close_price:<10.2f} | "
                f"{change_str:<10} | "
                f"{rsi_str:<8} | "
                f"{snap.ha_direction:<9} | "
                f"{sma200_str:<8} | "
                f"{renko_str:<7} | "
                f"{lb_str:<10}"
            )

        click.echo("=" * 115)
        click.echo(f"Total matching symbols displayed: {len(results)}\n")
        db_manager.dispose()

    except Exception as e:
        click.echo(f"Failed to execute screening command: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--config-path", default="config/config.yaml", help="Path to config.yaml configuration file.")
def refresh_snapshots(config_path: str):
    """Manually triggers a complete rebuild of the screening snapshots table."""
    config_file = Path(config_path)
    try:
        config = Config.load(config_file)
        setup_logging(config)

        db_manager = DatabaseManager.from_config(config)
        db_manager.initialize()

        session = db_manager.get_session()
        from stocks.services.screening import ScreeningService

        screening_service = ScreeningService(config, session)
        count = screening_service.refresh_all_snapshots()
        click.echo(f"Successfully rebuilt {count} screening snapshots.")
        db_manager.dispose()
    except Exception as e:
        click.echo(f"Failed to manually refresh snapshots: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--config-path", default="config/config.yaml", help="Path to config.yaml configuration file.")
@click.option(
    "--symbols", default=None, help="Comma-separated list of specific symbols to recalculate (e.g. RELIANCE,TCS)."
)
@click.option("--limit", type=int, default=None, help="Limit the number of symbols to process (useful for testing).")
def recalculate_derived(config_path: str, symbols: str, limit: int | None):
    """Recalculates technical indicators and market structures from historical prices stored in DB."""
    config_file = Path(config_path)
    try:
        config = Config.load(config_file)
        setup_logging(config)

        db_manager = DatabaseManager.from_config(config)
        db_manager.initialize()

        session = db_manager.get_session()
        db_service = DatabaseService(config, session)
        sync_engine = SyncEngine(config, db_manager)

        # 1. Fetch active symbols
        active_symbols = db_service.get_active_symbols()

        if symbols:
            target_symbols = [s.strip().upper() for s in symbols.split(",") if s.strip()]
            target_symbols_ns = [
                f"{s}.NS" if not s.endswith(".NS") and not s.startswith("^") else s for s in target_symbols
            ]
            active_symbols = [s for s in active_symbols if s.symbol in target_symbols_ns]
            logger.info(f"Restricting recalculation to {len(active_symbols)} requested symbols.")

        if limit:
            active_symbols = active_symbols[:limit]
            logger.info(f"Limiting processing to {len(active_symbols)} symbols.")

        total = len(active_symbols)
        logger.info(f"Starting historical derived data recalculation for {total} symbols...")

        from sqlalchemy import delete

        from stocks.db.models import DailyHeikinAshi, DailyIndicator, LineBreakLine, RenkoBrick

        processed = 0
        failed = 0

        for idx, symbol_obj in enumerate(active_symbols, 1):
            logger.info(f"[{idx}/{total}] Processing {symbol_obj.symbol}...")
            try:
                # Clear all existing derived data to guarantee clean cold start calculations
                session.execute(delete(DailyIndicator).where(DailyIndicator.symbol_id == symbol_obj.id))
                session.execute(delete(DailyHeikinAshi).where(DailyHeikinAshi.symbol_id == symbol_obj.id))
                session.execute(delete(RenkoBrick).where(RenkoBrick.symbol_id == symbol_obj.id))
                session.execute(delete(LineBreakLine).where(LineBreakLine.symbol_id == symbol_obj.id))
                session.commit()

                # Fetch all prices in DB
                prices = db_service.get_prices_for_window(symbol_obj.id, datetime.date(1970, 1, 1))
                if not prices:
                    logger.warning(f"[{symbol_obj.symbol}] No historical prices found in database. Skipping.")
                    continue

                # Run derived sync engine method
                sync_engine.calculate_and_save_derived_data(db_service, symbol_obj, prices)
                processed += 1
            except Exception as err:
                failed += 1
                logger.error(f"[{symbol_obj.symbol}] Failed to recalculate derived data: {err}")

        # 2. Refresh snapshots
        logger.info("Recalculation complete. Rebuilding screening snapshots table...")
        from stocks.services.screening import ScreeningService

        screening_service = ScreeningService(config, session)
        screening_service.refresh_all_snapshots()

        logger.info("Materializing strategy signals (all strategies)...")
        from stocks.services.strategy_screener import StrategyScreenerService

        StrategyScreenerService(config, session).refresh_all_strategies()

        logger.info(f"Derived data recalculation run finished. Processed: {processed}, Failed: {failed}")
        db_manager.dispose()
    except Exception as e:
        logger.critical(f"Recalculation process crashed: {e}")
        sys.exit(1)


@cli.command()
@click.option("--config-path", default="config/config.yaml", help="Path to config.yaml configuration file.")
@click.option("--strategy", default=None, help="Strategy id to materialize (default: registered default).")
def recalculate_strategy(config_path: str, strategy: str | None):
    """Rebuilds the materialized strategy_signals table from prices already in the DB.

    Useful after deploying a new strategy version without re-running a full sync.
    """
    config_file = Path(config_path)
    try:
        config = Config.load(config_file)
        setup_logging(config)

        db_manager = DatabaseManager.from_config(config)
        db_manager.initialize()
        session = db_manager.get_session()

        from stocks.services.strategies.registry import DEFAULT_STRATEGY_ID
        from stocks.services.strategy_screener import StrategyScreenerService

        strategy_id = strategy or DEFAULT_STRATEGY_ID
        logger.info(f"Materializing strategy signals for '{strategy_id}'...")
        count = StrategyScreenerService(config, session).refresh_all_signals(strategy_id)
        logger.info(f"Strategy signal materialization finished. {count} signals written.")
        db_manager.dispose()
    except Exception as e:
        logger.critical(f"Strategy recalculation crashed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    cli()
