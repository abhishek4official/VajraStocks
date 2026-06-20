from collections import defaultdict

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from stocks.api.deps import get_db
from stocks.config import Config as _Config
from stocks.db.models import StrategySignal, SymbolConfluenceLevel, SymbolFundamentals
from stocks.services.quant.confluence_service import ConfluenceService

config = _Config.load()
from stocks.services.screening import ScreeningService
from stocks.services.settings_service import SettingsService

router = APIRouter(prefix="/screeners", tags=["Stock Screening"])


def _structural_trade_setup(
    close: float | None,
    atr_pct: float | None,
    symbol_levels: list,
    risk_per_trade: float = 5000.0,
) -> dict:
    """Calculates trade setup using structural confluence levels.

    Returns stop_loss, target_1/2/3, potential_gain_pct, rr_ratio, position_size_shares.
    T1 is selected by strength_score (highest-confidence resistance above price).
    T2/T3 are the next structural levels above T1.
    """
    empty = {
        "stop_loss": None,
        "target_1": None,
        "target_2": None,
        "target_3": None,
        "potential_gain_pct": None,
        "rr_ratio": None,
        "position_size_shares": None,
    }
    if close is None or close <= 0:
        return empty

    atr_abs = atr_pct / 100.0 * close if (atr_pct is not None and atr_pct > 0) else 0.0

    pos_supports = [lvl for lvl in symbol_levels if lvl.level_type == "SUPPORT"]
    pos_resistances = [lvl for lvl in symbol_levels if lvl.level_type == "RESISTANCE"]

    # Support → stop loss
    pos_supports_sorted = sorted(pos_supports, key=lambda x: float(x.price), reverse=True)
    support_val = float(pos_supports_sorted[0].price) if pos_supports_sorted else None

    # T1: highest-strength resistance meaningfully above price
    best_r1 = ConfluenceService.select_best_resistance(pos_resistances, close, atr_abs)
    target_1 = round(float(best_r1.price), 2) if best_r1 is not None else None

    # T2/T3: next resistances by price above T1
    target_2 = target_3 = None
    if best_r1 is not None:
        above_t1 = sorted(
            [r for r in pos_resistances if float(r.price) > float(best_r1.price)],
            key=lambda x: float(x.price),
        )
        if len(above_t1) >= 1:
            target_2 = round(float(above_t1[0].price), 2)
        if len(above_t1) >= 2:
            target_3 = round(float(above_t1[1].price), 2)

    # Fallback targets when no confluence levels exist
    if target_1 is None:
        target_1 = round(close + 1.5 * atr_abs, 2) if atr_abs > 0 else None
    if target_2 is None and atr_abs > 0 and target_1 is not None:
        target_2 = round(target_1 + 1.5 * atr_abs, 2)

    # Stop loss
    if atr_abs > 0:
        if support_val is not None:
            stop = round(support_val - 1.5 * atr_abs, 2)
            if stop >= close:
                stop = round(close - 2.0 * atr_abs, 2)
        else:
            stop = round(close - 1.5 * atr_abs, 2)
    else:
        stop = None

    potential_gain_pct = round((target_1 - close) / close * 100.0, 2) if target_1 and close > 0 else None

    risk = (close - stop) if stop is not None else 0.0
    reward = (target_1 - close) if target_1 is not None else 0.0
    rr_ratio = round(reward / risk, 2) if risk > 0 else None

    position_size_shares = None
    if risk > 0 and risk_per_trade > 0:
        position_size_shares = int(risk_per_trade / risk)
        if position_size_shares <= 0:
            position_size_shares = None

    return {
        "stop_loss": stop,
        "target_1": target_1,
        "target_2": target_2,
        "target_3": target_3,
        "potential_gain_pct": potential_gain_pct,
        "rr_ratio": rr_ratio,
        "position_size_shares": position_size_shares,
    }


