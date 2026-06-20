from __future__ import annotations

from typing import Annotated, Any

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class VajraState(TypedDict):
    # Chat history — LangGraph merges via add_messages reducer
    messages: Annotated[list[BaseMessage], add_messages]

    # Routing
    intent: str
    symbol: str | None

    # Data accumulated through the pipeline
    sql_data: dict[str, Any]          # OHLCV + indicators for single-stock workflows
    market_data: dict[str, Any]       # Nifty data + regime for market/scan workflows
    analysis_scores: dict[str, Any]   # LLM technical scoring output
    scan_results: list[dict[str, Any]] # Opportunity scanner output (breakout/swing)
    analysis_candidates: list[dict[str, Any]]  # Scored swing candidates with DB refs
    trade_plan: dict[str, Any]        # ATR plan (single stock or swing_plans list)
    screener_rows: list[dict[str, Any]]  # SQL screening result rows for frontend grid

    # Final output
    report: str
    recommendation: str
    confidence: str

    # Error flag — set by any node on failure
    error: str | None
