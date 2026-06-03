import asyncio
import sys
import os
sys.path.append(os.path.abspath("src"))

from stocks.config import Config
from stocks.db.connection import DatabaseManager
from stocks.services.agents.orchestrator import Orchestrator

async def main():
    print("Loading config...")
    config = Config.load()
    print("Initializing Database Manager...")
    db_manager = DatabaseManager(config)
    db_manager.initialize()
    
    session = db_manager.get_session()
    try:
        print("Instantiating Orchestrator...")
        orch = Orchestrator(config, session)
        
        print("Running live execute_workflow for RELIANCE...")
        async for event in orch.execute_workflow("Analyze RELIANCE"):
            print("EVENT:", event.strip())
            
    except Exception as e:
        print("ERROR occurred during orchestrator run:", e)
        import traceback
        traceback.print_exc()
    finally:
        session.close()
        db_manager.dispose()

if __name__ == "__main__":
    asyncio.run(main())
