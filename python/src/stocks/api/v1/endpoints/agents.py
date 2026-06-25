import json
import uuid

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from loguru import logger
from sqlalchemy.orm import Session

from stocks.api.deps import get_config, get_db
from stocks.services.agents.graph import vajra_graph

router = APIRouter(prefix="/agents", tags=["AI Quant Agents"])

_NODE_STATUS: dict[str, str] = {
    "fetch_data": "Fetching stock data from database...",
    "fetch_market": "Fetching Nifty market data...",
    "market_regime": "Classifying market regime...",
    "scan_opportunities": "Scanning for opportunities...",
    "analyze_stock": "Scoring technical indicators...",
    "analyze_swing_candidates": "Evaluating swing candidates...",
    "trade_plan": "Calculating ATR trade plan...",
    "trade_plan_swing": "Building swing trade plans...",
    "sql_screen": "Executing SQL screening...",
    "report": "Compiling investment report...",
}


def _sse(event_type: str, data: object) -> str:
    return f"data: {json.dumps({'event': event_type, 'data': data})}\n\n"


@router.get("/chat-stream")
async def chat_stream(
    request: Request,
    prompt: str = Query(..., description="User query"),
    thread_id: str = Query(default="", description="Conversation thread ID for memory continuity"),
    db: Session = Depends(get_db),
):
    """Stream a LangGraph multi-agent research pipeline via Server-Sent Events.

    Pass the same thread_id across requests to maintain conversation memory.
    A new UUID is generated and returned when thread_id is omitted.
    """
    app_config = get_config(request)
    tid = thread_id.strip() or str(uuid.uuid4())

    # Always give LangGraph a fresh UUID so stale checkpoints from aborted runs
    # never bleed into the next request. The DB thread_id (tid) is only used for
    # conversation history persistence — not for LangGraph state.
    graph_tid = str(uuid.uuid4())

    run_config = {
        "configurable": {
            "thread_id": graph_tid,
            "db": db,
            "app_config": app_config,
        }
    }

    async def event_generator():
        yield _sse("started", "Activating AI research pipeline...")
        logger.info(f"AI pipeline started — thread={tid} prompt='{prompt[:80]}'")

        try:
            async for chunk in vajra_graph.astream(
                {"messages": [HumanMessage(content=prompt)]},
                config=run_config,
                stream_mode="updates",
            ):
                if await request.is_disconnected():
                    logger.warning(f"Client disconnected — aborting thread={tid}")
                    break

                for node_name, node_output in chunk.items():
                    if not isinstance(node_output, dict):
                        continue

                    # Emit intent_detected after router resolves
                    if node_name == "router":
                        yield _sse("intent_detected", {
                            "intent": node_output.get("intent", ""),
                            "symbol": node_output.get("symbol"),
                            "rationale": "",
                        })
                        continue

                    # Progress event for every other node
                    yield _sse("agent_active", {
                        "agent": node_name,
                        "status": _NODE_STATUS.get(node_name, f"Running {node_name}..."),
                        "data": {},
                    })

                    # Complete event when report or sql_screen finishes
                    if node_name in ("report", "sql_screen") and "report" in node_output:
                        report_body = node_output.get("report", "")
                        node_error = node_output.get("error")
                        # If report_node itself failed (empty body + error), surface error
                        if node_error and not report_body:
                            yield _sse("error", node_error)
                            return
                        yield _sse("complete", {
                            "report": report_body,
                            "recommendation": node_output.get("recommendation", "NEUTRAL"),
                            "confidence": node_output.get("confidence", "MEDIUM"),
                            "screener_results": node_output.get("screener_rows", []),
                            "thread_id": tid,
                        })
                        return

                    # For intermediate nodes: log the error but let the pipeline continue
                    # to report_node rather than aborting with a broken partial state.
                    if node_output.get("error"):
                        logger.warning(f"Node {node_name} reported error (pipeline continues): {node_output['error']}")

        except Exception as exc:
            logger.critical(f"AI pipeline crashed — thread={tid}: {exc}")
            yield _sse("error", f"Pipeline error: {exc}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
