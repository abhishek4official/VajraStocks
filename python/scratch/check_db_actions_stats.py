import pyodbc

mssql_conn_str = "Driver={ODBC Driver 17 for SQL Server};Server=(localdb)\\MSSQLLocalDB;Database=vajra_stocks;Trusted_Connection=yes;Encrypt=no;"

try:
    conn = pyodbc.connect(mssql_conn_str)
    cursor = conn.cursor()
    
    # Total active symbols
    cursor.execute("SELECT COUNT(*) FROM symbols WHERE is_active = 1")
    total_active = cursor.fetchone()[0]
    
    # Symbols with at least one corporate action
    cursor.execute("SELECT COUNT(DISTINCT symbol_id) FROM corporate_actions")
    symbols_with_actions = cursor.fetchone()[0]
    
    # Total corporate actions
    cursor.execute("SELECT COUNT(*) FROM corporate_actions")
    total_actions = cursor.fetchone()[0]
    
    print(f"Database stats:")
    print(f"  - Total Active Symbols: {total_active}")
    print(f"  - Symbols with Corporate Actions: {symbols_with_actions} ({symbols_with_actions/total_active*100:.1f}%)")
    print(f"  - Total Corporate Actions stored: {total_actions}")
    
    # Print a list of symbols in portfolio and see if we can query yfinance for them to compare
    cursor.execute("SELECT s.symbol, COUNT(c.id) FROM symbols s LEFT JOIN corporate_actions c ON s.id = c.symbol_id WHERE s.is_active = 1 GROUP BY s.symbol ORDER BY COUNT(c.id) DESC")
    top_symbols = cursor.fetchall()
    
    print("\nTop symbols with most corporate actions:")
    for sym, count in top_symbols[:10]:
        print(f"  - {sym}: {count} actions")
        
    print("\nSymbols with 0 corporate actions (sample of 10):")
    zero_symbols = [row[0] for row in top_symbols if row[1] == 0]
    print(f"  - Total symbols with 0 actions: {len(zero_symbols)}")
    for sym in zero_symbols[:10]:
        print(f"    * {sym}")
        
    conn.close()
except Exception as e:
    print(f"Error: {e}")
