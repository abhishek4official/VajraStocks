import pyodbc

mssql_conn_str = "Driver={ODBC Driver 17 for SQL Server};Server=(localdb)\\MSSQLLocalDB;Database=vajra_stocks;Trusted_Connection=yes;Encrypt=no;"

try:
    conn = pyodbc.connect(mssql_conn_str)
    cursor = conn.cursor()
    
    cursor.execute("SELECT TOP 10 id, run_id, start_time, end_time, status, total_symbols, processed_symbols, failed_symbols, records_inserted, error_summary FROM sync_jobs ORDER BY start_time DESC")
    jobs = cursor.fetchall()
    
    print("Recent Sync Jobs:")
    for job in jobs:
        print(f"  - Job ID: {job[0]}, Run ID: {job[1]}")
        print(f"    * Start: {job[2]}, End: {job[3]}")
        print(f"    * Status: {job[4]}")
        print(f"    * Progress: Total={job[5]}, Processed={job[6]}, Failed={job[7]}, Inserted={job[8]}")
        if job[9]:
            print(f"    * Error Summary: {job[9][:200]}...")
        print()
        
    conn.close()
except Exception as e:
    print(f"Error: {e}")
