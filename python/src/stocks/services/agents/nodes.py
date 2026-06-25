"""LangGraph nodes for the VajraStocks multi-agent research pipeline.

Replaces orchestrator.py + llm_client.py.
Deterministic Python services (TradePlannerService, ConfluenceService) are called
directly — no LLM wrapping needed for math.
"""

from __future__ import annotations

import datetime
import json
import re
from pathlib import Path
from typing import Any

from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.outputs import LLMResult
from langchain_core.runnables import RunnableConfig
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from stocks.config import Config
from stocks.services.agents.state import VajraState

# ─── LLM call logger ─────────────────────────────────────────────────────────

class _LLMLogger(BaseCallbackHandler):
    """Logs every LLM prompt and response via loguru so it appears in the app log."""

    def on_llm_start(self, serialized: dict, prompts: list[str], **kwargs) -> None:
        model = (serialized.get("kwargs") or {}).get("model", "?")
        for i, p in enumerate(prompts, 1):
            logger.info(f"[LLM→{model}] prompt #{i} ({len(p)} chars):\n{'-'*60}\n{p}\n{'-'*60}")

    def on_llm_end(self, response: LLMResult, **kwargs) -> None:
        for gen_list in response.generations:
            for gen in gen_list:
                text = getattr(gen, "text", "") or str(gen)
                usage = getattr(response, "llm_output", {}) or {}
                tokens = usage.get("token_usage") or usage.get("usage") or {}
                logger.info(f"[LLM←] tokens={tokens} | response ({len(text)} chars):\n{'-'*60}\n{text[:3000]}\n{'-'*60}")

    def on_llm_error(self, error: Exception, **kwargs) -> None:
        logger.error(f"[LLM✗] {error}")


_llm_logger = _LLMLogger()

# ─── Agent config loader ─────────────────────────────────────────────────────

_AGENTS_DIR = Path("config/agents")
_agent_configs: dict[str, dict] = {}


def _load_agent_configs() -> None:
    if not _AGENTS_DIR.exists():
        return
    for path in _AGENTS_DIR.glob("*.json"):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
                if name := data.get("name"):
                    _agent_configs[name] = data
        except Exception as exc:
            logger.error(f"Failed to load agent config {path}: {exc}")


_load_agent_configs()


def _sys(agent_name: str) -> str:
    return _agent_configs.get(agent_name, {}).get("system_instruction", "")


def _temp(agent_name: str) -> float:
    return float(_agent_configs.get(agent_name, {}).get("temperature", 0.2))


# ─── LLM factory ─────────────────────────────────────────────────────────────

_OPENAI_COMPAT = {"openai", "groq", "deepseek", "openrouter", "lm_studio", "custom"}


_OLLAMA_TIMEOUT = 900  # 15 minutes — home GPU systems can be slow to generate


def _build_llm(app_config: Config, temperature: float = 0.2):
    provider = app_config.ai.provider.lower().strip()
    model = app_config.ai.model
    base_url = app_config.ai.base_url.rstrip("/")
    api_key = getattr(app_config.ai, "api_key", "") or "none"

    if provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=model,
            base_url=base_url,
            temperature=temperature,
            validate_model_on_init=False,
            num_predict=4096,
            callbacks=[_llm_logger],
            client_kwargs={"timeout": _OLLAMA_TIMEOUT},
            async_client_kwargs={"timeout": _OLLAMA_TIMEOUT},
            sync_client_kwargs={"timeout": _OLLAMA_TIMEOUT},
        )

    import httpx
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=model,
        base_url=base_url,
        api_key=api_key,
        temperature=temperature,
        timeout=_OLLAMA_TIMEOUT,
        callbacks=[_llm_logger],
        http_async_client=httpx.AsyncClient(timeout=_OLLAMA_TIMEOUT),
    )


def _ctx(config: RunnableConfig) -> tuple[Config, Session]:
    c = config.get("configurable", {})
    return c["app_config"], c["db"]


# ─── Pydantic output schemas ─────────────────────────────────────────────────

class IntentResponse(BaseModel):
    intent: str = Field(description="analyze_stock | breakout_scan | swing_trade_scan | market_regime | sql_screening")
    symbol: str | None = Field(default=None, description="Ticker e.g. TCS.NS — null for scan/regime queries")
    rationale: str = Field(default="")


class AnalysisScores(BaseModel):
    symbol: str = Field(default="")
    scores: dict[str, Any] = Field(default_factory=dict)
    technical_audit: dict[str, Any] = Field(default_factory=dict)
    summary: str = Field(default="")


class RegimeOutput(BaseModel):
    regime: str = Field(default="SIDEWAYS")
    volatility_state: str = Field(default="NORMAL")
    key_factors: list[str] = Field(default_factory=list)
    rationale: str = Field(default="")


class ScanOutput(BaseModel):
    opportunities: list[dict[str, Any]] = Field(default_factory=list)
    market_context: str = Field(default="")


