import sys
from pathlib import Path
# Add src directory to PYTHONPATH
sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

import traceback
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from stocks.services.settings_service import SettingsService

try:
    engine = create_engine("sqlite:///data/vajra.db")
    Session = sessionmaker(bind=engine)
    session = Session()
    
    print("Instantiating SettingsService...")
    svc = SettingsService(session)
    
    print("Calling settings_by_category()...")
    settings = svc.settings_by_category()
    
    print("Success!")
    for cat, items in settings.items():
        print(f"Category: {cat}, items count: {len(items)}")
        for item in items[:2]:
            print(f"  - {item['key']}: {item['value']}")
except Exception as e:
    print("ERROR:")
    traceback.print_exc()
