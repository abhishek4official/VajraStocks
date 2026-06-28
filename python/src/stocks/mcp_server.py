# python/src/stocks/mcp_server.py
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional
from mcp.server.fastmcp import FastMCP
from sqlalchemy import select
from loguru import logger

from stocks.config import Config
from stocks.db.connection import DatabaseManager
from stocks.db.models import (
    Symbol,
    SymbolTrendline,
    DailyIndicator,
    DailyPrice,
    ScreeningSnapshot,
    SymbolConfluenceLevel,
)

# 1. Initialize FastMCP Server
mcp = FastMCP("VajraStocks")

def _get_user_appdata_dir() -> Path | None:
    import sys
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", "")
        return Path(appdata) / "VajraStocks" if appdata else None
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "VajraStocks"
    xdg = os.environ.get("XDG_DATA_HOME", "")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "VajraStocks"

def _resolve_config_yaml() -> Path:
    env = os.environ.get("VAJRA_CONFIG_YAML")
    if env:
        return Path(env)
    user_dir = _get_user_appdata_dir()
    if user_dir:
        user_cfg = user_dir / "config.yaml"
        if user_cfg.exists():
            return user_cfg
    config_path = Path("config/config.yaml")
    if not config_path.exists() and Path("../config/config.yaml").exists():
        config_path = Path("../config/config.yaml")
    return config_path

# Helper to manage sessions
def get_session():
    config_path = _resolve_config_yaml()
    config = Config.load(config_path)
    db_manager = DatabaseManager.from_config(config)
    db_manager.initialize()
    return db_manager.get_session()

def normalize_symbol(symbol: str) -> str:
    sym = symbol.strip().upper()
    if not sym.endswith(".NS") and not sym.startswith("^"):
        return f"{sym}.NS"
    return sym

# 2. Expose Tools

@mcp.tool()
def get_stock_trendlines(symbol: str) -> str:
    """Retrieves active, unbroken support and resistance trendlines for a stock symbol from local DB.
    
    Args:
        symbol: The stock symbol (e.g. RELIANCE or VENUSPIPES).
    """
    clean_sym = normalize_symbol(symbol)
    session = get_session()
    try:
        sym_obj = session.scalar(select(Symbol).filter_by(symbol=clean_sym))
        if not sym_obj:
            return f"Error: Symbol '{clean_sym}' not found in database."

        lines = session.scalars(
            select(SymbolTrendline)
            .filter_by(symbol_id=sym_obj.id, is_broken=False)
            .order_by(SymbolTrendline.score.desc())
        ).all()

        if not lines:
            return f"No active (unbroken) trendlines found in database for '{clean_sym}'."

        output = f"## Active Trendlines for {clean_sym}\n\n"
        output += "| Type | Touch Count | Score | Daily Slope % | Anchor 1 (Date / Price) | Anchor 2 (Date / Price) |\n"
        output += "| :--- | :---: | :---: | :---: | :--- | :--- |\n"
        for line in lines:
            output += (
                f"| {line.trendline_type} | {line.touch_count} | {line.score:.1f} | {line.slope_pct_per_day:+.3f}% "
                f"| {line.anchor1_date} (₹{line.anchor1_price:.2f}) "
                f"| {line.anchor2_date} (₹{line.anchor2_price:.2f}) |\n"
            )
        return output
    except Exception as e:
        logger.error(f"MCP get_stock_trendlines failed: {e}")
        return f"Error executing trendlines search: {e}"
    finally:
        session.close()

