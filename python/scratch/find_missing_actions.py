import pyodbc
import yfinance as yf
import datetime

mssql_conn_str = "Driver={ODBC Driver 17 for SQL Server};Server=(localdb)\\MSSQLLocalDB;Database=vajra_stocks;Trusted_Connection=yes;Encrypt=no;"

try:
    conn = pyodbc.connect(mssql_conn_str)
    cursor = conn.cursor()
    
    # 1. Find active symbols with 0 corporate actions in DB
    cursor.execute("SELECT s.id, s.symbol FROM symbols s LEFT JOIN corporate_actions c ON s.id = c.symbol_id WHERE s.is_active = 1 GROUP BY s.id, s.symbol HAVING COUNT(c.id) = 0")
    symbols_with_no_actions = cursor.fetchall()
    
    print(f"Found {len(symbols_with_no_actions)} active symbols with 0 corporate actions in database.")
    
    # Let's inspect a few of these symbols on yfinance to see if they had actions in the last 3 years
    three_years_ago = datetime.date.today() - datetime.timedelta(days=3 * 365)
    
    checked_count = 0
    missing_actions = []
    
    for sym_id, symbol in symbols_with_no_actions:
        if checked_count >= 30:  # Check a sample of 30 symbols to avoid hitting rate limits
            break
            
        print(f"Checking {symbol} on yfinance...")
        ticker = yf.Ticker(symbol)
        actions = ticker.actions
        
        # Check if there are any actions in the last 3 years
        if not actions.empty:
            recent_actions = actions[actions.index.date >= three_years_ago]
            if not recent_actions.empty:
                print(f"  * WARNING: {symbol} has {len(recent_actions)} corporate actions on yfinance in the last 3 years, but 0 in DB!")
                for idx, row in recent_actions.iterrows():
                    print(f"    - {idx.date()}: Dividends={row['Dividends']}, Splits={row['Stock Splits']}")
                missing_actions.append((symbol, len(recent_actions)))
                
        checked_count += 1
        
    print(f"\nSummary of check:")
    print(f"  - Total checked: {checked_count}")
    print(f"  - Symbols with missing recent actions: {len(missing_actions)}")
    for sym, count in missing_actions:
        print(f"    * {sym}: {count} actions missing")
        
    conn.close()
except Exception as e:
    print(f"Error: {e}")
