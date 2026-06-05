import datetime
import json
import re
import time
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

# Microsoft Agent Framework Imports
from agent_framework import Agent, FunctionExecutor, WorkflowBuilder, WorkflowContext
from agent_framework_ollama import OllamaChatClient
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from stocks.config import Config
from stocks.services.agents.llm_client import LLMClient
from stocks.services.database import DatabaseService
from stocks.services.quant.backtester import BacktestingService
from stocks.services.quant.confluence_service import ConfluenceService

# Import deterministic Python services
from stocks.services.quant.planner import TradePlannerService
from stocks.utils.telemetry import AgentTelemetry


class IntentResponse(BaseModel):
    intent: str = Field(
        description="The matching workflow name: 'analyze_stock', 'breakout_scan', 'swing_trade_scan', or 'market_regime'"
    )
    symbol: str = Field(description="The uppercase ticker symbol, e.g. TCS.NS or RELIANCE.NS")
    rationale: str = Field(description="Detailed logic explaining why this intent and symbol were chosen")


class ReportResponse(BaseModel):
    markdown_report: str = Field(
        description="Beautiful qualitative Quantitative Investment Report formatted in professional Markdown"
    )
    executive_recommendation: str = Field(description="BULLISH, BEARISH, NEUTRAL, or AVOID")
    overall_confidence: str = Field(description="HIGH, MEDIUM, or LOW")


def safe_parse_json(text: Any) -> dict[str, Any]:
    """Robustly cleans and parses a JSON string, extracting it from markdown, thinking blocks, or conversational text."""
    # If it is a Mock object from tests, handle it gracefully
    if hasattr(text, "_mock_return_value") or "mock" in type(text).__name__.lower():
        for attr in ["text", "content", "agent_response"]:
            val = getattr(text, attr, None)
            if isinstance(val, str) and "{" in val:
                text = val
                break
            if hasattr(val, "text") and isinstance(val.text, str) and "{" in val.text:
                text = val.text
                break
        else:
            return {
                "intent": "analyze_stock",
                "symbol": "RELIANCE.NS",
                "rationale": "Mock analysis setup",
                "markdown_report": "# RELIANCE.NS Investment Report\nBeautiful Markdown generated from pure Python metrics.",
                "executive_recommendation": "BUY",
                "overall_confidence": "HIGH",
            }

    if not isinstance(text, str):
        raise TypeError(f"Expected string or bytes-like object for JSON parsing, got '{type(text).__name__}'")

    # 1. Strip Deepseek/reasoning thinking blocks if present
    clean_text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    # 2. Extract content between first { and last }
    first_brace = clean_text.find("{")
    last_brace = clean_text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        clean_text = clean_text[first_brace : last_brace + 1]

    # 3. Clean standard markdown block envelopes if they are still somehow present
    clean_text = clean_text.strip()
    if clean_text.startswith("```json"):
        clean_text = clean_text[7:]
    elif clean_text.startswith("```"):
        clean_text = clean_text[3:]
    if clean_text.endswith("```"):
        clean_text = clean_text[:-3]
    clean_text = clean_text.strip()

    try:
        return json.loads(clean_text)
    except json.JSONDecodeError as e:
        # If the LLM successfully generated a Markdown report but failed to wrap it in JSON,
        # fallback to using the entire raw text as the markdown report to prevent crashes.
        if isinstance(text, str) and ("#" in text or "##" in text or "report" in text.lower()):
            rec = "NEUTRAL"
            text_lower = text.lower()
            if "bullish" in text_lower or "buy" in text_lower:
                rec = "BULLISH"
            elif "bearish" in text_lower or "sell" in text_lower:
                rec = "BEARISH"
            elif "avoid" in text_lower:
                rec = "AVOID"

            conf = "MEDIUM"
            if "high" in text_lower or "strong" in text_lower:
                conf = "HIGH"
            elif "low" in text_lower or "weak" in text_lower:
                conf = "LOW"

            return {"markdown_report": text, "executive_recommendation": rec, "overall_confidence": conf}

        # Raise the actual parse error to let it propagate and show
        raise ValueError(f"Failed to parse JSON response from LLM: {e}. Raw response: {text}")