@mcp.tool()
def get_technical_indicators(symbol: str, limit: int = 5) -> str:
    """Retrieves recent technical indicators (RSI, CMF, MACD, SMAs) and EOD closing prices for a stock symbol.
    
    Args:
        symbol: The stock symbol (e.g. TCS or AIAENG).
        limit: Number of recent trading days to return (default 5).
    """
    clean_sym = normalize_symbol(symbol)
    session = get_session()
    try:
        sym_obj = session.scalar(select(Symbol).filter_by(symbol=clean_sym))
        if not sym_obj:
            return f"Error: Symbol '{clean_sym}' not found in database."

        # Fetch indicators joined with price close to provide full context
        stmt = (
            select(DailyIndicator, DailyPrice.close)
            .join(
                DailyPrice,
                (DailyPrice.symbol_id == DailyIndicator.symbol_id)
                & (DailyPrice.trading_date == DailyIndicator.trading_date),
            )
            .where(DailyIndicator.symbol_id == sym_obj.id)
            .order_by(DailyIndicator.trading_date.desc())
            .limit(limit)
        )
        
        results = session.execute(stmt).all()
        if not results:
            return f"No indicator history found in database for '{clean_sym}'."

        output = f"## Recent Indicator History for {clean_sym}\n\n"
        output += "| Date | Close | RSI-14 | CMF-20 | MACD Hist | SMA-20 | SMA-50 | SMA-200 | Supertrend |\n"
        output += "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |\n"
        
        for ind, close in results:
            rsi_val = f"{ind.rsi_14:.1f}" if ind.rsi_14 is not None else "N/A"
            cmf_val = f"{ind.cmf_20:+.3f}" if ind.cmf_20 is not None else "N/A"
            macd_val = f"{ind.macd_histogram:+.2f}" if ind.macd_histogram is not None else "N/A"
            sma20 = f"₹{ind.sma_20:.2f}" if ind.sma_20 is not None else "N/A"
            sma50 = f"₹{ind.sma_50:.2f}" if ind.sma_50 is not None else "N/A"
            sma200 = f"₹{ind.sma_200:.2f}" if ind.sma_200 is not None else "N/A"
            st_dir = f"{ind.supertrend_dir or 'N/A'}"
            
            output += (
                f"| {ind.trading_date} | ₹{close:.2f} | {rsi_val} | {cmf_val} | {macd_val} | "
                f"{sma20} | {sma50} | {sma200} | {st_dir} |\n"
            )
        return output
    except Exception as e:
        logger.error(f"MCP get_technical_indicators failed: {e}")
        return f"Error executing indicators query: {e}"
    finally:
        session.close()

@mcp.tool()
def screen_stocks_snapshot(
    min_tqs: Optional[float] = None,
    weinstein_stage: Optional[int] = None,
    min_volume_ratio: Optional[float] = None,
    limit: int = 15,
) -> str:
    """Queries pre-compiled screening snapshots to find stocks matching technical filters.
    
    Args:
        min_tqs: Minimum Trend Quality Score (0–100). Higher = cleaner trend.
        weinstein_stage: Weinstein Stage (1=Basing, 2=Markup, 3=Topping, 4=Decline).
        min_volume_ratio: Minimum Volume Breakout Ratio (volume / 20-day average).
        limit: Maximum number of rows to return (default 15).
    """
    session = get_session()
    try:
        query = select(ScreeningSnapshot).where(~ScreeningSnapshot.symbol.like("^%"))
        
        if min_tqs is not None:
            query = query.where(ScreeningSnapshot.tqs >= min_tqs)
        if weinstein_stage is not None:
            query = query.where(ScreeningSnapshot.weinstein_stage == weinstein_stage)
        if min_volume_ratio is not None:
            query = query.where(ScreeningSnapshot.volume_breakout_ratio >= min_volume_ratio)
            
        query = query.order_by(ScreeningSnapshot.composite_score.desc()).limit(limit)
        results = session.scalars(query).all()
        
        if not results:
            return "No symbols matched the specified screening criteria in the database."

        output = f"## Screened Stocks Snapshot (Matches: {len(results)})\n\n"
        output += "| Symbol | Company | Close | Bias Score | TQS | Weinstein Stage | Vol Breakout | CMF |\n"
        output += "| :--- | :--- | ---: | ---: | ---: | :---: | ---: | ---: |\n"
        
        for row in results:
            close = float(row.close_price)
            comp = row.composite_score if row.composite_score is not None else 0.0
            tqs_val = f"{row.tqs:.0f}" if row.tqs is not None else "N/A"
            stage = row.weinstein_stage if row.weinstein_stage is not None else "—"
            vol_brk = f"{row.volume_breakout_ratio:.2f}x" if row.volume_breakout_ratio is not None else "N/A"
            cmf = f"{row.cmf_20:+.3f}" if row.cmf_20 is not None else "N/A"
            
            output += (
                f"| **{row.symbol.replace('.NS', '')}** | {row.company_name} | ₹{close:.2f} | "
                f"{comp:.1f} | {tqs_val} | {stage} | {vol_brk} | {cmf} |\n"
            )
        return output
    except Exception as e:
        logger.error(f"MCP screen_stocks_snapshot failed: {e}")
        return f"Error executing database screen: {e}"
    finally:
        session.close()

