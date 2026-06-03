import json

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy.orm import Session

from stocks.api.deps import get_db
from stocks.services.agents.orchestrator import Orchestrator

router = APIRouter(prefix="/agents", tags=["AI Quant Agents"])


def _build_config_from_settings(request: Request):
    """Builds a minimal Config-compatible object from DB settings for the Orchestrator."""
    from stocks.config import AIConfig, Config, DatabaseConfig, DownloaderConfig, SymbolsConfig, ValidationConfig, AppConfig, LoggingConfig
    from stocks.services.settings_service import SettingsService

    session = request.app.state.db_manager.get_session()
    try:
        svc = SettingsService(session)
        cfg = Config(
            app=AppConfig(
                name=svc.get_str("APPLICATION", "app_name", "VajraStocks"),
                env=svc.get_str("APPLICATION", "app_env", "production"),
            ),
            database=DatabaseConfig(
                connection_string=svc.get_str("DATABASE", "db_connection_string", "sqlite:///data/vajra.db"),
            ),
            downloader=DownloaderConfig(),
            symbols=SymbolsConfig(
                active_equities_url=svc.get_str("MARKET", "nse_equities_url"),
                fallback_csv_path=svc.get_str("MARKET", "nse_fallback_csv_path"),
            ),
            validation=ValidationConfig(),
            logging=LoggingConfig(),
            ai=AIConfig(
                provider=svc.get_str("AI", "ai_provider", "ollama"),
                base_url=svc.get_str("AI", "ai_base_url", "http://localhost:11434"),
                model=svc.get_str("AI", "ai_model", "qwen2.5-coder:7b"),
            ),
        )
        return cfg
    finally:
        session.close()


@router.get("/chat-stream")
async def chat_stream(
    request: Request,
    prompt: str = Query(..., description="The user's query prompt to feed the multi-agent system"),
    db: Session = Depends(get_db),
):
    """Executes a dynamic multi-agent technical research workflow and streams progress events in real-time."""
    logger.info(f"AI Agent Chat request initiated with prompt: '{prompt}'")

    config = _build_config_from_settings(request)
    orchestrator = Orchestrator(config, db)

    async def event_generator():
        try:
            async for event in orchestrator.execute_workflow(prompt):
                yield event
        except Exception as e:
            logger.critical(f"Critical error in AI Agent execution pipeline: {e}")
            err_payload = {"event": "error", "data": f"Workflow execution crash: {e}"}
            yield f"data: {json.dumps(err_payload)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