class TradeTactics(BaseModel):
    trade_tactics: str = Field(default="")
    setup_name: str = Field(default="Quantitative ATR Target Pattern")


class ReportOutput(BaseModel):
    markdown_report: str = Field(default="")
    executive_recommendation: str = Field(default="NEUTRAL")
    overall_confidence: str = Field(default="MEDIUM")


class SqlAgentOutput(BaseModel):
    sql_query: str = Field(default="")
    parameters: dict[str, Any] = Field(default_factory=dict)
    explanation: str = Field(default="")


# ─── Nodes ───────────────────────────────────────────────────────────────────

_TICKER_RE = re.compile(r'\b([A-Z]{2,20})\.NS\b', re.IGNORECASE)
_SCAN_WORDS = {"scan", "breakout", "momentum", "opportunities", "screener", "find stocks"}
_SWING_WORDS = {"swing", "reversal", "mean reversion"}
_REGIME_WORDS = {"regime", "nifty trend", "market trend", "market outlook", "bull", "bear"}


async def router_node(state: VajraState, config: RunnableConfig) -> dict[str, Any]:
    """Detect intent from the latest user message using heuristics + LLM fallback."""
    app_config, _ = _ctx(config)
    messages = state.get("messages", [])
    user_text = messages[-1].content if messages else ""
    uq = user_text.strip().upper()

    # Fast-path: SQL requests
    if uq.startswith("STOCKS:") or uq.startswith("SELECT") or "SQL" in uq:
        return {"intent": "sql_screening", "symbol": None}

    # Fast-path: explicit stock ticker present → always analyze_stock
    ticker_match = _TICKER_RE.search(user_text)
    if ticker_match:
        symbol = ticker_match.group(1).upper() + ".NS"
        return {"intent": "analyze_stock", "symbol": symbol}

    # Fast-path keyword heuristics (avoids LLM round-trip for clear cases)
    uq_lower = user_text.lower()
    if any(w in uq_lower for w in _SWING_WORDS):
        return {"intent": "swing_trade_scan", "symbol": None}
    if any(w in uq_lower for w in _SCAN_WORDS):
        return {"intent": "breakout_scan", "symbol": None}
    if any(w in uq_lower for w in _REGIME_WORDS):
        return {"intent": "market_regime", "symbol": None}

    # LLM fallback for ambiguous queries
    llm = _build_llm(app_config, _temp("orchestrator"))
    structured = llm.with_structured_output(IntentResponse)

    try:
        result: IntentResponse = await structured.ainvoke([
            SystemMessage(content=_sys("orchestrator")),
            HumanMessage(content=user_text),
        ])
        symbol = result.symbol
        if symbol:
            symbol = symbol.strip().upper()
            if not symbol.endswith(".NS") and not symbol.startswith("^"):
                symbol = f"{symbol}.NS"
            if not re.match(r"^[A-Z0-9.\-]+$", symbol):
                symbol = None
        return {"intent": result.intent or "analyze_stock", "symbol": symbol}
    except Exception as exc:
        logger.error(f"router_node failed: {exc}")
        return {"intent": "analyze_stock", "symbol": None, "error": str(exc)}


async def fetch_data_node(state: VajraState, config: RunnableConfig) -> dict[str, Any]:
    """Fetch OHLCV + technical indicators from the local DB for a single stock."""
    app_config, db = _ctx(config)
    symbol = state.get("symbol") or "RELIANCE.NS"

    from stocks.db.models import (
        DailyHeikinAshi,
        DailyIndicator,
        LineBreakLine,
        RenkoBrick,
        Symbol as SymModel,
    )
    from stocks.services.database import DatabaseService

    sym_obj = db.scalar(select(SymModel).filter_by(symbol=symbol))
    if not sym_obj:
        return {"sql_data": {}, "error": f"Symbol {symbol} not found in database."}

    db_service = DatabaseService(app_config, db)
    sliding_start = datetime.date.today() - datetime.timedelta(days=300)
    prices = db_service.get_prices_for_window(sym_obj.id, sliding_start)

    indicators = db.scalars(
        select(DailyIndicator)
        .filter_by(symbol_id=sym_obj.id)
        .order_by(DailyIndicator.trading_date.desc())
        .limit(14)
    ).all()

    ha = db.scalar(
        select(DailyHeikinAshi)
        .filter_by(symbol_id=sym_obj.id)
        .order_by(DailyHeikinAshi.trading_date.desc())
        .limit(1)
    )
    brick = db.scalar(
        select(RenkoBrick).filter_by(symbol_id=sym_obj.id).order_by(RenkoBrick.brick_index.desc()).limit(1)
    )
    lb = db.scalar(
        select(LineBreakLine).filter_by(symbol_id=sym_obj.id).order_by(LineBreakLine.line_index.desc()).limit(1)
    )

    ind_list = [
        {
            "trading_date": str(r.trading_date),
            "rsi_14": r.rsi_14,
            "atr_14": r.atr_14,
            "sma_20": r.sma_20,
            "sma_50": r.sma_50,
            "sma_200": r.sma_200,
            "macd_line": r.macd_line,
            "macd_signal": r.macd_signal,
            "macd_histogram": r.macd_histogram,
        }
        for r in indicators
    ]

    ha_dir = (
        ha.ha_direction
        if ha and hasattr(ha, "ha_direction")
        else ("UP" if ha and float(ha.close) >= float(ha.open) else "DOWN")
    )

    return {
        "sql_data": {
            "symbol": symbol,
            "prices": prices,
            "ind_list": ind_list,
            "latest_indicators": ind_list[0] if ind_list else {},
            "ha_direction": ha_dir,
            "renko_direction": brick.direction if brick else "UP",
            "line_break_direction": lb.direction if lb else "UP",
        }
    }