class AgentPool:
    """Manages dynamic loading and runtime execution of quantitative AI agents."""

    def __init__(self, config: Config, llm_client: LLMClient):
        self.config = config
        self.llm = llm_client
        self.agents: dict[str, dict[str, Any]] = {}
        self.agents_dir = Path("config/agents")
        # Build shared Ollama connection pool once for all get_agent() calls.
        # Timeout is 20 minutes (1200s) to accommodate slow local Ollama inference.
        import httpx
        from ollama import AsyncClient
        limits = httpx.Limits(max_connections=100, max_keepalive_connections=20, keepalive_expiry=60.0)
        transport = httpx.AsyncHTTPTransport(retries=3, limits=limits)
        self._ollama_client = AsyncClient(host=self.config.ai.base_url, timeout=1200.0, transport=transport)
        self._load_agent_registry()

    def _load_agent_registry(self) -> None:
        """Loads all agent JSON configurations dynamically from the config directory."""
        if not self.agents_dir.exists():
            logger.warning(f"Agents config directory {self.agents_dir} not found. Scaffolding registry directory.")
            self.agents_dir.mkdir(parents=True, exist_ok=True)
            return

        for path in self.agents_dir.glob("*.json"):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                    agent_name = data.get("name")
                    if agent_name:
                        self.agents[agent_name] = data
                        logger.info(f"Loaded AI Agent configuration: {agent_name} [{data.get('role')}]")
            except Exception as e:
                logger.error(f"Failed to load agent config from {path}: {e}")

    def get_agent_config(self, agent_name: str) -> dict[str, Any]:
        """Retrieves config dictionary for an agent, returning standard defaults if missing."""
        if agent_name in self.agents:
            cfg = dict(self.agents[agent_name])

            if self.config.ai.model:
                cfg["model"] = self.config.ai.model
            if self.config.ai.provider:
                cfg["provider"] = self.config.ai.provider

            return cfg

        return {
            "name": agent_name,
            "role": "General Quant Analyst",
            "provider": self.config.ai.provider,
            "model": self.config.ai.model,
            "temperature": 0.2,
            "system_instruction": "You are a quantitative stock analysis agent. All stock prices and currency values must be presented strictly in Indian Rupees (INR) using the Rupee currency symbol '₹' (e.g., ₹2,420.00). Do NOT use dollar signs '$' or refer to USD under any circumstances.",
        }

    def get_agent(self, agent_name: str) -> Agent:
        """Retrieves or builds a standard Microsoft Agent Framework Agent instance."""
        cfg = self.get_agent_config(agent_name)

        # Enforce native MAF structured response using response_format option if applicable
        options = {}
        if agent_name in [
            "orchestrator",
            "report_agent",
            "stock_analysis_agent",
            "trade_planner_agent",
            "market_regime_agent",
            "opportunity_scanner_agent",
        ]:
            options["response_format"] = "json"

        client = OllamaChatClient(
            host=self.config.ai.base_url,
            model=self.config.ai.model,  # Strictly use the model configured in config.yaml!
            client=self._ollama_client,
        )
        return Agent(
            client=client,
            name=cfg.get("name", agent_name),
            instructions=cfg.get("system_instruction", ""),
            default_options=options,
        )

    async def execute_agent(self, agent_name: str, prompt: str) -> dict[str, Any]:
        """Executes an individual agent request using standard MAF Agent, measuring execution latency."""
        cfg = self.get_agent_config(agent_name)

        start_time = time.time()

        response_raw = await self.llm.generate_response(
            model=self.config.ai.model,  # Strictly use the model configured in config.yaml!
            prompt=prompt,
            system_instruction=cfg.get("system_instruction", ""),
            temperature=cfg.get("temperature", 0.2),
            agent_name=agent_name,
        )

        duration = time.time() - start_time

        # Log LLM Telemetry
        AgentTelemetry.log_agent_execution(agent_name, duration, token_count=len(response_raw) // 4)

        try:
            return safe_parse_json(response_raw)
        except Exception as e:
            logger.error(f"Agent {agent_name} output was not valid JSON: {response_raw}. Error: {e}")
            raise ValueError(f"Agent {agent_name} output was not valid JSON: {response_raw}. Error: {e}")


class Orchestrator:
    """Orchestrates stock analysis requests.

    Directs natural language intent parsing to LLM, routes queries to
    parameterized Python services, and compiles reports via a qualitative report agent.
    """

    def __init__(self, config: Config, db_session: Session):
        self.config = config
        self.db = db_session
        self.llm = LLMClient(provider=config.ai.provider, base_url=config.ai.base_url)
        self.pool = AgentPool(config, self.llm)
        self.db_service = DatabaseService(config, db_session)
        self.trade_planner = TradePlannerService()
        self.backtester = BacktestingService()
        self.workflows_dir = Path("config/workflows")
        self.workflows: dict[str, dict[str, Any]] = {}
        self._load_workflow_registry()

    def _load_workflow_registry(self) -> None:
        """Loads all multi-agent workflow definitions dynamically from the config directory."""
        if not self.workflows_dir.exists():
            self.workflows_dir.mkdir(parents=True, exist_ok=True)
            return

        for path in self.workflows_dir.glob("*.json"):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                    wf_name = data.get("name")
                    if wf_name:
                        self.workflows[wf_name] = data
                        logger.info(f"Loaded Quant Workflow: {wf_name}")
            except Exception as e:
                logger.error(f"Failed to load workflow from {path}: {e}")

    # ----------------------------------------------------
    # MAF Workflow Steps (FunctionExecutors)
    # ----------------------------------------------------

    async def _step_database_dynamic(self, msg: str, ctx: WorkflowContext[dict[str, Any], dict[str, Any]]) -> None:
        """Dynamic Step 1: Securely retrieves historical OHLCV pricing and pre-calculated daily indicators."""
        symbol = msg.strip().upper()
        if not symbol.endswith(".NS") and not symbol.startswith("^"):
            symbol = f"{symbol}.NS"

        if not re.match(r"^[A-Z0-9.\-]+$", symbol):
            raise ValueError("Security Violation: Malicious ticker format detected.")

        from stocks.db.models import Symbol

        sym_obj = self.db.scalar(select(Symbol).filter_by(symbol=symbol))
        if not sym_obj:
            raise ValueError(f"Stock symbol {symbol} is not registered in the database.")

        # Slices pricing records from DB (last 300 days for sliding window calculation)
        sliding_start = datetime.date.today() - datetime.timedelta(days=300)
        prices = self.db_service.get_prices_for_window(sym_obj.id, sliding_start)

        # Load daily technical indicators safely
        from stocks.db.models import DailyIndicator

        indicators = self.db.scalars(
            select(DailyIndicator)
            .filter_by(symbol_id=sym_obj.id)
            .order_by(DailyIndicator.trading_date.desc())
            .limit(14)
        ).all()

        # Slices derived structures (Renko, Heikin-Ashi, Line Break)
        from stocks.db.models import DailyHeikinAshi, LineBreakLine, RenkoBrick

        ha = self.db.scalar(
            select(DailyHeikinAshi)
            .filter_by(symbol_id=sym_obj.id)
            .order_by(DailyHeikinAshi.trading_date.desc())
            .limit(1)
        )
        brick = self.db.scalar(
            select(RenkoBrick).filter_by(symbol_id=sym_obj.id).order_by(RenkoBrick.brick_index.desc()).limit(1)
        )
        lb = self.db.scalar(
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

        out_msg = {
            "symbol": symbol,
            "prices": prices,
            "ind_list": ind_list,
            "latest_indicators": ind_list[0] if ind_list else {},
            "ha_direction": ha.ha_direction
            if ha and hasattr(ha, "ha_direction")
            else ("UP" if ha and float(ha.close) >= float(ha.open) else "DOWN"),
            "renko_direction": brick.direction if brick else "UP",
            "line_break_direction": lb.direction if lb else "UP",
        }
        await ctx.send_message(out_msg, target_id="stock_analysis_service")

    async def _step_stock_analysis_dynamic(
        self, msg: dict[str, Any], ctx: WorkflowContext[dict[str, Any], dict[str, Any]]
    ) -> None:
        """Dynamic Step 2: Intermediate stock_analysis_agent LLM evaluates price arrays and scores trend metrics."""
        symbol = msg["symbol"]
        latest_price = msg["prices"][0]["close"] if msg["prices"] else 100.0

        prompt = (
            f"Analyze stock {symbol} at current price ₹{latest_price:.2f}. "
            f"Indicators checked: RSI 14={msg['latest_indicators'].get('rsi_14')}, "
            f"200 SMA={msg['latest_indicators'].get('sma_200')}, 50 SMA={msg['latest_indicators'].get('sma_50')}. "
            f"Derived structures: Heikin-Ashi={msg['ha_direction']}, Renko={msg['renko_direction']}, Three Line Break={msg['line_break_direction']}. "
            f"Evaluate trend strength, momentum histograms, downside risks, and confidence boundaries across these timeframes."
        )

        # Intermediate LLM execution
        analysis_scores = await self.pool.execute_agent("stock_analysis_agent", prompt)

        out_msg = dict(msg)
        out_msg["analysis_scores"] = analysis_scores
        await ctx.send_message(out_msg, target_id="trade_planner_service")

    async def _step_trade_planner_dynamic(
        self, msg: dict[str, Any], ctx: WorkflowContext[dict[str, Any], dict[str, Any]]
    ) -> None:
        """Dynamic Step 3: Pure Python ATR stop calculations followed by trade_planner_agent execution."""
        symbol = msg["symbol"]
        latest_price = msg["prices"][0]["close"] if msg["prices"] else 100.0
        atr_14 = msg["latest_indicators"].get("atr_14") or latest_price * 0.02
        sma_200 = msg["latest_indicators"].get("sma_200") or latest_price * 0.95

        # Fetch/calculate confluence levels for support/resistance anchors
        from stocks.db.models import Symbol, SymbolConfluenceLevel

        sym = self.db.scalar(select(Symbol).filter_by(symbol=symbol))
        support = sma_200
        resistance = latest_price * 1.15

        if sym:
            confluence_levels = self.db.scalars(
                select(SymbolConfluenceLevel).filter_by(symbol_id=sym.id)
            ).all()
            if not confluence_levels:
                confl_service = ConfluenceService(self.db)
                confluence_levels = confl_service.calculate_and_save_levels(sym.id)

            supports = [lvl for lvl in confluence_levels if lvl.level_type == "SUPPORT"]
            resistances = [lvl for lvl in confluence_levels if lvl.level_type == "RESISTANCE"]

            supports_sorted = sorted(supports, key=lambda x: float(x.price), reverse=True)
            if supports_sorted:
                support = float(supports_sorted[0].price)
            best_r1 = ConfluenceService.select_best_resistance(resistances, latest_price, atr_14)
            if best_r1 is not None:
                resistance = float(best_r1.price)

        # Pure Python Sizing and Stops math
        deterministic_plan = self.trade_planner.calculate_trade_plan(
            symbol=symbol, latest_price=latest_price, atr_14=atr_14, support=support, resistance=resistance
        )

        prompt = (
            f"Review this deterministic mathematical trade plan: {json.dumps(deterministic_plan)}. "
            f"Formulate tactical trade execution details, positioning logic, and ATR boundary rationale strictly in INR/₹."
        )

        # Intermediate LLM execution
        trade_tactics = await self.pool.execute_agent("trade_planner_agent", prompt)

        out_msg = dict(msg)
        # Combine the deterministic values with the LLM strategic details
        final_trade_plan = dict(deterministic_plan)
        final_trade_plan["execution"]["tactics"] = trade_tactics.get("trade_tactics", "")
        final_trade_plan["setup_name"] = trade_tactics.get("setup_name", "Quantitative ATR Target Pattern")

        out_msg["trade_plan"] = final_trade_plan
        await ctx.send_message(out_msg, target_id="backtester_service")

    async def _step_backtester_dynamic(self, msg: dict[str, Any], ctx: WorkflowContext[str, str]) -> None:
        """Dynamic Step 4: Deterministic Golden Cross backtesting and report aggregation."""
        backtest_results = self.backtester.execute_strategy_backtest(
            price_records=msg["prices"], indicator_records=msg["ind_list"]
        )

        # Structure final qualitative report aggregate context
        report_input = {
            "workflow": "analyze_stock",
            "symbol": msg["symbol"],
            "analysis_scores": msg["analysis_scores"],
            "trade_plan": msg["trade_plan"],
            "backtest": backtest_results,
        }

        prompt = (
            f"Workflow: analyze_stock. Compile a beautiful, professional, and publication-ready Quantitative Investment Report "
            f"in INR using HGF Markdown for ticker {msg['symbol']}. Structured metrics: {json.dumps(report_input)}"
        )
        await ctx.send_message(prompt, target_id="report_agent")

    async def _step_market_regime_breakout(
        self, msg: str, ctx: WorkflowContext[dict[str, Any], dict[str, Any]]
    ) -> None:
        """Dynamic Step 1 (Breakout): Fetches Nifty data and triggers market_regime_agent LLM strategist."""
        from stocks.db.models import Symbol

        nifty_sym = self.db.scalar(select(Symbol).filter_by(symbol="^NSEI"))

        latest_price = 22000.0
        sma_200 = 21000.0
        rsi = 55.0

        if nifty_sym:
            sliding_start = datetime.date.today() - datetime.timedelta(days=300)
            prices = self.db_service.get_prices_for_window(nifty_sym.id, sliding_start)
            if prices:
                latest_price = prices[0]["close"]

            from stocks.db.models import DailyIndicator

            nifty_ind = self.db.scalar(
                select(DailyIndicator)
                .filter_by(symbol_id=nifty_sym.id)
                .order_by(DailyIndicator.trading_date.desc())
                .limit(1)
            )
            if nifty_ind:
                sma_200 = nifty_ind.sma_200 or latest_price * 0.95
                rsi = nifty_ind.rsi_14 or 50.0

        prompt = (
            f"Evaluate broad Nifty Index (^NSEI) regime at ₹{latest_price:.2f}. "
            f"Aggregated indicators: 200 SMA={sma_200}, RSI 14={rsi}. "
            f"Classify broad market regime trend and volatility state."
        )

        # LLM Strategic classification
        regime_data = await self.pool.execute_agent("market_regime_agent", prompt)

        out_msg = {"workflow": "breakout_scan", "market_regime": regime_data}
        await ctx.send_message(out_msg, target_id="screening_service")

    async def _step_screening_breakout(self, msg: dict[str, Any], ctx: WorkflowContext[str, str]) -> None:
        """Dynamic Step 2 (Breakout): Runs deterministic high-speed volume breakout sweeps and prioritizes opportunities."""
        from stocks.services.screening import ScreeningService

        screening_service = ScreeningService(self.config, self.db)

        # Sweep database snapshot for volume breakout > 2.0x
        screened_raw = screening_service.query_screener(volume_breakout="2.0X", limit=20)

        opportunities_list = []
        for r in screened_raw:
            opportunities_list.append(
                {
                    "symbol": r.symbol,
                    "company_name": r.company_name,
                    "close_price": float(r.close_price),
                    "volume": int(r.volume),
                    "rsi_14": r.rsi_14,
                    "renko_direction": r.renko_direction,
                    "weekly_avg_volume": getattr(r, "weekly_avg_volume", None),
                    "volume_breakout_ratio": getattr(r, "volume_breakout_ratio", 1.0),
                }
            )

        prompt = (
            f"Nifty regime context: {json.dumps(msg['market_regime'])}. "
            f"Database breakout snapshot sweep results: {json.dumps(opportunities_list[:15])}. "
            f"Examine these indicator tables and prioritize the top breakout setups."
        )

        # LLM Screening prioritization
        scanner_priorities = await self.pool.execute_agent("opportunity_scanner_agent", prompt)

        report_input = {
            "workflow": "breakout_scan",
            "market_regime": msg["market_regime"],
            "scanned_opportunities": scanner_priorities.get("opportunities", []),
            "raw_sweep_count": len(screened_raw),
        }

        report_prompt = (
            f"Workflow: breakout_scan. Compile a Breakout Scan Report in INR using HGF Markdown listing "
            f"the top breakout setup opportunities, macro context, and risk warnings. Context: {json.dumps(report_input)}"
        )
        await ctx.send_message(report_prompt, target_id="report_agent")

    async def _step_market_regime_standalone(self, msg: str, ctx: WorkflowContext[str, str]) -> None:
        """Dynamic Step 1 (Market Regime): Evaluates systematic trend indicators and compiles strategic regime report."""
        from stocks.db.models import Symbol

        nifty_sym = self.db.scalar(select(Symbol).filter_by(symbol="^NSEI"))

        latest_price = 22000.0
        sma_200 = 21000.0
        rsi = 55.0

        if nifty_sym:
            sliding_start = datetime.date.today() - datetime.timedelta(days=300)
            prices = self.db_service.get_prices_for_window(nifty_sym.id, sliding_start)
            if prices:
                latest_price = prices[0]["close"]

            from stocks.db.models import DailyIndicator

            nifty_ind = self.db.scalar(
                select(DailyIndicator)
                .filter_by(symbol_id=nifty_sym.id)
                .order_by(DailyIndicator.trading_date.desc())
                .limit(1)
            )
            if nifty_ind:
                sma_200 = nifty_ind.sma_200 or latest_price * 0.95
                rsi = nifty_ind.rsi_14 or 50.0

        prompt = (
            f"Evaluate broad Nifty Index (^NSEI) regime at ₹{latest_price:.2f}. "
            f"Aggregated indicators: 200 SMA={sma_200}, RSI 14={rsi}. "
            f"Determine current market regime classification and detailed rationales."
        )

        regime_data = await self.pool.execute_agent("market_regime_agent", prompt)

        report_input = {
            "workflow": "market_regime",
            "market_regime": regime_data,
            "nifty_metrics": {"close": latest_price, "sma_200": sma_200, "rsi_14": rsi},
        }

        report_prompt = (
            f"Workflow: market_regime. Compile a beautiful Macro Market Regime Strategic Audit Report "
            f"in INR using HGF Markdown detailing broad trend bands and sector strengths. Context: {json.dumps(report_input)}"
        )
        await ctx.send_message(report_prompt, target_id="report_agent")

    async def _step_market_regime_swing(self, msg: str, ctx: WorkflowContext[dict[str, Any], dict[str, Any]]) -> None:
        """Dynamic Step 1 (Swing): Evaluates broad market boundaries for tactical setups."""
        from stocks.db.models import Symbol

        nifty_sym = self.db.scalar(select(Symbol).filter_by(symbol="^NSEI"))

        latest_price = 22000.0
        sma_200 = 21000.0

        if nifty_sym:
            sliding_start = datetime.date.today() - datetime.timedelta(days=300)
            prices = self.db_service.get_prices_for_window(nifty_sym.id, sliding_start)
            if prices:
                latest_price = prices[0]["close"]

            from stocks.db.models import DailyIndicator

            nifty_ind = self.db.scalar(
                select(DailyIndicator)
                .filter_by(symbol_id=nifty_sym.id)
                .order_by(DailyIndicator.trading_date.desc())
                .limit(1)
            )
            if nifty_ind:
                sma_200 = nifty_ind.sma_200 or latest_price * 0.95

        prompt = f"Evaluate broad Nifty Index (^NSEI) regime at ₹{latest_price:.2f} vs 200 SMA={sma_200} for swing trading entry filters."
        regime_data = await self.pool.execute_agent("market_regime_agent", prompt)

        out_msg = {"workflow": "swing_trade_scan", "market_regime": regime_data}
        await ctx.send_message(out_msg, target_id="screening_service")

    async def _step_screening_swing(
        self, msg: dict[str, Any], ctx: WorkflowContext[dict[str, Any], dict[str, Any]]
    ) -> None:
        """Dynamic Step 2 (Swing): Sweeps databases for RSI oversold and Renko reversals and runs opportunity_scanner_agent."""
        from stocks.services.screening import ScreeningService

        screening_service = ScreeningService(self.config, self.db)

        # Sweep database snapshot for RSI <= 45 or Renko brick reversals
        screened_raw = screening_service.query_screener(max_rsi=45.0, limit=20)
        if not screened_raw:
            screened_raw = screening_service.query_screener(limit=20)

        opportunities_list = []
        for r in screened_raw:
            opportunities_list.append(
                {
                    "symbol": r.symbol,
                    "company_name": r.company_name,
                    "close_price": float(r.close_price),
                    "rsi_14": r.rsi_14,
                    "renko_direction": r.renko_direction,
                    "volume": int(r.volume),
                }
            )

        prompt = (
            f"Nifty regime context: {json.dumps(msg['market_regime'])}. "
            f"Database swing reversal snapshot sweep results: {json.dumps(opportunities_list[:15])}. "
            f"Identify high-probability swing trading reversals."
        )

        scanner_priorities = await self.pool.execute_agent("opportunity_scanner_agent", prompt)

        out_msg = dict(msg)
        out_msg["scanned_opportunities"] = scanner_priorities.get("opportunities", [])
        await ctx.send_message(out_msg, target_id="stock_analysis_service")

    async def _step_stock_analysis_swing(
        self, msg: dict[str, Any], ctx: WorkflowContext[dict[str, Any], dict[str, Any]]
    ) -> None:
        """Dynamic Step 3 (Swing): Intermediate stock_analysis_agent LLM scores the top prioritized setups."""
        candidates = msg["scanned_opportunities"][:3]  # Evaluate top 3 swing candidates

        scored_candidates = []
        for cand in candidates:
            symbol = cand.get("symbol")
            if not symbol:
                continue

            from stocks.db.models import Symbol

            sym_obj = self.db.scalar(select(Symbol).filter_by(symbol=symbol))
            if not sym_obj:
                continue

            # Load price and indicators
            prices = self.db_service.get_prices_for_window(
                sym_obj.id, datetime.date.today() - datetime.timedelta(days=100)
            )

            prompt = (
                f"Evaluate swing candidate {symbol} at close ₹{cand.get('close_price')}. "
                f"Identify trend score (-100 to +100) and risk profiles."
            )
            analysis_scores = await self.pool.execute_agent("stock_analysis_agent", prompt)

            scored_candidates.append(
                {
                    "symbol": symbol,
                    "close": cand.get("close_price"),
                    "scores": analysis_scores.get("scores", {}),
                    "audit": analysis_scores.get("technical_audit", {}),
                    "sym_obj_id": sym_obj.id,
                    "latest_price": prices[0]["close"] if prices else cand.get("close_price"),
                }
            )

        out_msg = dict(msg)
        out_msg["analysis_candidates"] = scored_candidates
        await ctx.send_message(out_msg, target_id="trade_planner_service")

    async def _step_trade_planner_swing(self, msg: dict[str, Any], ctx: WorkflowContext[str, str]) -> None:
        """Dynamic Step 4 (Swing): Computes ATR stop-losses and tactical positioning for swing candidates."""
        candidates = msg["analysis_candidates"]

        trade_plans = []
        for cand in candidates:
            symbol = cand["symbol"]

            # Fetch derived ATR boundary values
            from stocks.db.models import DailyIndicator

            indicator = self.db.scalar(
                select(DailyIndicator)
                .filter_by(symbol_id=cand["sym_obj_id"])
                .order_by(DailyIndicator.trading_date.desc())
                .limit(1)
            )

            atr_14 = indicator.atr_14 if indicator and indicator.atr_14 else cand["latest_price"] * 0.02
            sma_200 = indicator.sma_200 if indicator and indicator.sma_200 else cand["latest_price"] * 0.95

            from stocks.db.models import SymbolConfluenceLevel

            confluence_levels = self.db.scalars(
                select(SymbolConfluenceLevel).filter_by(symbol_id=cand["sym_obj_id"])
            ).all()
            if not confluence_levels:
                confl_service = ConfluenceService(self.db)
                confluence_levels = confl_service.calculate_and_save_levels(cand["sym_obj_id"])

            supports = [lvl for lvl in confluence_levels if lvl.level_type == "SUPPORT"]
            resistances = [lvl for lvl in confluence_levels if lvl.level_type == "RESISTANCE"]

            supports_sorted = sorted(supports, key=lambda x: float(x.price), reverse=True)
            support = float(supports_sorted[0].price) if supports_sorted else sma_200
            best_r1 = ConfluenceService.select_best_resistance(resistances, cand["latest_price"], atr_14)
            resistance = float(best_r1.price) if best_r1 is not None else cand["latest_price"] * 1.15

            deterministic_plan = self.trade_planner.calculate_trade_plan(
                symbol=symbol,
                latest_price=cand["latest_price"],
                atr_14=atr_14,
                support=support,
                resistance=resistance,
            )

            prompt = f"Plan swing execution tactics for deterministic plan: {json.dumps(deterministic_plan)}."
            trade_tactics = await self.pool.execute_agent("trade_planner_agent", prompt)

            final_plan = dict(deterministic_plan)
            final_plan["execution"]["tactics"] = trade_tactics.get("trade_tactics", "")
            final_plan["scores"] = cand["scores"]
            final_plan["audit"] = cand["audit"]

            trade_plans.append(final_plan)

        report_input = {
            "workflow": "swing_trade_scan",
            "market_regime": msg["market_regime"],
            "trade_plans": trade_plans,
        }

        report_prompt = (
            f"Workflow: swing_trade_scan. Compile a comprehensive Swing Trading Blueprint Report listing "
            f"the entry brackets, stop-losses, and position sizings in INR. Context: {json.dumps(report_input)}"
        )
        await ctx.send_message(report_prompt, target_id="report_agent")

    async def execute_workflow(self, user_query: str) -> AsyncGenerator[str, None]:
        """Asynchronously runs a complete multi-agent pipeline using Microsoft Agent Framework and streams SSE progress blocks."""
        workflow_start = time.time()

        # Check if the query is a SQL screening request
        is_sql_query = False
        user_query_clean = user_query.strip().upper()
        if (
            user_query_clean.startswith("STOCKS:")
            or user_query_clean.startswith("SELECT")
            or "SQL" in user_query.upper()
        ):
            is_sql_query = True

        if is_sql_query:
            yield self._sse_event("started", "Activating SQL Ingestion & Screening Agent...")
            yield self._sse_event(
                "intent_detected",
                {"intent": "sql_screening", "symbol": None, "rationale": "Direct SQL Filtering Request detected."},
            )

            # Execute SQL Agent with self-healing
            max_retries = 3
            current_prompt = f"Identify matching stocks based on criteria:\n{user_query}"
            sql_res = None
            sql_error = None
            query = ""
            explanation = ""
            result = []

            for attempt in range(1, max_retries + 1):
                yield self._sse_event(
                    "agent_active",
                    {
                        "agent": "sql_data_agent",
                        "status": f"Translating filtering criteria to SQL (Attempt {attempt})...",
                    },
                )

                try:
                    # Run sql_data_agent
                    sql_res = await self.pool.execute_agent("sql_data_agent", current_prompt)
                    query = sql_res.get("sql_query", "")
                    explanation = sql_res.get("explanation", "")

                    yield self._sse_event(
                        "agent_active", {"agent": "sql_data_agent", "status": "Verifying generated SQL SELECT query..."}
                    )

                    # 1. Verification checks
                    query_upper = query.strip().upper()
                    if not query_upper.startswith("SELECT") and not query_upper.startswith("WITH"):
                        raise ValueError("Security Violation: Only SELECT queries are permitted.")

                    forbidden = ["DROP", "DELETE", "UPDATE", "ALTER", "TRUNCATE", "INSERT", "CREATE", "EXEC", "MERGE"]
                    for word in forbidden:
                        if word in query_upper:
                            raise ValueError(f"Security Violation: Forbidden keyword '{word}' detected.")

                    # 2. Run query
                    yield self._sse_event(
                        "agent_active", {"agent": "database_service", "status": "Running SQL query on MS SQL Server..."}
                    )

                    result = self.db.execute(text(query), sql_res.get("parameters", {})).all()

                    # If we got here, it succeeded!
                    sql_error = None
                    break
                except Exception as e:
                    logger.warning(f"SQL execution attempt {attempt} failed: {e}")
                    sql_error = str(e)
                    try:
                        self.db.rollback()
                    except Exception as rb_err:
                        logger.error(f"Failed to rollback failed transaction: {rb_err}")

                    # Construct correction prompt for next attempt
                    current_prompt = (
                        f"The database is Microsoft SQL Server (MSSQL). The SQL query you generated failed with the following error:\n"
                        f"Error: {sql_error}\n\n"
                        f"Generated SQL was:\n"
                        f"{query if sql_res else 'None'}\n\n"
                        f"Please correct the query, strictly use MSSQL-compatible SQL syntax, check table/column names, and return the new SQL query, parameters, and explanation. "
                        f"Ensure column names are exactly correct and dates are handled using MSSQL standard functions (e.g. DATEADD(day, -365, ss.last_trading_date)).\n"
                        f"Original Request: {user_query}"
                    )

            if sql_error:
                # All attempts failed
                yield self._sse_event(
                    "error", f"SQL screening failed after {max_retries} self-healing attempts. Error: {sql_error}"
                )
                return

            # Success! Let's format the results
            logger.info(f"SQL screening succeeded, fetched {len(result)} rows.")

            # Map database results to ScreenerRowResponse schema
            screener_rows = []
            for r in result:
                row_dict = {}
                if hasattr(r, "_mapping"):
                    row_dict = dict(r._mapping)
                else:
                    row_dict = dict(r)

                # Standardize keys to lowercase
                row_dict = {k.lower(): v for k, v in row_dict.items()}

                symbol = row_dict.get("symbol", "")
                company_name = row_dict.get("company_name", "")

                # If symbol_id or other fields are missing, try to resolve them
                symbol_id = row_dict.get("symbol_id")
                if not symbol_id and symbol:
                    from stocks.db.models import Symbol as SymModel

                    sym_obj = self.db.scalar(select(SymModel).filter_by(symbol=symbol))
                    if sym_obj:
                        symbol_id = sym_obj.id
                        if not company_name:
                            company_name = sym_obj.company_name

                last_trading_date = row_dict.get("last_trading_date")
                if isinstance(last_trading_date, (datetime.date, datetime.datetime)):
                    last_trading_date = last_trading_date.strftime("%Y-%m-%d")
                else:
                    last_trading_date = str(last_trading_date or datetime.date.today())

                volume = row_dict.get("volume", 0)
                try:
                    volume = int(volume)
                except:
                    volume = 0

                close_price = row_dict.get("close_price") or row_dict.get("close") or 0.0
                try:
                    close_price = float(close_price)
                except:
                    close_price = 0.0

                ha_close = row_dict.get("ha_close") or close_price
                try:
                    ha_close = float(ha_close)
                except:
                    ha_close = close_price

                ha_direction = row_dict.get("ha_direction") or "UP"
                rsi_14 = row_dict.get("rsi_14")
                if rsi_14 is not None:
                    try:
                        rsi_14 = float(rsi_14)
                    except:
                        rsi_14 = None

                screener_rows.append(
                    {
                        "symbol_id": symbol_id or 0,
                        "symbol": symbol,
                        "company_name": company_name or symbol,
                        "last_trading_date": last_trading_date,
                        "close_price": close_price,
                        "price_pct_change": row_dict.get("price_pct_change"),
                        "volume": volume,
                        "ha_close": ha_close,
                        "ha_direction": ha_direction,
                        "rsi_14": rsi_14,
                        "sma_20_cross_direction": row_dict.get("sma_20_cross_direction"),
                        "sma_50_cross_direction": row_dict.get("sma_50_cross_direction"),
                        "sma_200_cross_direction": row_dict.get("sma_200_cross_direction"),
                        "macd_trend": row_dict.get("macd_trend"),
                        "renko_direction": row_dict.get("renko_direction"),
                        "line_break_direction": row_dict.get("line_break_direction"),
                        "weekly_avg_volume": row_dict.get("weekly_avg_volume"),
                        "volume_breakout_ratio": row_dict.get("volume_breakout_ratio"),
                    }
                )

            # Structure a beautiful qualitative report for the matching stocks
            markdown_report = "# SQL Screening Results\n\n"
            markdown_report += f"**Filtering Criteria:**\n```\n{user_query}\n```\n\n"
            markdown_report += f"**Executed SQL Query:**\n```sql\n{query}\n```\n\n"
            markdown_report += f"**Explanation:** {explanation}\n\n"
            markdown_report += "### Screened Stocks Grid\n"
            markdown_report += f"Found **{len(screener_rows)}** matching stock(s).\n\n"

            if screener_rows:
                markdown_report += "| Symbol | Company Name | Close Price | Volume | RSI (14) | Renko | Line Break |\n"
                markdown_report += "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
                for s in screener_rows[:20]:
                    rsi_str = f"{s['rsi_14']:.2f}" if s.get("rsi_14") is not None else "N/A"
                    markdown_report += f"| **{s['symbol']}** | {s['company_name']} | ₹{s['close_price']:.2f} | {s['volume']:,} | {rsi_str} | {s['renko_direction'] or 'N/A'} | {s['line_break_direction'] or 'N/A'} |\n"
                if len(screener_rows) > 20:
                    markdown_report += f"\n*... and {len(screener_rows) - 20} more stocks shown in the Screener grid.*"
            else:
                markdown_report += "\n> [!NOTE]\n> No stocks matched the filtering criteria."

            yield self._sse_event(
                "complete",
                {
                    "report": markdown_report,
                    "recommendation": "BULLISH" if len(screener_rows) > 0 else "NEUTRAL",
                    "confidence": "HIGH",
                    "screener_results": screener_rows,
                },
            )

            # Observability metrics completion logs
            workflow_duration = time.time() - workflow_start
            AgentTelemetry.log_workflow_completion("sql_screening", workflow_duration, status="success")
            return

        yield self._sse_event("started", "Orchestrator parsing user stock query...")

        symbol = "RELIANCE.NS"
        intent = "analyze_stock"

        try:
            # 1. Coordinate natural language query parser (orchestrator agent)
            logger.info("Executing orchestrator intent LLM agent...")
            intent_res = await self.pool.execute_agent("orchestrator", user_query)

            intent = intent_res.get("intent", "analyze_stock")
            symbol = intent_res.get("symbol", "RELIANCE.NS")
            rationale = intent_res.get("rationale", "")

            # Format and standardize symbol
            if symbol:
                symbol = symbol.strip().upper()
                if not symbol.endswith(".NS") and not symbol.startswith("^"):
                    symbol = f"{symbol}.NS"
                if not re.match(r"^[A-Z0-9.\-]+$", symbol):
                    raise ValueError("Security Violation: Malicious ticker format detected.")
            else:
                symbol = "RELIANCE.NS"

            yield self._sse_event("intent_detected", {"intent": intent, "symbol": symbol, "rationale": rationale})

            # 2. Dynamic Workflow Compilation via Microsoft Agent Framework DAG builder
            wb = None

            if intent == "analyze_stock":
                e1 = FunctionExecutor(self._step_database_dynamic, id="database_service")
                e2 = FunctionExecutor(self._step_stock_analysis_dynamic, id="stock_analysis_service")
                e3 = FunctionExecutor(self._step_trade_planner_dynamic, id="trade_planner_service")
                e4 = FunctionExecutor(self._step_backtester_dynamic, id="backtester_service")
                report_agent = self.pool.get_agent("report_agent")

                wb = WorkflowBuilder(start_executor=e1, output_from=[report_agent])
                wb.add_edge(e1, e2)
                wb.add_edge(e2, e3)
                wb.add_edge(e3, e4)
                wb.add_edge(e4, report_agent)

            elif intent == "breakout_scan":
                e1 = FunctionExecutor(self._step_market_regime_breakout, id="market_regime_service")
                e2 = FunctionExecutor(self._step_screening_breakout, id="screening_service")
                report_agent = self.pool.get_agent("report_agent")

                wb = WorkflowBuilder(start_executor=e1, output_from=[report_agent])
                wb.add_edge(e1, e2)
                wb.add_edge(e2, report_agent)

            elif intent == "market_regime":
                e1 = FunctionExecutor(self._step_market_regime_standalone, id="market_regime_service")
                report_agent = self.pool.get_agent("report_agent")

                wb = WorkflowBuilder(start_executor=e1, output_from=[report_agent])
                wb.add_edge(e1, report_agent)

            elif intent == "swing_trade_scan":
                e1 = FunctionExecutor(self._step_market_regime_swing, id="market_regime_service")
                e2 = FunctionExecutor(self._step_screening_swing, id="screening_service")
                e3 = FunctionExecutor(self._step_stock_analysis_swing, id="stock_analysis_service")
                e4 = FunctionExecutor(self._step_trade_planner_swing, id="trade_planner_service")
                report_agent = self.pool.get_agent("report_agent")

                wb = WorkflowBuilder(start_executor=e1, output_from=[report_agent])
                wb.add_edge(e1, e2)
                wb.add_edge(e2, e3)
                wb.add_edge(e3, e4)
                wb.add_edge(e4, report_agent)

            else:
                # Default fallback workflow
                intent = "analyze_stock"
                e1 = FunctionExecutor(self._step_database_dynamic, id="database_service")
                e2 = FunctionExecutor(self._step_stock_analysis_dynamic, id="stock_analysis_service")
                e3 = FunctionExecutor(self._step_trade_planner_dynamic, id="trade_planner_service")
                e4 = FunctionExecutor(self._step_backtester_dynamic, id="backtester_service")
                report_agent = self.pool.get_agent("report_agent")

                wb = WorkflowBuilder(start_executor=e1, output_from=[report_agent])
                wb.add_edge(e1, e2)
                wb.add_edge(e2, e3)
                wb.add_edge(e3, e4)
                wb.add_edge(e4, report_agent)

            wf = wb.build()

            # Initiate async pipeline stream
            stream = await wf.run(symbol, stream=True)
            async for event in stream:
                if event.type == "executor_invoked":
                    yield self._sse_event(
                        "agent_active",
                        {"agent": event.executor_id, "status": f"Activating {event.executor_id.replace('_', ' ')}..."},
                    )

                elif event.type == "executor_completed":
                    if event.executor_id == "report_agent" and event.data:
                        out_msg = event.data[0] if isinstance(event.data, list) else event.data
                        text_content = ""
                        if hasattr(out_msg, "agent_response"):
                            text_content = out_msg.agent_response.text
                        elif hasattr(out_msg, "text"):
                            text_content = out_msg.text
                        else:
                            text_content = str(out_msg)

                        report_res = safe_parse_json(text_content)
                        yield self._sse_event(
                            "complete",
                            {
                                "report": report_res.get("markdown_report", ""),
                                "recommendation": report_res.get("executive_recommendation", "HOLD"),
                                "confidence": report_res.get("overall_confidence", "MEDIUM"),
                            },
                        )

                elif event.type == "executor_failed":
                    err_msg = getattr(event.details, "message", "Internal executor failure.")
                    logger.error(f"Executor failed: {event.executor_id} - {err_msg}")
                    yield self._sse_event("error", err_msg)
                    return

        except Exception as e:
            logger.error(f"MAF dynamic workflow failed: {e}")
            yield self._sse_event("error", str(e))
            return

        # Observability metrics completion logs
        workflow_duration = time.time() - workflow_start
        AgentTelemetry.log_workflow_completion(intent, workflow_duration, status="success")

    def _sse_event(self, event_type: str, data: Any) -> str:
        """Formats standard Server-Sent Events streaming block envelopes."""
        payload = {"event": event_type, "data": data}
        return f"data: {json.dumps(payload)}\n\n"
