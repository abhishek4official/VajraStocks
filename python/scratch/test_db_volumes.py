import sys
import os
sys.path.append(os.path.abspath("src"))

from stocks.config import Config
from stocks.db.connection import DatabaseManager
from stocks.db.models import ScreeningSnapshot, DailyPrice
from sqlalchemy import select, func

def main():
    config = Config.load()
    db_manager = DatabaseManager(config)
    db_manager.initialize()
    
    session = db_manager.get_session()
    
    try:
        # Check active symbols in snapshots
        snapshots = session.scalars(select(ScreeningSnapshot)).all()
        print(f"Total screening snapshots: {len(snapshots)}")
        
        if not snapshots:
            print("No screening snapshots found in the database. Please run a sync or import data first!")
            return
            
        symbol_ids = [s.symbol_id for s in snapshots]
        
        # Pull 6 EOD price history rows
        subq = select(
            DailyPrice.symbol_id,
            DailyPrice.volume,
            DailyPrice.trading_date,
            func.row_number().over(
                partition_by=DailyPrice.symbol_id,
                order_by=DailyPrice.trading_date.desc()
            ).label("rn")
        ).where(DailyPrice.symbol_id.in_(symbol_ids)).subquery()
        
        stmt_volumes = select(
            subq.c.symbol_id,
            subq.c.trading_date,
            subq.c.volume
        ).where(subq.c.rn <= 6)
        
        volume_rows = session.execute(stmt_volumes).all()
        print(f"Total volume history rows fetched: {len(volume_rows)}")
        
        from collections import defaultdict
        vols_by_symbol = defaultdict(list)
        for sym_id, t_date, vol in volume_rows:
            vols_by_symbol[sym_id].append((t_date, int(vol)))
            
        for s in snapshots[:15]:
            vols = vols_by_symbol.get(s.symbol_id, [])
            vols_list = [v[1] for v in vols]
            
            latest_volume = vols_list[0] if len(vols_list) >= 1 else int(s.volume)
            preceding_vols = vols_list[1:6] if len(vols_list) > 1 else []
            
            if preceding_vols:
                weekly_avg = sum(preceding_vols) / len(preceding_vols)
            else:
                weekly_avg = float(latest_volume)
                
            ratio = latest_volume / weekly_avg if weekly_avg > 0 else 1.0
            
            print(f"Symbol: {s.symbol} | Latest EOD Price Vol: {latest_volume:,} | Snapshot Vol: {s.volume:,} | Preceding Vols: {[f'{v:,}' for v in preceding_vols]} | Weekly Avg Vol: {weekly_avg:,.2f} | Ratio: {ratio:.2f}x")
            
    finally:
        session.close()
        db_manager.dispose()

if __name__ == "__main__":
    main()