async def fetch_market_node(state: VajraState, config: RunnableConfig) -> dict[str, Any]:
    """Fetch Nifty ^NSEI data needed for regime / scan workflows."""
    app_config, db = _ctx(config)

    from stocks.db.models import DailyIndicator, Symbol as SymModel
    from stocks.services.database import DatabaseService

    nifty = db.scalar(select(SymModel).filter_by(symbol="^NSEI"))
    latest_price, sma_200, rsi = 22000.0, 21000.0, 55.0

    if nifty:
        db_service = DatabaseService(app_config, db)
        prices = db_service.get_prices_for_window(
            nifty.id, datetime.date.today() - datetime.timedelta(days=300)
        )
        if prices:
            latest_price = prices[0]["close"]

        ind = db.scalar(
            select(DailyIndicator)
            .filter_by(symbol_id=nifty.id)
            .order_by(DailyIndicator.trading_date.desc())
            .limit(1)
        )
        if ind:
            sma_200 = ind.sma_200 or latest_price * 0.95
            rsi = ind.rsi_14 or 55.0

    return {"market_data": {"latest_price": latest_price, "sma_200": sma_200, "rsi": rsi}}


async def market_regime_node(state: VajraState, config: RunnableConfig) -> dict[str, Any]:
    """Classify broad market regime using the market_regime_agent LLM."""
    app_config, _ = _ctx(config)
    mkt = state.get("market_data", {})
    intent = state.get("intent", "market_regime")

    prompt = (
        f"Evaluate broad Nifty Index (^NSEI) regime at ₹{mkt.get('latest_price', 22000):.2f}. "
        f"200 SMA={mkt.get('sma_200', 21000)}, RSI 14={mkt.get('rsi', 55)}. "
        + (
            "Classify broad market regime trend and volatility state."
            if intent == "market_regime"
            else "Classify regime and volatility for swing/breakout entry filters."
        )
    )

    llm = _build_llm(app_config, _temp("market_regime_agent"))
    try:
        result: RegimeOutput = await llm.with_structured_output(RegimeOutput).ainvoke([
            SystemMessage(content=_sys("market_regime_agent")),
            HumanMessage(content=prompt),
        ])
        updated = {**mkt, "regime": result.model_dump()}
        return {"market_data": updated}
    except Exception as exc:
        logger.error(f"market_regime_node failed: {exc}")
        updated = {**mkt, "regime": {"regime": "SIDEWAYS", "volatility_state": "NORMAL"}}
        return {"market_data": updated, "error": str(exc)}


async def scan_opportunities_node(state: VajraState, config: RunnableConfig) -> dict[str, Any]:
    """Run Python screener sweep + LLM opportunity prioritization."""
    app_config, db = _ctx(config)
    intent = state.get("intent", "breakout_scan")

    from stocks.services.screening import ScreeningService

    svc = ScreeningService(app_config, db)
    if intent == "breakout_scan":
        screened = svc.query_screener(volume_breakout="2.0X", limit=20)
    else:
        screened = svc.query_screener(max_rsi=45.0, limit=20) or svc.query_screener(limit=20)

    opps = [
        {
            "symbol": r.symbol,
            "company_name": r.company_name,
            "close_price": float(r.close_price),
            "volume": int(r.volume),
            "rsi_14": r.rsi_14,
            "renko_direction": r.renko_direction,
            "avg_traded_value": getattr(r, "avg_traded_value", None),
            "volume_breakout_ratio": getattr(r, "volume_breakout_ratio", 1.0),
        }
        for r in screened
    ]

    mkt = state.get("market_data", {})
    prompt = (
        f"Nifty regime: {json.dumps(mkt.get('regime', {}))}. "
        f"Screened stocks: {json.dumps(opps[:15])}. "
        + (
            "Prioritize top breakout setups."
            if intent == "breakout_scan"
            else "Identify high-probability swing reversals."
        )
    )

    llm = _build_llm(app_config, _temp("opportunity_scanner_agent"))
    try:
        result: ScanOutput = await llm.with_structured_output(ScanOutput).ainvoke([
            SystemMessage(content=_sys("opportunity_scanner_agent")),
            HumanMessage(content=prompt),
        ])
        # Merge scanner_context into market_data so report_node can use it
        mkt = state.get("market_data", {})
        return {
            "scan_results": result.opportunities,
            "market_data": {**mkt, "scanner_context": result.market_context},
        }
    except Exception as exc:
        logger.error(f"scan_opportunities_node failed: {exc}")
        return {"scan_results": opps[:5], "error": str(exc)}


