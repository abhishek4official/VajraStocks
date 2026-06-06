"""Strategy Registry — single source of truth for available strategies (§3.4).

Wraps the research-backed swing/position strategies in `swing.py` behind a uniform
adapter so the Screener API + materializer stay strategy-agnostic. Adding a strategy
is a one-line registration; both the API and the UI pick it up automatically.
"""

from __future__ import annotations

from typing import Any

from stocks.services.strategies import swing

# Display ordering of the registered strategies.
_ORDER = ["minervini", "high52", "weinstein", "momentum", "dual"]

# Human-friendly grouping for the auto-rendered param panel.
_GROUP = {
    "timeframe": "Universe", "benchmark_symbol": "Universe", "use_market_filter": "Universe",
    "regime_ma_days": "Universe", "max_open_positions": "Universe",
    "risk_per_trade": "Risk", "stop_atr_mult": "Risk", "trail_atr_mult": "Risk",
    "atr_len_days": "Risk", "max_position_weight": "Risk", "max_gross_exposure": "Risk",
    "profit_target_R": "Risk", "weighting": "Risk",
}

_DESC = {
    "timeframe": "Bar timeframe: weekly / monthly",
    "benchmark_symbol": "Relative-strength benchmark (set by app)",
    "use_market_filter": "Gate entries by the index regime (uncheck = always risk-on)",
    "regime_ma_days": "Benchmark long-MA length for risk-on/off (days)",
    "max_open_positions": "Portfolio breadth cap (backtest only)",
    "weighting": "Position weighting: atr (vol-scaled) or equal",
    "risk_per_trade": "ATR fixed-fractional risk budget per trade",
    "stop_atr_mult": "Initial stop distance (x ATR)",
    "trail_atr_mult": "Chandelier trailing stop (x ATR)",
    "atr_len_days": "ATR length for sizing/stops (days)",
    "max_position_weight": "Per-name weight cap",
    "max_gross_exposure": "Long-only gross exposure cap",
    "profit_target_R": "Profit target in R (0 = let winners run)",
}


def _synth_schema(parameters: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Build a UI-renderable param schema from a strategy's flat `parameters` dict."""
    schema: dict[str, dict[str, Any]] = {}
    for key, val in parameters.items():
        group = _GROUP.get(key, "Signal")
        desc = _DESC.get(key, key.replace("_", " "))
        if isinstance(val, bool):
            spec = {"type": "boolean", "default": val}
        elif isinstance(val, (int, float)):
            spec = {"type": "number", "default": val}
        elif val is None:
            spec = {"type": "string", "default": ""}
        else:
            spec = {"type": "string", "default": str(val)}
        spec.update({"group": group, "description": desc})
        schema[key] = spec
    return schema


class SwingStrategyAdapter:
    """Uniform façade over a `swing._PortfolioStrategy` subclass."""

    version = "1.0"

    def __init__(self, sid: str, cls: type):
        self.id = sid
        self.cls = cls
        self.name = cls.metadata.get("name", sid)
        self.description = cls.metadata.get("source", "")
        self.data_needs = {"min_bars": 60, "benchmark": True, "timeframe": "weekly"}

    @property
    def param_schema(self) -> dict[str, dict[str, Any]]:
        return _synth_schema(self.cls.parameters)

    def resolve_params(self, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        """Defaults merged with caller overrides, coerced to each param's type."""
        params = dict(self.cls.parameters)
        for key, val in (overrides or {}).items():
            if key not in params or val is None:
                continue
            cur = params[key]
            try:
                if isinstance(cur, bool):
                    val = val if isinstance(val, bool) else str(val).lower() in ("1", "true", "yes")
                elif isinstance(cur, int) and not isinstance(cur, bool):
                    val = int(float(val))
                elif isinstance(cur, float):
                    val = float(val)
            except (TypeError, ValueError):
                continue
            params[key] = val
        return params

    def make(self, overrides: dict[str, Any] | None = None, force_market_ok: bool = False):
        """Instantiate a configured strategy with overrides applied."""
        strat = self.cls()
        strat.parameters = self.resolve_params(overrides)
        if force_market_ok:
            strat.parameters["use_market_filter"] = False
        strat.initialize()
        return strat


_REGISTRY: dict[str, SwingStrategyAdapter] = {
    sid: SwingStrategyAdapter(sid, swing.STRATEGIES[sid]) for sid in _ORDER if sid in swing.STRATEGIES
}

# The default strategy materialized after each sync (Minervini — a robust, populated set).
DEFAULT_STRATEGY_ID = "minervini"


def list_strategies() -> list[SwingStrategyAdapter]:
    return list(_REGISTRY.values())


def get_strategy(strategy_id: str) -> SwingStrategyAdapter | None:
    return _REGISTRY.get(strategy_id)


def strategy_meta(strategy: SwingStrategyAdapter) -> dict:
    return {
        "id": strategy.id,
        "name": strategy.name,
        "version": strategy.version,
        "description": strategy.description,
        "param_schema": strategy.param_schema,
        "data_needs": strategy.data_needs,
    }
