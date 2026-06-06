import pyodbc

mssql_conn_str = "Driver={ODBC Driver 17 for SQL Server};Server=(localdb)\\MSSQLLocalDB;Database=vajra_stocks;Trusted_Connection=yes;Encrypt=no;"

try:
    conn = pyodbc.connect(mssql_conn_str)
    cursor = conn.cursor()
    
    # 1. Fetch portfolio holdings
    cursor.execute("SELECT instrument, symbol_id FROM portfolio_holdings")
    holdings = cursor.fetchall()
    
    print("Portfolio Holdings:")
    if not holdings:
        print("  (No holdings found in database)")
    
    for instrument, symbol_id in holdings:
        # Check symbol table
        cursor.execute("SELECT symbol, company_name FROM symbols WHERE id = ?", symbol_id)
        sym_row = cursor.fetchone()
        if sym_row:
            sym_name = sym_row[0]
            comp_name = sym_row[1]
        else:
            sym_name = "UNKNOWN"
            comp_name = "UNKNOWN"
            
        # Count corporate actions for this symbol
        cursor.execute("SELECT COUNT(*) FROM corporate_actions WHERE symbol_id = ?", symbol_id)
        action_count = cursor.fetchone()[0]
        
        print(f"  - {instrument} (resolved to {sym_name}): {action_count} corporate actions in database")
        
        if action_count > 0:
            cursor.execute("SELECT action_type, value, action_date FROM corporate_actions WHERE symbol_id = ? ORDER BY action_date DESC", symbol_id)
            actions = cursor.fetchall()
            for action_type, value, action_date in actions[:3]:
                print(f"    * {action_type} of {value} on {action_date}")

    conn.close()
except Exception as e:
    print(f"Error querying MSSQL: {e}")