async def analyze_stock_node(state: VajraState, config: RunnableConfig) -> dict[str, Any]:
    """Score a single stock's technicals using the stock_analysis_agent LLM."""
    app_config, _ = _ctx(config)
    sql_data = state.get("sql_data", {})
    symbol = sql_data.get("symbol", state.get("symbol", ""))
    prices = sql_data.get("prices", [])
    latest_price = prices[0]["close"] if prices else 100.0
    ind_list = sql_data.get("ind_list", [])
    ind = sql_data.get("latest_indicators", {})

    # Recent price trend (last 10 closes)
    recent_closes = [round(float(p["close"]), 2) for p in prices[:10]] if prices else []

    prompt = (
        f"Perform a full quantitative technical analysis for {symbol}.\n\n"
        f"Current Price: ₹{latest_price:.2f}\n"
        f"Recent 10-day Closes (newest first): {recent_closes}\n\n"
        f"Latest Indicators:\n"
        f"  RSI-14: {ind.get('rsi_14')}\n"
        f"  ATR-14: {ind.get('atr_14')}\n"
        f"  SMA-20: {ind.get('sma_20')}  SMA-50: {ind.get('sma_50')}  SMA-200: {ind.get('sma_200')}\n"
        f"  MACD Line: {ind.get('macd_line')}  Signal: {ind.get('macd_signal')}  Histogram: {ind.get('macd_histogram')}\n\n"
        f"14-Day Indicator History (newest first):\n{json.dumps(ind_list, default=str)}\n\n"
        f"Path-Dependent Chart Signals:\n"
        f"  Heikin-Ashi Direction: {sql_data.get('ha_direction')}\n"
        f"  Renko Direction: {sql_data.get('renko_direction')}\n"
        f"  Three-Line Break Direction: {sql_data.get('line_break_direction')}\n\n"
        f"Score trend strength, momentum, risk, and confidence. Provide a detailed technical summary."
    )

    llm = _build_llm(app_config, _temp("stock_analysis_agent"))
    try:
        result: AnalysisScores = await llm.with_structured_output(AnalysisScores).ainvoke([
            SystemMessage(content=_sys("stock_analysis_agent")),
            HumanMessage(content=prompt),
        ])
        return {"analysis_scores": result.model_dump()}
    except Exception as exc:
        logger.error(f"analyze_stock_node failed: {exc}")
        return {"analysis_scores": {}, "error": str(exc)}


async def analyze_swing_candidates_node(state: VajraState, config: RunnableConfig) -> dict[str, Any]:
    """Score the top 3 swing candidates individually using stock_analysis_agent."""
    app_config, db = _ctx(config)
    candidates = (state.get("scan_results") or [])[:3]

    from stocks.db.models import Symbol as SymModel
    from stocks.services.database import DatabaseService

    db_service = DatabaseService(app_config, db)
    llm = _build_llm(app_config, _temp("stock_analysis_agent"))
    structured = llm.with_structured_output(AnalysisScores)
    scored: list[dict] = []

    for cand in candidates:
        sym_name = cand.get("symbol")
        if not sym_name:
            continue
        sym_obj = db.scalar(select(SymModel).filter_by(symbol=sym_name))
        if not sym_obj:
            continue

        prices = db_service.get_prices_for_window(
            sym_obj.id, datetime.date.today() - datetime.timedelta(days=100)
        )
        prompt = (
            f"Evaluate swing candidate {sym_name} at ₹{cand.get('close_price')}. "
            f"Score trend (-100 to +100) and risk profile."
        )
        try:
            result: AnalysisScores = await structured.ainvoke([
                SystemMessage(content=_sys("stock_analysis_agent")),
                HumanMessage(content=prompt),
            ])
            scored.append({
                "symbol": sym_name,
                "close": cand.get("close_price"),
                "scores": result.scores,
                "audit": result.technical_audit,
                "summary": result.summary,
                "sym_obj_id": sym_obj.id,
                "latest_price": prices[0]["close"] if prices else cand.get("close_price"),
            })
        except Exception as exc:
            logger.warning(f"Swing analysis skipped for {sym_name}: {exc}")

    return {"analysis_candidates": scored}


