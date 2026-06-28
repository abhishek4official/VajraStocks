"""Tests for the LangGraph-based multi-agent research pipeline.

Replaces the deleted Microsoft Agent Framework (MAF) tests that imported
LLMClient, Orchestrator, and AgentPool — none of which exist anymore.

Coverage:
  - Graph compilation (build_graph)
  - Routing functions (_route_from_router, _route_from_regime, _route_from_scan)
  - VajraState structure
  - router_node fast-path heuristics (no LLM call)
"""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage
from unittest.mock import AsyncMock, MagicMock, patch

from stocks.services.agents.graph import (
    _route_from_regime,
    _route_from_router,
    _route_from_scan,
    build_graph,
    vajra_graph,
)
from stocks.services.agents.nodes import router_node
from stocks.services.agents.state import VajraState


# ─── Graph compilation ────────────────────────────────────────────────────────

def test_build_graph_compiles_without_error():
    """build_graph() must compile to a runnable StateGraph without raising."""
    graph = build_graph()
    assert graph is not None


def test_module_level_vajra_graph_is_compiled():
    """The module-level singleton must be available at import time."""
    assert vajra_graph is not None


# ─── Routing functions ────────────────────────────────────────────────────────

@pytest.mark.parametrize("intent,expected", [
    ("analyze_stock",    "fetch_data"),
    ("breakout_scan",    "fetch_market"),
    ("swing_trade_scan", "fetch_market"),
    ("market_regime",    "fetch_market"),
    ("sql_screening",    "sql_screen"),
    ("unknown_intent",   "fetch_data"),   # fallback to analyze_stock path
])
def test_route_from_router(intent, expected):
    state: VajraState = {"intent": intent, "messages": [], "symbol": None,
                         "sql_data": {}, "market_data": {}, "analysis_scores": {},
                         "scan_results": [], "analysis_candidates": [], "trade_plan": {},
                         "screener_rows": [], "report": "", "recommendation": "",
                         "confidence": "", "error": None}
    assert _route_from_router(state) == expected


@pytest.mark.parametrize("intent,expected", [
    ("market_regime",    "report"),
    ("breakout_scan",    "scan_opportunities"),
    ("swing_trade_scan", "scan_opportunities"),
])
def test_route_from_regime(intent, expected):
    state: VajraState = {"intent": intent, "messages": [], "symbol": None,
                         "sql_data": {}, "market_data": {}, "analysis_scores": {},
                         "scan_results": [], "analysis_candidates": [], "trade_plan": {},
                         "screener_rows": [], "report": "", "recommendation": "",
                         "confidence": "", "error": None}
    assert _route_from_regime(state) == expected


@pytest.mark.parametrize("intent,expected", [
    ("swing_trade_scan", "analyze_swing_candidates"),
    ("breakout_scan",    "report"),
    ("analyze_stock",    "report"),
])
def test_route_from_scan(intent, expected):
    state: VajraState = {"intent": intent, "messages": [], "symbol": None,
                         "sql_data": {}, "market_data": {}, "analysis_scores": {},
                         "scan_results": [], "analysis_candidates": [], "trade_plan": {},
                         "screener_rows": [], "report": "", "recommendation": "",
                         "confidence": "", "error": None}
    assert _route_from_scan(state) == expected


# ─── VajraState structure ─────────────────────────────────────────────────────

def test_vajra_state_accepts_all_required_keys():
    """VajraState TypedDict must accept all fields without a type error at runtime."""
    state: VajraState = {
        "messages": [HumanMessage(content="Analyze RELIANCE.NS")],
        "intent": "analyze_stock",
        "symbol": "RELIANCE.NS",
        "sql_data": {},
        "market_data": {},
        "analysis_scores": {},
        "scan_results": [],
        "analysis_candidates": [],
        "trade_plan": {},
        "screener_rows": [],
        "report": "",
        "recommendation": "NEUTRAL",
        "confidence": "MEDIUM",
        "error": None,
    }
    assert state["intent"] == "analyze_stock"
    assert state["symbol"] == "RELIANCE.NS"


# ─── router_node fast-path heuristics (no LLM) ───────────────────────────────

def _make_state(prompt: str) -> VajraState:
    return {
        "messages": [HumanMessage(content=prompt)],
        "intent": "", "symbol": None,
        "sql_data": {}, "market_data": {}, "analysis_scores": {},
        "scan_results": [], "analysis_candidates": [], "trade_plan": {},
        "screener_rows": [], "report": "", "recommendation": "",
        "confidence": "", "error": None,
    }


def _make_config(app_config=None):
    cfg = MagicMock()
    cfg.ai.provider = "ollama"
    cfg.ai.model = "mock"
    cfg.ai.base_url = "http://localhost:11434"
    return {"configurable": {"app_config": app_config or cfg, "db": MagicMock()}}


@pytest.mark.anyio
async def test_router_node_sql_fast_path():
    state = _make_state("STOCKS: close > 200 AND rsi < 40")
    result = await router_node(state, _make_config())
    assert result["intent"] == "sql_screening"
    assert result["symbol"] is None


@pytest.mark.anyio
async def test_router_node_ticker_fast_path():
    state = _make_state("What is the outlook for TCS.NS?")
    result = await router_node(state, _make_config())
    assert result["intent"] == "analyze_stock"
    assert result["symbol"] == "TCS.NS"


@pytest.mark.anyio
async def test_router_node_swing_keyword_fast_path():
    state = _make_state("Find swing trade setups today")
    result = await router_node(state, _make_config())
    assert result["intent"] == "swing_trade_scan"


@pytest.mark.anyio
async def test_router_node_regime_keyword_fast_path():
    state = _make_state("What is the market regime right now?")
    result = await router_node(state, _make_config())
    assert result["intent"] == "market_regime"


@pytest.mark.anyio
async def test_router_node_scan_keyword_fast_path():
    state = _make_state("Find breakout opportunities in the market")
    result = await router_node(state, _make_config())
    assert result["intent"] == "breakout_scan"


@pytest.mark.anyio
async def test_router_node_select_sql_fast_path():
    state = _make_state("SELECT symbol FROM screening_snapshots WHERE rsi_14 < 30")
    result = await router_node(state, _make_config())
    assert result["intent"] == "sql_screening"


@pytest.mark.anyio
async def test_router_node_llm_fallback_uses_mock():
    """For ambiguous prompts the router falls back to the LLM; verify it handles
    the LLM response cleanly without hitting a live endpoint."""
    state = _make_state("Give me some ideas")

    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.intent = "breakout_scan"
    mock_response.symbol = None
    mock_response.rationale = "Interpreted as a scan request"
    mock_llm.with_structured_output.return_value.ainvoke = AsyncMock(return_value=mock_response)

    with patch("stocks.services.agents.nodes._build_llm", return_value=mock_llm):
        result = await router_node(state, _make_config())

    assert result["intent"] == "breakout_scan"
    assert result["symbol"] is None
