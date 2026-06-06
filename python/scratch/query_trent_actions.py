from pathlib import Path
from stocks.config import Config
from stocks.db.connection import DatabaseManager
from stocks.db.models import CorporateAction, Symbol
from sqlalchemy import select

config_file = Path(r"C:\Users\abhis\AppData\Roaming\VajraStocks\config.yaml")
if not config_file.exists():
    print(f"Error: Config file not found at {config_file}")
    exit(1)

config = Config.load(config_file)
db_manager = DatabaseManager.from_config(config)
try:
    db_manager.initialize()
    session = db_manager.get_session()
    
    symbol_str = "TRENT.NS"
    clean_sym = symbol_str.strip().upper()
    raw_sym = clean_sym.replace(".NS", "")
    if not clean_sym.endswith(".NS") and not clean_sym.startswith("^"):
        clean_sym = f"{clean_sym}.NS"

    stmt = (
        select(CorporateAction, Symbol)
        .join(Symbol, CorporateAction.symbol_id == Symbol.id)
        .where((Symbol.symbol == clean_sym) | (Symbol.symbol == raw_sym))
        .order_by(CorporateAction.action_date.desc())
    )

    results = session.execute(stmt).all()
    print(f"Query for {symbol_str} returned {len(results)} actions:")
    for act, sym in results:
        print(f"  - Action ID: {act.id}, Symbol: {sym.symbol}, Type: {act.action_type}, Value: {act.value}, Date: {act.action_date}")
        
    session.close()
finally:
    db_manager.dispose()