async def trade_plan_node(state: VajraState, config: RunnableConfig) -> dict[str, Any]:
    """ATR-based trade plan (pure Python) + LLM execution tactics for a single stock."""
    app_config, db = _ctx(config)
    sql_data = state.get("sql_data", {})
    symbol = sql_data.get("symbol", state.get("symbol", ""))
    prices = sql_data.get("prices", [])
    latest_price = prices[0]["close"] if prices else 100.0
    ind = sql_data.get("latest_indicators", {})
    atr_14 = ind.get("atr_14") or latest_price * 0.02
    sma_200 = ind.get("sma_200") or latest_price * 0.95

    from stocks.db.models import Symbol as SymModel, SymbolConfluenceLevel
    from stocks.services.quant.confluence_service import ConfluenceService
    from stocks.services.quant.planner import TradePlannerService

    sym = db.scalar(select(SymModel).filter_by(symbol=symbol))
    support, resistance = sma_200, latest_price * 1.15

    if sym:
        levels = db.scalars(select(SymbolConfluenceLevel).filter_by(symbol_id=sym.id)).all()
        if not levels:
            levels = ConfluenceService(db).calculate_and_save_levels(sym.id)
        supports = sorted(
            [lv for lv in levels if lv.level_type == "SUPPORT"], key=lambda x: float(x.price), reverse=True
        )
        resistances = [lv for lv in levels if lv.level_type == "RESISTANCE"]
        if supports:
            support = float(supports[0].price)
        best_r = ConfluenceService.select_best_resistance(resistances, latest_price, atr_14)
        if best_r:
            resistance = float(best_r.price)

    det_plan = TradePlannerService().calculate_trade_plan(
        symbol=symbol, latest_price=latest_price, atr_14=atr_14, support=support, resistance=resistance
    )

    llm = _build_llm(app_config, _temp("trade_planner_agent"))
    try:
        result: TradeTactics = await llm.with_structured_output(TradeTactics).ainvoke([
            SystemMessage(content=_sys("trade_planner_agent")),
            HumanMessage(content=f"Formulate execution tactics for plan: {json.dumps(det_plan)}."),
        ])
        det_plan["execution"]["tactics"] = result.trade_tactics
        det_plan["setup_name"] = result.setup_name
    except Exception as exc:
        logger.warning(f"trade_plan_node tactics LLM failed: {exc}")

    return {"trade_plan": det_plan}


async def trade_plan_swing_node(state: VajraState, config: RunnableConfig) -> dict[str, Any]:
    """ATR plans + LLM tactics for all scored swing candidates."""
    app_config, db = _ctx(config)
    candidates = state.get("analysis_candidates", [])

    from stocks.db.models import DailyIndicator, SymbolConfluenceLevel
    from stocks.services.quant.confluence_service import ConfluenceService
    from stocks.services.quant.planner import TradePlannerService

    llm = _build_llm(app_config, _temp("trade_planner_agent"))
    structured = llm.with_structured_output(TradeTactics)
    planner = TradePlannerService()
    trade_plans: list[dict] = []

    for cand in candidates:
        sym_id = cand.get("sym_obj_id")
        latest_price = cand.get("latest_price", 100.0)

        ind = None
        if sym_id:
            ind = db.scalar(
                select(DailyIndicator)
                .filter_by(symbol_id=sym_id)
                .order_by(DailyIndicator.trading_date.desc())
                .limit(1)
            )

        atr_14 = (ind.atr_14 if ind and ind.atr_14 else latest_price * 0.02)
        sma_200 = (ind.sma_200 if ind and ind.sma_200 else latest_price * 0.95)

        levels = db.scalars(select(SymbolConfluenceLevel).filter_by(symbol_id=sym_id)).all() if sym_id else []
        if not levels and sym_id:
            levels = ConfluenceService(db).calculate_and_save_levels(sym_id)

        supports = sorted(
            [lv for lv in levels if lv.level_type == "SUPPORT"], key=lambda x: float(x.price), reverse=True
        )
        resistances = [lv for lv in levels if lv.level_type == "RESISTANCE"]
        support = float(supports[0].price) if supports else sma_200
        best_r = ConfluenceService.select_best_resistance(resistances, latest_price, atr_14)
        resistance = float(best_r.price) if best_r else latest_price * 1.15

        plan = planner.calculate_trade_plan(
            symbol=cand["symbol"], latest_price=latest_price, atr_14=atr_14,
            support=support, resistance=resistance,
        )
        try:
            result: TradeTactics = await structured.ainvoke([
                SystemMessage(content=_sys("trade_planner_agent")),
                HumanMessage(content=f"Swing execution tactics for: {json.dumps(plan)}."),
            ])
            plan["execution"]["tactics"] = result.trade_tactics
            plan["setup_name"] = result.setup_name
        except Exception as exc:
            logger.warning(f"Swing tactics LLM skipped for {cand['symbol']}: {exc}")

        plan["scores"] = cand.get("scores", {})
        plan["audit"] = cand.get("audit", {})
        trade_plans.append(plan)

    return {"trade_plan": {"swing_plans": trade_plans}}


