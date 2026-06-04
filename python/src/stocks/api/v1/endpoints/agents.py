import json

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy.orm import Session

from stocks.api.deps import get_config, get_db
from stocks.services.agents.orchestrator import Orchestrator

router = APIRouter(prefix="/agents", tags=["AI Quant Agents"])


@router.get("/chat-stream")
async def chat_stream(
    request: Request,
    prompt: str = Query(..., description="The user's query prompt to feed the multi-agent system"),
    db: Session = Depends(get_db),
):
    """Executes a dynamic multi-agent technical research workflow and streams progress events in real-time."""
    logger.info(f"AI Agent Chat request initiated with prompt: '{prompt}'")

    config = get_config(request)   # reads AI settings live from DB — no config.yaml
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
