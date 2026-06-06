import pyodbc

# Connection to master database
conn_str = "Driver={ODBC Driver 17 for SQL Server};Server=(localdb)\\MSSQLLocalDB;Database=master;Trusted_Connection=yes;Encrypt=no;"

try:
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    
    # 1. List all user databases
    cursor.execute("SELECT name FROM sys.databases WHERE database_id > 4")
    databases = [row[0] for row in cursor.fetchall()]
    print("Databases on LocalDB:")
    for db in databases:
        print(f"  - {db}")
        
    print("\nInspecting each database for corporate actions count:")
    for db in databases:
        try:
            db_conn_str = f"Driver={{ODBC Driver 17 for SQL Server}};Server=(localdb)\\MSSQLLocalDB;Database={db};Trusted_Connection=yes;Encrypt=no;"
            db_conn = pyodbc.connect(db_conn_str)
            db_cursor = db_conn.cursor()
            
            # Check if corporate_actions table exists
            db_cursor.execute("SELECT COUNT(*) FROM sys.tables WHERE name = 'corporate_actions'")
            table_exists = db_cursor.fetchone()[0] > 0
            
            if table_exists:
                db_cursor.execute("SELECT COUNT(*) FROM corporate_actions")
                action_count = db_cursor.fetchone()[0]
                db_cursor.execute("SELECT COUNT(*) FROM daily_prices")
                price_count = db_cursor.fetchone()[0]
                db_cursor.execute("SELECT COUNT(*) FROM symbols")
                sym_count = db_cursor.fetchone()[0]
                print(f"  * Database: {db}")
                print(f"    - symbols: {sym_count}")
                print(f"    - daily_prices: {price_count}")
                print(f"    - corporate_actions: {action_count}")
            else:
                print(f"  * Database: {db} (no corporate_actions table)")
                
            db_conn.close()
        except Exception as inner_e:
            print(f"  * Database: {db} (Error: {inner_e})")
            
    conn.close()
except Exception as e:
    print(f"Error connecting to master: {e}")