def compute_trade_quality_score(snap, rr_ratio: float | None = None) -> float | None:
    """Trade quality score (0-100) blending the composite signal score with R:R.

    When composite_score is available in the snapshot (post-recalculation),
    it drives 90% of the score; R:R adjusts the remaining 10%.
    Falls back to a heuristic when composite_score is absent (legacy snapshots).
    """
    if snap is None:
        return None

    composite = getattr(snap, "composite_score", None)

    if composite is not None:
        # Primary path: use the pre-computed composite score
        rr_component = 50.0
        if rr_ratio is not None:
            rr_component = min(100.0, max(0.0, rr_ratio / 3.0 * 100.0))
        return round(0.90 * float(composite) + 0.10 * rr_component, 1)

    # Legacy fallback (snapshots not yet recalculated)
    trend = 0
    if snap.sma_200_cross_direction == "ABOVE":
        trend += 40
    if snap.regime_bias == "VERY_BULLISH":
        trend += 50
    elif snap.regime_bias == "BULLISH":
        trend += 35
    elif snap.regime_bias == "NEUTRAL":
        trend += 15
    if snap.weekly_trend == "UP":
        trend += 15
    elif snap.weekly_trend is None:
        trend += 8
    if snap.mtf_confirmed:
        trend = min(trend + 10, 100)
    if getattr(snap, "trend_strength_class", None) == "STRONG":
        trend = min(trend + 10, 100)
    if getattr(snap, "supertrend_dir", None) == "UP":
        trend = min(trend + 5, 100)
    score = min(trend, 100) * 0.30

    rs = 50.0
    if snap.rs_score_1m is not None:
        rs = min(100.0, max(0.0, float(snap.rs_score_1m) * 50.0))
    score += rs * 0.20

    vol = {"HIGH": 100, "MEDIUM": 60, "LOW": 20}.get(snap.vol_class, 50)
    if getattr(snap, "obv_trend", None) == "UP":
        vol = min(vol + 15, 100)
    score += vol * 0.15

    mom = 0
    if snap.rsi_14 is not None:
        rsi = float(snap.rsi_14)
        if rsi >= 70: mom = 95
        elif rsi >= 60: mom = 82
        elif rsi >= 50: mom = 65
        elif rsi >= 40: mom = 40
        elif rsi >= 30: mom = 20
    if snap.macd_trend == "BULLISH": mom = min(mom + 12, 100)
    if snap.ret_1w is not None and float(snap.ret_1w) > 0: mom = min(mom + 8, 100)
    if snap.ha_direction == "UP": mom = min(mom + 5, 100)
    score += mom * 0.25

    rr = 50.0
    if rr_ratio is not None:
        rr = min(100.0, max(0.0, rr_ratio / 3.0 * 100.0))
    score += rr * 0.10
    return round(score, 1)


# Pydantic Request & Response Schemas
class ScreeningParams(BaseModel):
    min_rsi: float | None = None
    max_rsi: float | None = None
    sma_20_cross: str | None = None  # 'ABOVE', 'BELOW'
    sma_50_cross: str | None = None  # 'ABOVE', 'BELOW'
    sma_200_cross: str | None = None  # 'ABOVE', 'BELOW'
    macd_trend: str | None = None  # 'BULLISH', 'BEARISH'
    ha_dir: str | None = None  # 'UP', 'DOWN'
    renko_dir: str | None = None  # 'UP', 'DOWN'
    lb_dir: str | None = None  # 'UP', 'DOWN'
    min_avg_traded_value: float | None = None
    volume_breakout: str | None = None  # 'ANY', '1.5X', '2.0X', '3.0X'
    only_nr7: bool = False
    only_inside_bar: bool = False
    only_gap_up: bool = False
    only_gap_down: bool = False
    min_rs_1m: float | None = None
    # CMF filters
    min_cmf: float | None = None
    max_cmf: float | None = None
    cmf_rising: bool | None = None
    cmf_crossed_zero: bool | None = None
    # StochRSI filters
    max_stochrsi_k: float | None = None
    min_stochrsi_k: float | None = None
    stochrsi_bullish_xover_max_days: int | None = None
    # Crossover recency filters
    ema_ribbon_bull_max_days:  int | None = None   # days_since_ema9_ema20_bull
    golden_cross_max_days:     int | None = None   # days_since_sma20_sma50_bull
    macd_bull_xover_max_days:  int | None = None   # days_since_macd_bull
    cmf_bull_xover_max_days:   int | None = None   # days_since_cmf_bull
    limit: int = 2500


