import sys
import yaml
from pathlib import Path

# Add src to python path
sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import create_engine, text
from stocks.db.connection import DatabaseManager

# Load connection string from config.yaml
config_yaml = Path(__file__).resolve().parents[1] / "config" / "config.yaml"
if not config_yaml.exists():
    print("config.yaml not found!")
    sys.exit(1)

with open(config_yaml, encoding="utf-8") as f:
    data = yaml.safe_load(f) or {}

db_config = data.get("database", {})
conn_str = db_config.get("connection_string", "")
provider = db_config.get("provider", "")

print(f"Config provider: {provider}")
print(f"Config connection string: {conn_str}")

try:
    print("Testing connection using sqlalchemy create_engine...")
    engine = create_engine(conn_str)
    with engine.connect() as conn:
        print("Successfully connected to MSSQL!")
        
        # Check tables
        print("\nChecking tables in database:")
        res = conn.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_type = 'BASE TABLE';"
        ))
        tables = [row[0] for row in res]
        print("Tables found:", tables)
        
        if "app_settings" in tables:
            print("\nQuerying app_settings count...")
            cnt = conn.execute(text("SELECT COUNT(*) FROM app_settings;")).scalar()
            print(f"app_settings row count: {cnt}")
            
            # Print a few settings
            print("\nPrinting top 5 settings:")
            rows = conn.execute(text("SELECT TOP 5 category, [key], value FROM app_settings;")).fetchall()
            for r in rows:
                print(f"  {r[0]}.{r[1]} = {r[2]}")
        else:
            print("\nTable 'app_settings' does NOT exist in MSSQL database!")
            
except Exception as e:
    import traceback
    print("\nERROR connecting/querying MSSQL:")
    traceback.print_exc()
