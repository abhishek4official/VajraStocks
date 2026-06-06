from pathlib import Path
from stocks.config import Config
from stocks.db.connection import DatabaseManager
from stocks.db.models import CorporateAction, Symbol
from sqlalchemy import select, func

config_file = Path(r"C:\Users\abhis\AppData\Roaming\VajraStocks\config.yaml")
if not config_file.exists():
    print(f"Error: Config file not found at {config_file}")
    exit(1)

config = Config.load(config_file)
db_manager = DatabaseManager.from_config(config)
try:
    db_manager.initialize()
    session = db_manager.get_session()
    
    count = session.query(CorporateAction).count()
    print(f"SUCCESS: Found {count} corporate actions in database.")
    
    if count > 0:
        # Group by action_type
        counts = session.query(CorporateAction.action_type, func.count(CorporateAction.id)).group_by(CorporateAction.action_type).all()
        print("\nCounts by Action Type:")
        for act_type, cnt in counts:
            print(f"  - {act_type}: {cnt}")
            
        # Get some sample actions
        actions = session.query(CorporateAction, Symbol).join(Symbol, CorporateAction.symbol_id == Symbol.id).order_by(CorporateAction.action_date.desc()).limit(10).all()
        print("\nLatest 10 Corporate Actions:")
        for act, sym in actions:
            print(f"  - {sym.symbol.replace('.NS', '')}: {act.action_type} of {act.value} on {act.action_date}")
    
    session.close()
finally:
    db_manager.dispose()