class ScreenerRowResponse(BaseModel):
    symbol_id: int
    symbol: str
    company_name: str
    last_trading_date: str
    close_price: float
    price_pct_change: float | None = None
    volume: int
    ha_close: float
    ha_direction: str
    rsi_14: float | None = None
    sma_20_cross_direction: str | None = None
    sma_50_cross_direction: str | None = None
    sma_200_cross_direction: str | None = None
    macd_trend: str | None = None
    renko_direction: str | None = None
    line_break_direction: str | None = None
    is_nr7: bool | None = None
    is_inside_bar: bool | None = None
    is_gap_up: bool | None = None
    is_gap_down: bool | None = None
    rs_score_1m: float | None = None
    regime_bias: str | None = None
    weekly_trend: str | None = None
    avg_traded_value: float | None = None
    volume_breakout_ratio: float | None = None
    ret_1w: float | None = None
    ret_2w: float | None = None
    ret_3w: float | None = None
    ret_4w: float | None = None
    atr_pct: float | None = None
    stop_loss: float | None = None
    target_1: float | None = None
    target_2: float | None = None
    target_3: float | None = None
    potential_gain_pct: float | None = None
    rr_ratio: float | None = None
    position_size_shares: int | None = None
    trade_quality_score: float | None = None
    adx_14: float | None = None
    trend_strength_class: str | None = None
    obv_trend: str | None = None
    supertrend_dir: str | None = None
    stoch_state: str | None = None
    composite_score: float | None = None
    trend_score_val: float | None = None
    volume_score_val: float | None = None
    rs_score_val: float | None = None
    momentum_score_val: float | None = None
    cmf_score_val: float | None = None
    breakout_score_val: float | None = None
    cmf_20: float | None = None
    cmf_20_prev: float | None = None
    cmf_crossed_above_zero: bool | None = None
    stochrsi_k: float | None = None
    stochrsi_d: float | None = None
    stochrsi_zone: str | None = None
    stochrsi_bullish_xover_days_ago: int | None = None
    stochrsi_bearish_xover_days_ago: int | None = None
    ml2_p_tp: float | None = None
    ml2_p_sl: float | None = None
    ml2_ev_score: float | None = None
    ml2_rank: int | None = None
    ml2_signal: str | None = None
    strategy_signals: dict = {}   # {strategy_id: {"signal": str, "score": float|None}}
    # Crossover recency
    days_since_price_sma20_bull: int | None = None
    days_since_price_sma50_bull: int | None = None
    days_since_price_ema20_bull: int | None = None
    days_since_ema9_ema20_bull:  int | None = None
    days_since_ema9_ema20_bear:  int | None = None
    days_since_sma20_sma50_bull: int | None = None
    days_since_macd_bull:        int | None = None
    days_since_macd_bear:        int | None = None
    days_since_cmf_bull:         int | None = None
    days_since_cmf_bear:         int | None = None
    ema9_ema20_spread:           float | None = None
    macd_histogram_slope:        float | None = None
    macd_above_zero:             bool | None = None
    cmf_slope_5d:                float | None = None
    # Fundamentals
    market_cap:       float | None = None
    enterprise_value: float | None = None
    pe_ratio:         float | None = None
    forward_pe:       float | None = None
    pb_ratio:         float | None = None
    ev_ebitda:        float | None = None
    price_to_sales:   float | None = None
    revenue_ttm:      float | None = None
    net_profit_ttm:   float | None = None
    ebitda:           float | None = None
    gross_margin:     float | None = None
    profit_margin:    float | None = None
    operating_margin: float | None = None
    eps_ttm:          float | None = None
    book_value:       float | None = None
    dividend_yield:   float | None = None
    roe:              float | None = None
    roa:              float | None = None
    debt_to_equity:   float | None = None
    current_ratio:    float | None = None
    free_cashflow:    float | None = None
    sector:           str | None = None
    industry:         str | None = None

    class Config:
        from_attributes = True


def _build_confl_map(db: Session, symbol_ids: list[int]) -> dict:
    """Batch-loads confluence levels for the given symbol IDs, returns dict keyed by symbol_id."""
    confl_by_symbol_id: dict = defaultdict(list)
    if not symbol_ids:
        return confl_by_symbol_id
    chunk_size = 1000
    for i in range(0, len(symbol_ids), chunk_size):
        chunk = symbol_ids[i : i + chunk_size]
        for lvl in db.scalars(
            select(SymbolConfluenceLevel).where(SymbolConfluenceLevel.symbol_id.in_(chunk))
        ).all():
            confl_by_symbol_id[lvl.symbol_id].append(lvl)
    return confl_by_symbol_id


def _build_strategy_signal_map(db: Session, symbol_ids: list[int]) -> dict:
    """Batch-loads materialized strategy signals for the given symbol IDs.

    Returns {symbol_id: {strategy_id: {"signal": str, "score": float|None}}} so the
    screener can show each stock's per-strategy signal alongside its technicals.
    """
    out: dict = defaultdict(dict)
    if not symbol_ids:
        return out
    chunk_size = 1000
    for i in range(0, len(symbol_ids), chunk_size):
        chunk = symbol_ids[i : i + chunk_size]
        for s in db.scalars(
            select(StrategySignal).where(StrategySignal.symbol_id.in_(chunk))
        ).all():
            out[s.symbol_id][s.strategy_id] = {"signal": s.signal, "score": s.score}
    return out


