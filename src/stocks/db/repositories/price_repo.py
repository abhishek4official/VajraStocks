# src/stocks/db/repositories/price_repo.py
import datetime
from typing import List, Dict, Any, Set
from sqlalchemy import select
from sqlalchemy.orm import Session
from stocks.db.models import DailyPrice, CorporateAction, SymbolSyncState

class PriceRepository:
    """Repository handling database operations for DailyPrice and CorporateAction tables."""

    def __init__(self, db: Session):
        self.db = db

    def get_existing_dates(self, symbol_id: int, start_date: datetime.date) -> Set[datetime.date]:
        """Pre-fetches all existing dates for a symbol to resolve N+1 query loops.
        
        Runs a single optimized SELECT statement instead of looping inside write transactions.
        """
        stmt = select(DailyPrice.trading_date).where(
            DailyPrice.symbol_id == symbol_id,
            DailyPrice.trading_date >= start_date
        )
        return set(self.db.scalars(stmt).all())

    def bulk_save_stock_data(
        self, symbol_id: int, prices: List[Dict[str, Any]], actions: List[Dict[str, Any]], sync_date: datetime.date
    ) -> int:
        """Saves stock daily prices and corporate actions using bulk database operations.
        
        Ensures atomic transactions and high-speed bulk insertions.
        """
        try:
            if not prices:
                return 0

            # 1. Pre-fetch existing dates in a single SELECT query
            min_date = min(p["trading_date"] for p in prices)
            existing_dates = self.get_existing_dates(symbol_id, min_date)

            # 2. Filter duplicate dates in Python memory in O(1) time
            new_prices = []
            for p in prices:
                t_date = p["trading_date"]
                if isinstance(t_date, str):
                    t_date = datetime.datetime.strptime(t_date, "%Y-%m-%d").date()
                if t_date in existing_dates:
                    continue
                new_prices.append({
                    "symbol_id": symbol_id,
                    "trading_date": t_date,
                    "open": p["open"],
                    "high": p["high"],
                    "low": p["low"],
                    "close": p["close"],
                    "adj_close": p["adj_close"],
                    "volume": p["volume"],
                    "granularity": p.get("granularity", "1d")
                })

            inserted_count = 0
            if new_prices:
                # 3. Perform high-speed SQLAlchemy bulk mapping inserts
                self.db.bulk_insert_mappings(DailyPrice, new_prices)
                inserted_count = len(new_prices)

            # 4. Save Corporate Actions similarly (Batch filtering)
            if actions:
                stmt_act = select(CorporateAction.action_date, CorporateAction.action_type).where(
                    CorporateAction.symbol_id == symbol_id
                )
                existing_actions = set(self.db.execute(stmt_act).all())

                new_actions = []
                for a in actions:
                    a_date = a["action_date"]
                    if isinstance(a_date, str):
                        a_date = datetime.datetime.strptime(a_date, "%Y-%m-%d").date()
                    act_key = (a_date, a["action_type"])
                    if act_key in existing_actions:
                        continue
                    new_actions.append({
                        "symbol_id": symbol_id,
                        "action_date": a_date,
                        "action_type": a["action_type"],
                        "value": a["value"]
                    })

                if new_actions:
                    self.db.bulk_insert_mappings(CorporateAction, new_actions)

            # 5. Update isolated sync state
            state_stmt = select(SymbolSyncState).filter_by(symbol_id=symbol_id)
            state = self.db.scalar(state_stmt)
            if state is None:
                state = SymbolSyncState(
                    symbol_id=symbol_id,
                    last_successful_sync_date=sync_date,
                    last_attempt_status="SUCCESS"
                )
                self.db.add(state)
            else:
                state.last_successful_sync_date = sync_date
                state.last_attempt_status = "SUCCESS"
                state.last_error_message = None

            self.db.commit()
            return inserted_count

        except Exception as e:
            self.db.rollback()
            raise e
