from pathlib import Path
from stocks.config import Config
from stocks.db.connection import DatabaseManager
from stocks.db.models import PortfolioHolding, SymbolConfluenceLevel, Symbol, ScreeningSnapshot
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
    
    # Query holdings
    holdings = session.query(PortfolioHolding).all()
    print(f"--- TRACING PORTFOLIO RISK CALCULATIONS FOR {len(holdings)} HOLDINGS ---")
    print(f"{'Symbol':<15} | {'Qty':<6} | {'LTP':<8} | {'ATR%':<5} | {'ATR_Abs':<7} | {'Support':<8} | {'Old Stop':<8} | {'New Stop':<8} | {'Old Risk':<9} | {'New Risk':<9} | {'Change':<8}")
    print("-" * 115)
    
    total_old_risk = 0.0
    total_new_risk = 0.0
    
    for h in holdings:
        # Get symbol
        sym = session.query(Symbol).filter_by(id=h.symbol_id).first() if h.symbol_id else None
        if not sym:
            print(f"{h.instrument:<15} | No matched symbol in DB. Skipping.")
            continue
            
        # Get snapshot
        snap = session.query(ScreeningSnapshot).filter_by(symbol=sym.symbol).first()
        ltp = float(snap.close_price) if snap and snap.close_price else float(h.ltp_imported)
        atr_pct = float(snap.atr_pct) if snap and snap.atr_pct is not None else 0.0
        atr_abs = (atr_pct / 100.0) * ltp if ltp > 0 else 0.0
        
        # Get confluence levels
        confl_levels = session.query(SymbolConfluenceLevel).filter_by(symbol_id=sym.id).all()
        pos_supports = [lvl for lvl in confl_levels if lvl.level_type == "SUPPORT"]
        pos_supports_sorted = sorted(pos_supports, key=lambda x: float(x.price), reverse=True)
        support_val = float(pos_supports_sorted[0].price) if pos_supports_sorted else None
        
        # 1. Old Stop Calculation: ltp - 1.5 * atr_abs
        old_stop = round(ltp - 1.5 * atr_abs, 2)
        old_open_risk = round(h.qty * (ltp - old_stop), 2)
        
        # 2. New Stop Calculation (Structural support)
        if support_val is not None:
            new_stop = round(support_val - 1.5 * atr_abs, 2)
            if new_stop >= ltp:
                new_stop = round(ltp - 2.0 * atr_abs, 2)
        else:
            new_stop = round(ltp - 1.5 * atr_abs, 2)
            
        new_open_risk = round(h.qty * (ltp - new_stop), 2)
        
        total_old_risk += old_open_risk
        total_new_risk += new_open_risk
        change = new_open_risk - old_open_risk
        
        support_str = f"{support_val:.2f}" if support_val is not None else "None"
        print(f"{sym.symbol.replace('.NS', ''):<15} | {h.qty:<6.1f} | {ltp:<8.2f} | {atr_pct:<5.2f} | {atr_abs:<7.2f} | {support_str:<8} | {old_stop:<8.2f} | {new_stop:<8.2f} | {old_open_risk:<9.2f} | {new_open_risk:<9.2f} | +{change:.2f}")

    print("-" * 115)
    print(f"Total Portfolio: {'':<72} | {total_old_risk:<9.2f} | {total_new_risk:<9.2f} | +{total_new_risk - total_old_risk:.2f}")
    
    session.close()
finally:
    db_manager.dispose()