def _build_fund_map(db: Session, symbol_ids: list[int]) -> dict:
    """Batch-loads SymbolFundamentals keyed by symbol_id."""
    fund_by_id: dict = {}
    if not symbol_ids:
        return fund_by_id
    chunk_size = 1000
    for i in range(0, len(symbol_ids), chunk_size):
        chunk = symbol_ids[i : i + chunk_size]
        for f in db.scalars(
            select(SymbolFundamentals).where(SymbolFundamentals.symbol_id.in_(chunk))
        ).all():
            fund_by_id[f.symbol_id] = f
    return fund_by_id


def _build_row(r, confl_by_symbol_id: dict, risk_per_trade: float, strat_by_symbol_id: dict | None = None, fund_by_symbol_id: dict | None = None) -> dict:
    """Builds a single screener response row dict from a ScreeningSnapshot."""
    close = float(r.close_price)
    setup = _structural_trade_setup(close, r.atr_pct, confl_by_symbol_id.get(r.symbol_id, []), risk_per_trade)
    tqs = compute_trade_quality_score(r, setup.get("rr_ratio"))
    fund = (fund_by_symbol_id or {}).get(r.symbol_id)
    return {
        "symbol_id": r.symbol_id,
        "symbol": r.symbol,
        "company_name": r.company_name,
        "last_trading_date": r.last_trading_date.strftime("%Y-%m-%d"),
        "close_price": close,
        "price_pct_change": r.price_pct_change,
        "volume": int(r.volume),
        "ha_close": float(r.ha_close),
        "ha_direction": r.ha_direction,
        "rsi_14": r.rsi_14,
        "sma_20_cross_direction": r.sma_20_cross_direction,
        "sma_50_cross_direction": r.sma_50_cross_direction,
        "sma_200_cross_direction": r.sma_200_cross_direction,
        "macd_trend": r.macd_trend,
        "renko_direction": r.renko_direction,
        "line_break_direction": r.line_break_direction,
        "is_nr7": r.is_nr7,
        "is_inside_bar": r.is_inside_bar,
        "is_gap_up": r.is_gap_up,
        "is_gap_down": r.is_gap_down,
        "rs_score_1m": r.rs_score_1m,
        "regime_bias": getattr(r, "regime_bias", None),
        "weekly_trend": getattr(r, "weekly_trend", None),
        "avg_traded_value": getattr(r, "avg_traded_value", None),
        "volume_breakout_ratio": getattr(r, "volume_breakout_ratio", None),
        "ret_1w": r.ret_1w,
        "ret_2w": r.ret_2w,
        "ret_3w": r.ret_3w,
        "ret_4w": r.ret_4w,
        "atr_pct": r.atr_pct,
        **setup,
        "trade_quality_score": tqs,
        "adx_14": getattr(r, "adx_14", None),
        "trend_strength_class": getattr(r, "trend_strength_class", None),
        "obv_trend": getattr(r, "obv_trend", None),
        "supertrend_dir": getattr(r, "supertrend_dir", None),
        "stoch_state": getattr(r, "stoch_state", None),
        "composite_score": getattr(r, "composite_score", None),
        "trend_score_val": getattr(r, "trend_score_val", None),
        "volume_score_val": getattr(r, "volume_score_val", None),
        "rs_score_val": getattr(r, "rs_score_val", None),
        "momentum_score_val": getattr(r, "momentum_score_val", None),
        "cmf_score_val": getattr(r, "cmf_score_val", None),
        "breakout_score_val": getattr(r, "breakout_score_val", None),
        "cmf_20": getattr(r, "cmf_20", None),
        "cmf_20_prev": getattr(r, "cmf_20_prev", None),
        "cmf_crossed_above_zero": getattr(r, "cmf_crossed_above_zero", None),
        "stochrsi_k": getattr(r, "stochrsi_k", None),
        "stochrsi_d": getattr(r, "stochrsi_d", None),
        "stochrsi_zone": getattr(r, "stochrsi_zone", None),
        "stochrsi_bullish_xover_days_ago": getattr(r, "stochrsi_bullish_xover_days_ago", None),
        "stochrsi_bearish_xover_days_ago": getattr(r, "stochrsi_bearish_xover_days_ago", None),
        "ml2_p_tp":    getattr(r, "ml2_p_tp",    None),
        "ml2_p_sl":    getattr(r, "ml2_p_sl",    None),
        "ml2_ev_score":getattr(r, "ml2_ev_score", None),
        "ml2_rank":    getattr(r, "ml2_rank",     None),
        "ml2_signal":  getattr(r, "ml2_signal",   None),
        "strategy_signals": (strat_by_symbol_id or {}).get(r.symbol_id, {}),
        "market_cap":       getattr(fund, "market_cap",       None),
        "enterprise_value": getattr(fund, "enterprise_value", None),
        "pe_ratio":         getattr(fund, "pe_ratio",         None),
        "forward_pe":       getattr(fund, "forward_pe",       None),
        "pb_ratio":         getattr(fund, "pb_ratio",         None),
        "ev_ebitda":        getattr(fund, "ev_ebitda",        None),
        "price_to_sales":   getattr(fund, "price_to_sales",   None),
        "revenue_ttm":      getattr(fund, "revenue_ttm",      None),
        "net_profit_ttm":   getattr(fund, "net_profit_ttm",   None),
        "ebitda":           getattr(fund, "ebitda",           None),
        "gross_margin":     getattr(fund, "gross_margin",     None),
        "profit_margin":    getattr(fund, "profit_margin",    None),
        "operating_margin": getattr(fund, "operating_margin", None),
        "eps_ttm":          getattr(fund, "eps_ttm",          None),
        "book_value":       getattr(fund, "book_value",       None),
        "dividend_yield":   getattr(fund, "dividend_yield",   None),
        "roe":              getattr(fund, "roe",              None),
        "roa":              getattr(fund, "roa",              None),
        "debt_to_equity":   getattr(fund, "debt_to_equity",   None),
        "current_ratio":    getattr(fund, "current_ratio",    None),
        "free_cashflow":    getattr(fund, "free_cashflow",    None),
        "sector":           getattr(fund, "sector",           None),
        "industry":         getattr(fund, "industry",         None),
        "days_since_price_sma20_bull": getattr(r, "days_since_price_sma20_bull", None),
        "days_since_price_sma50_bull": getattr(r, "days_since_price_sma50_bull", None),
        "days_since_price_ema20_bull": getattr(r, "days_since_price_ema20_bull", None),
        "days_since_ema9_ema20_bull":  getattr(r, "days_since_ema9_ema20_bull", None),
        "days_since_ema9_ema20_bear":  getattr(r, "days_since_ema9_ema20_bear", None),
        "days_since_sma20_sma50_bull": getattr(r, "days_since_sma20_sma50_bull", None),
        "days_since_macd_bull":        getattr(r, "days_since_macd_bull", None),
        "days_since_macd_bear":        getattr(r, "days_since_macd_bear", None),
        "days_since_cmf_bull":         getattr(r, "days_since_cmf_bull", None),
        "days_since_cmf_bear":         getattr(r, "days_since_cmf_bear", None),
        "ema9_ema20_spread":           getattr(r, "ema9_ema20_spread", None),
        "macd_histogram_slope":        getattr(r, "macd_histogram_slope", None),
        "macd_above_zero":             getattr(r, "macd_above_zero", None),
        "cmf_slope_5d":                getattr(r, "cmf_slope_5d", None),
    }


