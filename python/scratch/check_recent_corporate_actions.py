import pyodbc

mssql_conn_str = "Driver={ODBC Driver 17 for SQL Server};Server=(localdb)\\MSSQLLocalDB;Database=vajra_stocks;Trusted_Connection=yes;Encrypt=no;"

try:
    conn = pyodbc.connect(mssql_conn_str)
    cursor = conn.cursor()
    
    # Query corporate actions ordered by created_at desc
    cursor.execute("SELECT TOP 20 c.id, s.symbol, c.action_date, c.action_type, c.value, c.created_at FROM corporate_actions c JOIN symbols s ON c.symbol_id = s.id ORDER BY c.created_at DESC")
    actions = cursor.fetchall()
    
    print("Most Recently Created Corporate Actions in Database:")
    for act in actions:
        print(f"  - ID: {act[0]}, Symbol: {act[1]}, Action: {act[3]} of {act[4]} on {act[2]}, Created At: {act[5]}")
        
    conn.close()
except Exception as e:
    print(f"Error: {e}")
