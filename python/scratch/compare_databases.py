import sqlite3
import pyodbc
from pathlib import Path

sqlite_db = Path(r"C:\Users\abhis\AppData\Roaming\VajraStocks\data\vajra.db")
mssql_conn_str = "Driver={ODBC Driver 17 for SQL Server};Server=(localdb)\\MSSQLLocalDB;Database=vajra_stocks;Trusted_Connection=yes;Encrypt=no;"

print("Comparing databases:")

# 1. Check SQLite
if sqlite_db.exists():
    try:
        sqlite_conn = sqlite3.connect(sqlite_db)
        sqlite_cursor = sqlite_conn.cursor()
        
        # Check if table symbols exists
        sqlite_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='corporate_actions'")
        if sqlite_cursor.fetchone():
            sqlite_cursor.execute("SELECT COUNT(*) FROM symbols")
            sym_count = sqlite_cursor.fetchone()[0]
            sqlite_cursor.execute("SELECT COUNT(*) FROM daily_prices")
            price_count = sqlite_cursor.fetchone()[0]
            sqlite_cursor.execute("SELECT COUNT(*) FROM corporate_actions")
            action_count = sqlite_cursor.fetchone()[0]
            print(f"SQLite database ({sqlite_db}):")
            print(f"  - Symbols: {sym_count}")
            print(f"  - Daily Prices: {price_count}")
            print(f"  - Corporate Actions: {action_count}")
        else:
            print(f"SQLite database exists but 'corporate_actions' table was not found.")
            
        sqlite_conn.close()
    except Exception as e:
        print(f"Error querying SQLite database: {e}")
else:
    print(f"SQLite database not found at {sqlite_db}")

# 2. Check MSSQL
try:
    mssql_conn = pyodbc.connect(mssql_conn_str)
    mssql_cursor = mssql_conn.cursor()
    
    mssql_cursor.execute("SELECT COUNT(*) FROM symbols")
    sym_count = mssql_cursor.fetchone()[0]
    mssql_cursor.execute("SELECT COUNT(*) FROM daily_prices")
    price_count = mssql_cursor.fetchone()[0]
    mssql_cursor.execute("SELECT COUNT(*) FROM corporate_actions")
    action_count = mssql_cursor.fetchone()[0]
    print(f"\nMSSQL database (vajra_stocks):")
    print(f"  - Symbols: {sym_count}")
    print(f"  - Daily Prices: {price_count}")
    print(f"  - Corporate Actions: {action_count}")
    
    mssql_conn.close()
except Exception as e:
    print(f"\nError querying MSSQL database: {e}")