@mcp.tool()
def calculate_trade_plan(symbol: str, risk_budget: float = 5000.0) -> str:
    """Generates an ATR-based trade plan with Entry, Stop Loss, Target levels and position sizes.
    
    Args:
        symbol: The stock symbol (e.g. RADICO or SCHNEIDER).
        risk_budget: Total amount of capital you are willing to risk on this trade in INR (default ₹5,000).
    """
    clean_sym = normalize_symbol(symbol)
    session = get_session()
    try:
        sym_obj = session.scalar(select(Symbol).filter_by(symbol=clean_sym))
        if not sym_obj:
            return f"Error: Symbol '{clean_sym}' not found in database."

        latest_ind = session.scalar(
            select(DailyIndicator)
            .filter_by(symbol_id=sym_obj.id)
            .order_by(DailyIndicator.trading_date.desc())
            .limit(1)
        )
        latest_price_obj = session.scalar(
            select(DailyPrice)
            .filter_by(symbol_id=sym_obj.id)
            .order_by(DailyPrice.trading_date.desc())
            .limit(1)
        )

        if not latest_price_obj:
            return f"Error: No price history available to calculate trade plan for '{clean_sym}'."

        close = float(latest_price_obj.close)
        atr = float(latest_ind.atr_14) if latest_ind and latest_ind.atr_14 else close * 0.02
        sma_200 = float(latest_ind.sma_200) if latest_ind and latest_ind.sma_200 else close * 0.95

        # Fetch or calculate confluence support/resistance
        from stocks.services.quant.confluence_service import ConfluenceService
        from stocks.services.quant.planner import TradePlannerService

        levels = session.scalars(select(SymbolConfluenceLevel).filter_by(symbol_id=sym_obj.id)).all()
        if not levels:
            levels = ConfluenceService(session).calculate_and_save_levels(sym_obj.id)

        supports = sorted(
            [lv for lv in levels if lv.level_type == "SUPPORT"], key=lambda x: float(x.price), reverse=True
        )
        resistances = [lv for lv in levels if lv.level_type == "RESISTANCE"]

        support = float(supports[0].price) if supports else sma_200
        best_r = ConfluenceService.select_best_resistance(resistances, close, atr)
        resistance = float(best_r.price) if best_r else close * 1.15

        # Call deterministic planner
        planner = TradePlannerService(risk_per_trade_inr=risk_budget)
        plan = planner.calculate_trade_plan(
            symbol=clean_sym, latest_price=close, atr_14=atr, support=support, resistance=resistance
        )
        exec_plan = plan.get("execution", {})

        output = f"## Swing Trade Setup: {clean_sym}\n\n"
        output += f"**Current Price:** ₹{close:.2f} | **Daily ATR (14):** ₹{atr:.2f}\n"
        output += f"**Identified Support Pivot:** ₹{support:.2f} | **Target Resistance Pivot:** ₹{resistance:.2f}\n\n"
        
        output += "### ⚡ Execution Trade Plan\n"
        output += f"- **Action Verdict:** **{exec_plan.get('action', 'HOLD')}**\n"
        output += f"- **Suggested Entry Zone:** ₹{exec_plan.get('entry_zone', 'N/A')}\n"
        output += f"- **Stop Loss Level:** ₹{exec_plan.get('stop_loss', 'N/A')} *(1.5x ATR below support pivot)*\n"
        
        targets = exec_plan.get("targets", [])
        for i, target in enumerate(targets, 1):
            output += f"- **Target {i}:** ₹{target:.2f}\n"
            
        output += f"- **Risk-to-Reward (R:R) Ratio:** {exec_plan.get('risk_reward_ratio', 'N/A')} : 1\n"
        output += f"- **Suggested Position Sizing:** **{exec_plan.get('position_size_shares', 1)} shares** *(with risk budget of ₹{risk_budget:,.2f})*\n\n"
        
        output += "### 📈 Execution Tactics\n"
        output += f"{plan.get('tactics', 'N/A')}\n"
        return output
    except Exception as e:
        logger.error(f"MCP calculate_trade_plan failed: {e}")
        return f"Error compiling trade plan: {e}"
    finally:
        session.close()

if __name__ == "__main__":
    mcp.run()