async def report_node(state: VajraState, config: RunnableConfig) -> dict[str, Any]:
    """Aggregate all pipeline outputs into a final markdown investment report."""
    app_config, _ = _ctx(config)
    intent = state.get("intent", "analyze_stock")

    today = datetime.date.today().isoformat()

    def _f(v, decimals=2):
        try:
            return f"₹{float(v):.{decimals}f}" if v is not None else "N/A"
        except Exception:
            return "N/A"

    def _n(v, decimals=2):
        try:
            return f"{float(v):.{decimals}f}" if v is not None else "N/A"
        except Exception:
            return "N/A"

    # Build prompt with data embedded inline — not as a trailing JSON blob,
    # so small models actually read and use the real numbers.
    preamble = (
        f"CRITICAL RULES:\n"
        f"- Use ONLY the numbers provided below. Do NOT invent placeholder values, "
        f"hypothetical numbers, estimated dates, or sections you have no data for.\n"
        f"- If a metric is not provided, write N/A — never fill it from your training knowledge.\n"
        f"- Do NOT write 'Hypothetical', '[X]', '[Value]', or any placeholder text.\n"
        f"- Today's date is {today}. Do not use any other date.\n\n"
    )

    if intent == "analyze_stock":
        sql_data = state.get("sql_data", {})
        prices = sql_data.get("prices", [])
        ind = sql_data.get("latest_indicators", {})
        ind_list = sql_data.get("ind_list", [])
        prior = state.get("analysis_scores", {})
        prior_scores = prior.get("scores", {})
        prior_audit = prior.get("technical_audit", {})
        prior_summary = prior.get("summary", "")
        trade = state.get("trade_plan", {})
        exec_block = trade.get("execution", {})
        symbol = state.get("symbol") or sql_data.get("symbol", "N/A")
        price = prices[0]["close"] if prices else None
        recent_closes = [round(float(p["close"]), 2) for p in prices[:10]] if prices else []

        # 14-day indicator history — compact table for trend context
        ind_rows = ""
        for r in ind_list[:14]:
            ind_rows += (
                f"  {r.get('trading_date','?')}  RSI={_n(r.get('rsi_14'))}  "
                f"MACD_H={_n(r.get('macd_histogram'))}  "
                f"SMA20={_f(r.get('sma_20'))}  SMA50={_f(r.get('sma_50'))}\n"
            )

        # Prior analysis block — included as additional context, not as instructions
        prior_block = ""
        if prior_scores or prior_audit:
            prior_block = (
                f"--- Prior Analysis Agent Output (supplementary context — you may agree or disagree) ---\n"
                f"Trend Score     : {prior_scores.get('trend_score', 'N/A')}  (-100 bearish → +100 bullish)\n"
                f"Momentum Score  : {prior_scores.get('momentum_score', 'N/A')}  (-100 → +100)\n"
                f"Risk Score      : {prior_scores.get('risk_score', 'N/A')}  (0 low → 100 high risk)\n"
                f"Confidence Score: {prior_scores.get('confidence_score', 'N/A')}  (0 → 100)\n"
                f"MA Assessment   : {prior_audit.get('moving_averages', 'N/A')}\n"
                f"RSI Assessment  : {prior_audit.get('rsi_assessment', 'N/A')}\n"
                f"Path Agreement  : {prior_audit.get('path_dependent_agreement', 'N/A')}\n"
                f"Agent Summary   : {prior_summary or 'N/A'}\n\n"
            )

        targets = exec_block.get("targets", [])
        data_block = (
            f"=== LIVE MARKET DATA: {symbol} (as of {today}) ===\n\n"
            f"Current Price  : {_f(price)}\n"
            f"Recent 10 Closes (newest first): {recent_closes}\n\n"
            f"--- Momentum & Trend Indicators ---\n"
            f"RSI-14         : {_n(ind.get('rsi_14'))}  (overbought >70, oversold <30)\n"
            f"ATR-14         : {_f(ind.get('atr_14'))}  (daily volatility range)\n"
            f"SMA-20         : {_f(ind.get('sma_20'))}\n"
            f"SMA-50         : {_f(ind.get('sma_50'))}\n"
            f"SMA-200        : {_f(ind.get('sma_200'))}\n"
            f"MACD Line      : {_n(ind.get('macd_line'))}\n"
            f"MACD Signal    : {_n(ind.get('macd_signal'))}\n"
            f"MACD Histogram : {_n(ind.get('macd_histogram'))}\n\n"
            f"--- Path-Dependent Chart Signals ---\n"
            f"Heikin-Ashi    : {sql_data.get('ha_direction', 'N/A')}\n"
            f"Renko          : {sql_data.get('renko_direction', 'N/A')}\n"
            f"Three-Line Break: {sql_data.get('line_break_direction', 'N/A')}\n\n"
            f"--- 14-Day Indicator History (newest first) ---\n"
            f"{ind_rows}\n"
            f"{prior_block}"
            f"--- ATR-Based Trade Levels (reference only) ---\n"
            f"Setup Name     : {trade.get('setup_name', 'N/A')}\n"
            f"Entry Zone     : ₹{exec_block.get('entry_zone', 'N/A')}\n"
            f"Stop-Loss      : {_f(exec_block.get('stop_loss'))}\n"
            f"Target 1       : {_f(targets[0]) if len(targets) > 0 else 'N/A'}\n"
            f"Target 2       : {_f(targets[1]) if len(targets) > 1 else 'N/A'}\n"
            f"Risk/Reward    : {exec_block.get('risk_reward_ratio', 'N/A')}\n"
            f"Position Size  : {exec_block.get('position_size_shares', 'N/A')} shares (₹5,000 risk budget)\n"
            f"Execution Tactics: {exec_block.get('tactics', 'N/A')}\n"
        )

        task = (
            f"You are an expert quantitative analyst. Analyze the data above for {symbol} independently.\n"
            f"The 'Prior Analysis Agent Output' section is supplementary context from a separate scoring agent — "
            f"use it to inform your view but reach your own conclusion. You may agree or disagree with it.\n\n"
            f"Write a publication-ready report in Markdown with these sections:\n"
            f"1. Executive Summary — your own BUY / HOLD / SELL / AVOID stance with clear reasoning\n"
            f"2. Technical Indicators Analysis — interpret RSI, MACD, SMA positioning, ATR\n"
            f"3. Trend & Momentum Assessment — what do the 14-day history and path signals tell you?\n"
            f"4. Prior Analysis Review — where do you agree or disagree with the scoring agent?\n"
            f"5. Trade Levels Review — evaluate the entry/stop/targets; is the R/R acceptable?\n"
            f"6. Risk Caveats — specific risks visible in this data\n"
        )

    elif intent == "breakout_scan":
        mkt = state.get("market_data", {})
        regime = mkt.get("regime", {})
        opps = state.get("scan_results", [])
        data_block = (
            f"=== LIVE MARKET DATA (as of {today}) ===\n\n"
            f"Nifty Price  : {_f(mkt.get('latest_price')) if 'latest_price' in mkt else 'N/A'}\n"
            f"Regime       : {regime.get('regime', 'N/A')}\n"
            f"Volatility   : {regime.get('volatility_state', 'N/A')}\n"
            f"Key Factors  : {', '.join(regime.get('key_factors', []))}\n\n"
            f"Scanner Context: {mkt.get('scanner_context', 'N/A')}\n\n"
            f"--- Screened Breakout Candidates ({len(opps)} total) ---\n"
            f"{json.dumps(opps[:15], default=str)}\n"
        )
        task = (
            f"Write a publication-ready Breakout Scan Report in Markdown.\n"
            f"Sections: 1) Market Regime Overview, "
            f"2) Top Breakout Candidates Table (symbol/price/RSI/volume-ratio/setup-type), "
            f"3) Entry criteria and ATR-based stop-loss notes for each candidate.\n"
        )

    elif intent == "swing_trade_scan":
        mkt = state.get("market_data", {})
        regime = mkt.get("regime", {})
        plans = state.get("trade_plan", {}).get("swing_plans", [])
        data_block = (
            f"=== LIVE MARKET DATA (as of {today}) ===\n\n"
            f"Regime     : {regime.get('regime', 'N/A')}\n"
            f"Volatility : {regime.get('volatility_state', 'N/A')}\n\n"
            f"Scanner Context: {mkt.get('scanner_context', 'N/A')}\n\n"
            f"--- Swing Trade Plans ({len(plans)} candidates) ---\n"
            f"{json.dumps(plans, default=str)}\n"
        )
        task = (
            f"Write a publication-ready Swing Trade Scan Report in Markdown.\n"
            f"Sections: 1) Market Regime Overview, "
            f"2) Top Swing Candidates each with full ATR trade plan in ₹, "
            f"3) Risk management guidelines.\n"
        )

    else:  # market_regime
        mkt = state.get("market_data", {})
        regime = mkt.get("regime", {})
        data_block = (
            f"=== LIVE NIFTY DATA (as of {today}) ===\n\n"
            f"Nifty Price : {_f(mkt.get('latest_price')) if 'latest_price' in mkt else 'N/A'}\n"
            f"SMA-200     : {_f(mkt.get('sma_200')) if 'sma_200' in mkt else 'N/A'}\n"
            f"RSI-14      : {_n(mkt.get('rsi')) if 'rsi' in mkt else 'N/A'}\n"
            f"Regime      : {regime.get('regime', 'N/A')}\n"
            f"Volatility  : {regime.get('volatility_state', 'N/A')}\n"
            f"Key Factors : {', '.join(regime.get('key_factors', []))}\n"
            f"Rationale   : {regime.get('rationale', 'N/A')}\n"
        )
        task = (
            f"Write a publication-ready Market Regime Report in Markdown.\n"
            f"Sections: 1) Nifty Trend Classification with price context, "
            f"2) Volatility State analysis, "
            f"3) Implications for swing/breakout traders.\n"
        )

    prompt = preamble + data_block + "\n" + task

    llm = _build_llm(app_config, _temp("report_agent"))
    try:
        response = await llm.ainvoke([
            SystemMessage(content=_sys("report_agent")),
            HumanMessage(content=prompt),
        ])
        report_text = response.content or ""

        rec_match = re.search(r'recommendation:\s*(BULLISH|BEARISH|NEUTRAL|AVOID)', report_text, re.IGNORECASE)
        conf_match = re.search(r'confidence:\s*(HIGH|MEDIUM|LOW)', report_text, re.IGNORECASE)
        recommendation = rec_match.group(1).upper() if rec_match else "NEUTRAL"
        confidence = conf_match.group(1).upper() if conf_match else "MEDIUM"

        return {"report": report_text, "recommendation": recommendation, "confidence": confidence}
    except Exception as exc:
        logger.error(f"report_node failed: {exc}")
        return {"report": "", "recommendation": "NEUTRAL", "confidence": "LOW", "error": str(exc)}