@router.get("", response_model=list[ScreenerRowResponse])
def get_screening_results_get(
    min_rsi: float | None = None,
    max_rsi: float | None = None,
    sma_20_cross: str | None = None,
    sma_50_cross: str | None = None,
    sma_200_cross: str | None = None,
    macd_trend: str | None = None,
    ha_dir: str | None = None,
    renko_dir: str | None = None,
    lb_dir: str | None = None,
    min_avg_traded_value: float | None = None,
    volume_breakout: str | None = None,
    only_nr7: bool = False,
    only_inside_bar: bool = False,
    only_gap_up: bool = False,
    only_gap_down: bool = False,
    min_rs_1m: float | None = None,
    min_cmf: float | None = None,
    max_cmf: float | None = None,
    cmf_rising: bool | None = None,
    cmf_crossed_zero: bool | None = None,
    max_stochrsi_k: float | None = None,
    min_stochrsi_k: float | None = None,
    stochrsi_bullish_xover_max_days: int | None = None,
    ema_ribbon_bull_max_days: int | None = None,
    golden_cross_max_days: int | None = None,
    macd_bull_xover_max_days: int | None = None,
    cmf_bull_xover_max_days: int | None = None,
    limit: int = 2500,
    db: Session = Depends(get_db),
):
    """Executes a high-speed screening sweep using query parameters directly against the narrow snapshot layer."""
    screening_service = ScreeningService(config, db)
    results = screening_service.query_screener(
        min_rsi=min_rsi,
        max_rsi=max_rsi,
        sma_20_cross=sma_20_cross,
        sma_50_cross=sma_50_cross,
        sma_200_cross=sma_200_cross,
        macd_trend=macd_trend,
        ha_dir=ha_dir,
        renko_dir=renko_dir,
        lb_dir=lb_dir,
        min_avg_traded_value=min_avg_traded_value,
        volume_breakout=volume_breakout,
        only_nr7=only_nr7,
        only_inside_bar=only_inside_bar,
        only_gap_up=only_gap_up,
        only_gap_down=only_gap_down,
        min_rs_1m=min_rs_1m,
        min_cmf=min_cmf,
        max_cmf=max_cmf,
        cmf_rising=cmf_rising,
        cmf_crossed_zero=cmf_crossed_zero,
        max_stochrsi_k=max_stochrsi_k,
        min_stochrsi_k=min_stochrsi_k,
        stochrsi_bullish_xover_max_days=stochrsi_bullish_xover_max_days,
        ema_ribbon_bull_max_days=ema_ribbon_bull_max_days,
        golden_cross_max_days=golden_cross_max_days,
        macd_bull_xover_max_days=macd_bull_xover_max_days,
        cmf_bull_xover_max_days=cmf_bull_xover_max_days,
        limit=limit,
    )

    risk_per_trade = SettingsService(db).get_float("PORTFOLIO", "default_risk_amount", 5000.0)
    ids = [r.symbol_id for r in results]
    confl_by_symbol_id = _build_confl_map(db, ids)
    strat_by_symbol_id = _build_strategy_signal_map(db, ids)
    fund_by_symbol_id = _build_fund_map(db, ids)
    return [_build_row(r, confl_by_symbol_id, risk_per_trade, strat_by_symbol_id, fund_by_symbol_id) for r in results]


