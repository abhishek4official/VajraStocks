from pathlib import Path
from stocks.config import Config
from stocks.db.connection import DatabaseManager
from stocks.db.models import SymbolConfluenceLevel, Symbol
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
    
    count = session.query(SymbolConfluenceLevel).count()
    print(f"SUCCESS: Found {count} confluence levels in database.")
    
    if count > 0:
        # Load a few samples
        levels = session.query(SymbolConfluenceLevel, Symbol).join(Symbol, SymbolConfluenceLevel.symbol_id == Symbol.id).limit(5).all()
        print("\nSample Calculated Levels:")
        for lvl, sym in levels:
            print(f"  - {sym.symbol.replace('.NS', '')}: {lvl.level_type} at {lvl.price} (Strength: {lvl.strength_score}/100, Components: {lvl.components})")
    
    session.close()
finally:
    db_manager.dispose()
