"""Utility to backfill all historical corporate actions (splits and dividends) from yFinance.

This script fetches only corporate actions (no daily prices), meaning it runs
quickly and populates any missing splits or dividends in the database.

Usage:
    # Backfill only your portfolio holdings (very fast)
    uv run python scripts/backfill_corporate_actions.py --portfolio-only

    # Backfill all active symbols in the database
    uv run python scripts/backfill_corporate_actions.py
"""

import sys
import argparse
import time
import datetime
from pathlib import Path
import yfinance as yf
from loguru import logger
from sqlalchemy import select, func

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from stocks.config import Config
from stocks.db.connection import DatabaseManager
from stocks.db.models import CorporateAction, Symbol, PortfolioHolding

def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill historical corporate actions from yFinance.")
    parser.add_argument("--portfolio-only", action="store_true", help="Only sync symbols in your portfolio holdings.")
    args = parser.parse_args()

    config_file = Path(r"C:\Users\abhis\AppData\Roaming\VajraStocks\config.yaml")
    if not config_file.exists():
        logger.error(f"Config file not found at {config_file}")
        sys.exit(1)

    config = Config.load(config_file)
    db_manager = DatabaseManager.from_config(config)
    
    try:
        db_manager.initialize()
        session = db_manager.get_session()
        
        # 1. Fetch target symbols
        if args.portfolio_only:
            logger.info("Fetching symbols in your portfolio holdings...")
            stmt = select(Symbol).join(PortfolioHolding, Symbol.id == PortfolioHolding.symbol_id)
            symbols = list(session.scalars(stmt).all())
        else:
            logger.info("Fetching all active symbols from database...")
            stmt = select(Symbol).where(Symbol.is_active == True)
            symbols = list(session.scalars(stmt).all())
            
        total_symbols = len(symbols)
        logger.info(f"Found {total_symbols} symbols to process.")
        
        processed = 0
        inserted_total = 0
        
        for idx, symbol_obj in enumerate(symbols, 1):
            ticker_str = symbol_obj.symbol
            logger.info(f"[{idx}/{total_symbols}] Processing {ticker_str}...")
            
            try:
                # Get existing actions to avoid duplicate keys
                stmt_act = select(CorporateAction.action_date, CorporateAction.action_type).where(
                    CorporateAction.symbol_id == symbol_obj.id
                )
                existing_actions = set(session.execute(stmt_act).all())
                
                # Fetch full actions history from yFinance
                ticker = yf.Ticker(ticker_str)
                actions_df = ticker.actions
                
                new_actions = []
                
                if actions_df is not None and not actions_df.empty:
                    for date_idx, row in actions_df.iterrows():
                        a_date = date_idx.date() if isinstance(date_idx, datetime.datetime) else date_idx
                        
                        # Parse dividends and splits
                        div_val = float(row["Dividends"])
                        split_val = float(row["Stock Splits"])
                        
                        if div_val > 0.0:
                            act_key = (a_date, "DIVIDEND")
                            if act_key not in existing_actions:
                                new_actions.append(
                                    CorporateAction(
                                        symbol_id=symbol_obj.id,
                                        action_date=a_date,
                                        action_type="DIVIDEND",
                                        value=div_val
                                    )
                                )
                                existing_actions.add(act_key)
                                
                        if split_val > 0.0:
                            act_key = (a_date, "SPLIT")
                            if act_key not in existing_actions:
                                new_actions.append(
                                    CorporateAction(
                                        symbol_id=symbol_obj.id,
                                        action_date=a_date,
                                        action_type="SPLIT",
                                        value=split_val
                                    )
                                )
                                existing_actions.add(act_key)
                                
                if new_actions:
                    session.add_all(new_actions)
                    session.commit()
                    inserted_total += len(new_actions)
                    logger.info(f"  -> Inserted {len(new_actions)} new corporate actions.")
                else:
                    logger.debug("  -> No new actions found.")
                    
            except Exception as e:
                session.rollback()
                logger.error(f"Failed to sync actions for {ticker_str}: {e}")
                
            processed += 1
            # Rate limiting to respect Yahoo Finance API constraints
            time.sleep(0.5)
            
        logger.success(f"Backfill complete! Processed {processed}/{total_symbols} symbols. Inserted {inserted_total} actions.")
        session.close()
        
    finally:
        db_manager.dispose()

if __name__ == "__main__":
    main()