@router.post("/run", response_model=list[ScreenerRowResponse])
def get_screening_results_post(params: ScreeningParams, db: Session = Depends(get_db)):
    """Executes a high-speed screening sweep using a POST body request directly against the snapshot layer."""
    screening_service = ScreeningService(config, db)
    results = screening_service.query_screener(
        min_rsi=params.min_rsi,
        max_rsi=params.max_rsi,
        sma_20_cross=params.sma_20_cross,
        sma_50_cross=params.sma_50_cross,
        sma_200_cross=params.sma_200_cross,
        macd_trend=params.macd_trend,
        ha_dir=params.ha_dir,
        renko_dir=params.renko_dir,
        lb_dir=params.lb_dir,
        min_avg_traded_value=params.min_avg_traded_value,
        volume_breakout=params.volume_breakout,
        only_nr7=params.only_nr7,
        only_inside_bar=params.only_inside_bar,
        only_gap_up=params.only_gap_up,
        only_gap_down=params.only_gap_down,
        min_rs_1m=params.min_rs_1m,
        min_cmf=params.min_cmf,
        max_cmf=params.max_cmf,
        cmf_rising=params.cmf_rising,
        cmf_crossed_zero=params.cmf_crossed_zero,
        max_stochrsi_k=params.max_stochrsi_k,
        min_stochrsi_k=params.min_stochrsi_k,
        stochrsi_bullish_xover_max_days=params.stochrsi_bullish_xover_max_days,
        ema_ribbon_bull_max_days=params.ema_ribbon_bull_max_days,
        golden_cross_max_days=params.golden_cross_max_days,
        macd_bull_xover_max_days=params.macd_bull_xover_max_days,
        cmf_bull_xover_max_days=params.cmf_bull_xover_max_days,
        limit=params.limit,
    )

    risk_per_trade = SettingsService(db).get_float("PORTFOLIO", "default_risk_amount", 5000.0)
    ids = [r.symbol_id for r in results]
    confl_by_symbol_id = _build_confl_map(db, ids)
    strat_by_symbol_id = _build_strategy_signal_map(db, ids)
    fund_by_symbol_id = _build_fund_map(db, ids)
    return [_build_row(r, confl_by_symbol_id, risk_per_trade, strat_by_symbol_id, fund_by_symbol_id) for r in results]
