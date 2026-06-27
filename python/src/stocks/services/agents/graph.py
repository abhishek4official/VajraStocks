"""LangGraph StateGraph — unified multi-agent research pipeline.

Replaces the Microsoft Agent Framework WorkflowBuilder + FunctionExecutor approach.
All 4 workflows (analyze_stock, breakout_scan, swing_trade_scan, market_regime) and
the direct sql_screening path are expressed as a single compiled graph with conditional
routing edges. Conversation memory is checkpointed to SQLite so state survives restarts.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from stocks.services.agents.nodes import (
    analyze_stock_node,
    analyze_swing_candidates_node,
    fetch_data_node,
    fetch_market_node,
    market_regime_node,
    report_node,
    router_node,
    scan_opportunities_node,
    sql_screen_node,
    trade_plan_node,
    trade_plan_swing_node,
)
from stocks.services.agents.state import VajraState

# ─── Routing functions ────────────────────────────────────────────────────────

def _route_from_router(state: VajraState) -> str:
    return {
        "analyze_stock": "fetch_data",
        "breakout_scan": "fetch_market",
        "swing_trade_scan": "fetch_market",
        "market_regime": "fetch_market",
        "sql_screening": "sql_screen",
    }.get(state.get("intent", "analyze_stock"), "fetch_data")


def _route_from_regime(state: VajraState) -> str:
    # market_regime workflow ends at report; others continue to scan
    return "report" if state.get("intent") == "market_regime" else "scan_opportunities"


def _route_from_scan(state: VajraState) -> str:
    # swing needs per-candidate analysis; breakout goes straight to report
    return (
        "analyze_swing_candidates"
        if state.get("intent") == "swing_trade_scan"
        else "report"
    )


# ─── Graph construction ───────────────────────────────────────────────────────

def _make_checkpointer() -> SqliteSaver:
    """Return a SqliteSaver backed by data/vajra_graph.db (beside the main DB)."""
    checkpoint_path = Path("data/vajra_graph.db")
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(checkpoint_path), check_same_thread=False)
    return SqliteSaver(conn)


def build_graph():
    builder = StateGraph(VajraState)

    # Register all nodes
    builder.add_node("router", router_node)
    builder.add_node("fetch_data", fetch_data_node)
    builder.add_node("fetch_market", fetch_market_node)
    builder.add_node("market_regime", market_regime_node)
    builder.add_node("scan_opportunities", scan_opportunities_node)
    builder.add_node("analyze_stock", analyze_stock_node)
    builder.add_node("analyze_swing_candidates", analyze_swing_candidates_node)
    builder.add_node("trade_plan", trade_plan_node)
    builder.add_node("trade_plan_swing", trade_plan_swing_node)
    builder.add_node("sql_screen", sql_screen_node)
    builder.add_node("report", report_node)

    # Entry
    builder.add_edge(START, "router")

    # Route from router → workflow entry points
    builder.add_conditional_edges(
        "router",
        _route_from_router,
        {"fetch_data": "fetch_data", "fetch_market": "fetch_market", "sql_screen": "sql_screen"},
    )

    # ── analyze_stock path ───────────────────────────────────────────────────
    builder.add_edge("fetch_data", "analyze_stock")
    builder.add_edge("analyze_stock", "trade_plan")
    # NOTE: the fabricated "backtest" node was removed (V2.0 spec M0). A real,
    # reproducible backtest engine (M2) will re-insert a trustworthy node here.
    builder.add_edge("trade_plan", "report")

    # ── market_regime / breakout_scan / swing_trade_scan shared entry ────────
    builder.add_edge("fetch_market", "market_regime")
    builder.add_conditional_edges(
        "market_regime",
        _route_from_regime,
        {"report": "report", "scan_opportunities": "scan_opportunities"},
    )
    builder.add_conditional_edges(
        "scan_opportunities",
        _route_from_scan,
        {"report": "report", "analyze_swing_candidates": "analyze_swing_candidates"},
    )
    builder.add_edge("analyze_swing_candidates", "trade_plan_swing")
    builder.add_edge("trade_plan_swing", "report")

    # ── sql_screening path (bypasses report_node) ────────────────────────────
    builder.add_edge("sql_screen", END)

    # ── all report paths terminate ────────────────────────────────────────────
    builder.add_edge("report", END)

    return builder.compile(checkpointer=_make_checkpointer())


# Module-level singleton — shared across all requests for the same process lifetime.
# SqliteSaver persists conversation state to data/vajra_graph.db across restarts.
vajra_graph = build_graph()
