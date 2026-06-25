"""Integrity guard (V2.0 spec M0): the fabricated backtester must stay gone.

The old services/quant/backtester.py returned hardcoded sharpe=1.75 / profit_factor=2.1
on success and invented a 55.45% win rate on any error, then fed those numbers into the
AI research report via a graph node. Until a real, reproducible engine exists (M2), no
fabricated backtest metrics may flow through the pipeline.
"""

import importlib

import pytest


def test_fake_backtester_module_is_removed():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("stocks.services.quant.backtester")


def test_graph_has_no_backtest_node():
    from stocks.services.agents.graph import build_graph

    graph = build_graph()
    node_names = set(graph.get_graph().nodes)
    assert "backtest" not in node_names
