"""First-run setup wizard API — bootstraps the database and seeds initial configuration."""

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/setup", tags=["Setup"])


class SetupRequest(BaseModel):
    db_provider: str = "sqlite"
    db_connection_string: str = "sqlite:///data/vajra.db"
    ai_provider: str = "ollama"
    ai_base_url: str = "http://localhost:11434"
    ai_model: str = "qwen2.5-coder:7b"
    ai_api_key: str = ""
    download_symbols: bool = True


@router.get("/status")
def setup_status(request: Request):
    """Returns whether a first-run setup is needed."""
    first_run = getattr(request.app.state, "first_run", False)
    # Also check if settings table is populated
    try:
        from stocks.services.settings_service import SettingsService
        from sqlalchemy import select
        from stocks.db.models import AppSetting
        session = request.app.state.db_manager.get_session()
        try:
            row = session.scalar(select(AppSetting).limit(1))
            setup_needed = row is None
        finally:
            session.close()
    except Exception:
        setup_needed = True

    return {
        "setup_needed": setup_needed or first_run,
        "version": "1.0.0",
    }


@router.post("/initialize")
async def initialize(body: SetupRequest, request: Request):
    """Applies user-chosen settings from the setup wizard and triggers symbol download."""
    from stocks.services.settings_service import SettingsService

    session = request.app.state.db_manager.get_session()
    try:
        svc = SettingsService(session)

        # Update user-chosen settings
        svc.set("DATABASE", "db_provider",          body.db_provider)
        svc.set("DATABASE", "db_connection_string",  body.db_connection_string)
        svc.set("AI",       "ai_provider",           body.ai_provider)
        svc.set("AI",       "ai_base_url",           body.ai_base_url)
        svc.set("AI",       "ai_model",              body.ai_model)
        if body.ai_api_key:
            svc.set("AI",   "ai_api_key",            body.ai_api_key)

        request.app.state.first_run = False

    finally:
        session.close()

    # Trigger symbol download in background if requested
    if body.download_symbols:
        import asyncio
        asyncio.create_task(_background_symbol_download(request))

    return {"status": "initialized", "download_started": body.download_symbols}


async def _background_symbol_download(request: Request):
    """Runs the symbol bootstrap using DB-backed config (no config.yaml)."""
    import asyncio
    from loguru import logger
    from stocks.api.deps import get_config

    await asyncio.sleep(0.5)
    try:
        logger.info("Background: starting initial symbol download...")
        cfg = get_config(request)
        db_manager = request.app.state.db_manager
        session = db_manager.get_session()
        try:
            from stocks.services.symbol import SymbolService
            svc = SymbolService(cfg, session)
            parsed = svc.fetch_active_symbols_from_nse()
            count = svc.sync_symbols(parsed)
            svc.ensure_indices_registered()
            logger.info(f"Background symbol download complete — {count} symbols registered.")
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Background symbol download failed: {e}")