async def sql_screen_node(state: VajraState, config: RunnableConfig) -> dict[str, Any]:
    """Natural language → SQL screening with self-healing retry (up to 3 attempts)."""
    app_config, db = _ctx(config)
    messages = state.get("messages", [])
    user_query = messages[-1].content if messages else ""

    llm = _build_llm(app_config, _temp("sql_data_agent"))
    structured = llm.with_structured_output(SqlAgentOutput)

    current_prompt = f"Identify matching stocks based on criteria:\n{user_query}"
    sql_error: str | None = None
    query = ""
    explanation = ""
    db_rows: list = []

    for attempt in range(1, 4):
        try:
            sql_res: SqlAgentOutput = await structured.ainvoke([
                SystemMessage(content=_sys("sql_data_agent")),
                HumanMessage(content=current_prompt),
            ])
            query = sql_res.sql_query
            explanation = sql_res.explanation

            qu = query.strip().upper()
            if not (qu.startswith("SELECT") or qu.startswith("WITH")):
                raise ValueError("Security: only SELECT queries are permitted.")

            for kw in ("DROP", "DELETE", "UPDATE", "ALTER", "TRUNCATE", "INSERT", "CREATE", "EXEC", "MERGE"):
                if kw in qu:
                    raise ValueError(f"Security: forbidden keyword '{kw}' detected.")

            db_rows = db.execute(text(query), sql_res.parameters).all()
            sql_error = None
            break
        except Exception as exc:
            logger.warning(f"SQL attempt {attempt} failed: {exc}")
            sql_error = str(exc)
            try:
                db.rollback()
            except Exception:
                pass
            current_prompt = (
                f"The MSSQL query failed (attempt {attempt}):\nError: {sql_error}\n"
                f"SQL was:\n{query}\n\n"
                f"Fix using MSSQL-compatible syntax. Original request: {user_query}"
            )

    if sql_error:
        return {
            "report": f"# SQL Screening Error\n\nFailed after 3 attempts: {sql_error}",
            "recommendation": "NEUTRAL",
            "confidence": "LOW",
            "screener_rows": [],
            "error": sql_error,
        }

    screener_rows: list[dict] = []
    for r in db_rows:
        row = {k.lower(): v for k, v in (r._mapping.items() if hasattr(r, "_mapping") else dict(r).items())}
        close_price = float(row.get("close_price") or row.get("close") or 0.0)
        rsi_14 = row.get("rsi_14")
        try:
            rsi_14 = float(rsi_14) if rsi_14 is not None else None
        except Exception:
            rsi_14 = None
        screener_rows.append({
            "symbol": row.get("symbol", ""),
            "company_name": row.get("company_name", ""),
            "close_price": close_price,
            "volume": int(row.get("volume") or 0),
            "rsi_14": rsi_14,
            "ha_direction": row.get("ha_direction", ""),
            "renko_direction": row.get("renko_direction", ""),
            "line_break_direction": row.get("line_break_direction", ""),
            "macd_trend": row.get("macd_trend", ""),
            "avg_traded_value": row.get("avg_traded_value"),
            "volume_breakout_ratio": row.get("volume_breakout_ratio"),
        })

    md = (
        f"# SQL Screening Results\n\n"
        f"**Criteria:**\n```\n{user_query}\n```\n\n"
        f"**SQL:**\n```sql\n{query}\n```\n\n"
        f"**{explanation}**\n\n"
        f"### {len(screener_rows)} stock(s) found\n\n"
    )
    if screener_rows:
        md += "| Symbol | Company | Close | Volume | RSI | Renko | Line Break |\n"
        md += "| :--- | :--- | ---: | ---: | ---: | :--- | :--- |\n"
        for s in screener_rows[:20]:
            rsi_str = f"{s['rsi_14']:.1f}" if s.get("rsi_14") is not None else "N/A"
            md += (
                f"| **{s['symbol']}** | {s['company_name']} | ₹{s['close_price']:.2f} "
                f"| {s['volume']:,} | {rsi_str} | {s['renko_direction'] or 'N/A'} "
                f"| {s['line_break_direction'] or 'N/A'} |\n"
            )
        if len(screener_rows) > 20:
            md += f"\n*… and {len(screener_rows) - 20} more.*"
    else:
        md += "> No stocks matched the filtering criteria."

    return {
        "report": md,
        "recommendation": "BULLISH" if screener_rows else "NEUTRAL",
        "confidence": "HIGH",
        "screener_rows": screener_rows,
    }
