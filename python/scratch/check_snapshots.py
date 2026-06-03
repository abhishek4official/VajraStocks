import sys
from sqlalchemy import select
from stocks.config import Config
from stocks.db.connection import DatabaseManager
from stocks.db.models import ScreeningSnapshot

def check():
    config = Config.load()
    db_mgr = DatabaseManager(config)
    db_mgr.initialize()
    session = db_mgr.get_session()
    
    # Query first 10 snapshots
    stmt = select(ScreeningSnapshot).limit(10)
    results = session.scalars(stmt).all()
    
    print(f"Total snapshots returned in test: {len(results)}")
    print("Symbol | is_nr7 | is_inside_bar | is_gap_up | is_gap_down")
    print("-" * 60)
    for r in results:
        print(f"{r.symbol} | {r.is_nr7} | {r.is_inside_bar} | {r.is_gap_up} | {r.is_gap_down}")
        
    # Let's count how many True we have for each
    print(f"NR7 count (where True): {session.query(ScreeningSnapshot).filter(ScreeningSnapshot.is_nr7 == True).count()}")
    print(f"Inside Bar count (where True): {session.query(ScreeningSnapshot).filter(ScreeningSnapshot.is_inside_bar == True).count()}")
    print(f"Gap Up count (where True): {session.query(ScreeningSnapshot).filter(ScreeningSnapshot.is_gap_up == True).count()}")
    print(f"Gap Down count (where True): {session.query(ScreeningSnapshot).filter(ScreeningSnapshot.is_gap_down == True).count()}")
    
    db_mgr.dispose()

if __name__ == "__main__":
    check()
