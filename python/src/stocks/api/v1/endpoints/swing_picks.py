from __future__ import annotations

import datetime
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from stocks.api.deps import get_db
from stocks.db.models import (
    DailyIndicator,
    ScreeningSnapshot,
    SwingPickNote,
    SymbolConfluenceLevel,
    SymbolTrendline,
)
from stocks.services.quant.confluence_service import ConfluenceService
from stocks.services.settings_service import SettingsService

router = APIRouter(prefix="/swing-picks", tags=["Swing Picks"])


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _project_trendline(
    d1: datetime.date, p1: float,
    d2: datetime.date, p2: float,
    target: datetime.date,
) -> float:
    epoch = datetime.date(1970, 1, 1)
    o1, o2, ot = (d1 - epoch).days, (d2 - epoch).days, (target - epoch).days
    if o2 == o1:
        return float(p1)
    return float(p1) + (float(p2) - float(p1)) * (ot - o1) / (o2 - o1)


def _compute_trade_plan(
    close: float,
    atr_pct: float | None,
    symbol_levels: list,
    risk_per_trade: float = 5000.0,
    stop_atr_mult: float = 1.5,
    entry_atr_low: float = 0.5,
    entry_atr_high: float = 0.25,
    min_res_strength: int = 30,
    total_capital: float = 0.0,
    max_weight_pct: float = 25.0,
) -> dict:
    empty: dict = {
        "stop_loss": None, "target_1": None, "target_2": None,
        "rr_ratio": None, "position_size_shares": None,
        "entry_zone_low": None, "entry_zone_high": None,
        "intermediate_resistance": False, "intermediate_resistance_price": None,
        "notional_capped": False,
    }
    if not close or close <= 0:
        return empty

    atr = (atr_pct / 100.0 * close) if (atr_pct and atr_pct > 0) else close * 0.02

    supports = sorted(
        [l for l in symbol_levels if l.level_type == "SUPPORT"],
        key=lambda x: float(x.price), reverse=True,
    )
    resistances = [l for l in symbol_levels if l.level_type == "RESISTANCE"]

    support_val = float(supports[0].price) if supports else None
    best_r1 = ConfluenceService.select_best_resistance(
        resistances, close, atr, min_strength=min_res_strength
    )
    target_1 = round(float(best_r1.price), 2) if best_r1 else None

    # Detect intermediate resistance between CMP and T1
    intermediate_resistance = False
    intermediate_resistance_price = None
    if target_1 is not None and best_r1 is not None:
        min_gap = max(atr * 0.5, close * 0.005)
        between = [
            r for r in resistances
            if float(r.price) > close + min_gap
            and float(r.price) < float(best_r1.price) - min_gap
        ]
        if between:
            intermediate_resistance = True
            intermediate_resistance_price = round(min(float(r.price) for r in between), 2)

    target_2 = None
    if best_r1:
        above_t1 = sorted(
            [r for r in resistances if float(r.price) > float(best_r1.price)],
            key=lambda x: float(x.price),
        )
        if above_t1:
            target_2 = round(float(above_t1[0].price), 2)

    if target_1 is None:
        target_1 = round(close + stop_atr_mult * atr, 2)
    if target_2 is None:
        target_2 = round(target_1 + stop_atr_mult * atr, 2)

    if support_val is not None:
        stop = round(support_val - stop_atr_mult * atr, 2)
        if stop >= close:
            stop = round(close - (stop_atr_mult + 0.5) * atr, 2)
    else:
        stop = round(close - stop_atr_mult * atr, 2)

    risk = close - stop
    reward = target_1 - close
    rr = round(reward / risk, 2) if risk > 0 else None
    qty = int(risk_per_trade / risk) if risk > 0 else None

    # ATR-based entry zone
    entry_zone_low = round(close - entry_atr_low * atr, 2)
    entry_zone_high = round(close + entry_atr_high * atr, 2)

    # Notional cap
    notional_capped = False
    if total_capital > 0 and qty is not None:
        max_notional = total_capital * (max_weight_pct / 100.0)
        if qty * close > max_notional:
            qty = max(1, int(max_notional / close))
            notional_capped = True

    return {
        "stop_loss": stop,
        "target_1": target_1,
        "target_2": target_2,
        "rr_ratio": rr,
        "position_size_shares": qty,
        "entry_zone_low": entry_zone_low,
        "entry_zone_high": entry_zone_high,
        "intermediate_resistance": intermediate_resistance,
        "intermediate_resistance_price": intermediate_resistance_price,
        "notional_capped": notional_capped,
    }


def _resistance_ceiling(
    symbol_id: int,
    close: float,
    atr: float,
    trendlines_by_symbol: dict[int, list],
    today: datetime.date,
) -> tuple[bool, float | None]:
    for tl in trendlines_by_symbol.get(symbol_id, []):
        if tl.trendline_type != "RESISTANCE" or tl.is_broken:
            continue
        projected = _project_trendline(
            tl.anchor1_date, float(tl.anchor1_price),
            tl.anchor2_date, float(tl.anchor2_price),
            today,
        )
        if close <= projected <= close + 1.5 * atr:
            return True, round(projected, 2)
    return False, None


def _best_support_trendline(
    symbol_id: int,
    close: float,
    trendlines_by_symbol: dict[int, list],
    today: datetime.date,
) -> tuple[float | None, int | None, float | None]:
    best = None
    for tl in trendlines_by_symbol.get(symbol_id, []):
        if tl.trendline_type != "SUPPORT" or tl.is_broken:
            continue
        projected = _project_trendline(
            tl.anchor1_date, float(tl.anchor1_price),
            tl.anchor2_date, float(tl.anchor2_price),
            today,
        )
        if projected >= close:
            continue
        if best is None or float(tl.score) > float(best.score):
            best = tl
    if best is None:
        return None, None, None
    return float(best.score), best.touch_count, float(best.slope_pct_per_day)


def _build_pick(
    snap: ScreeningSnapshot,
    indicator: DailyIndicator | None,
    levels: list,
    trendlines_by_symbol: dict[int, list],
    risk_per_trade: float,
    today: datetime.date,
    enforce_stage2: bool = True,
    min_rr_buy: float = 1.0,
    min_rr_watchlist: float = 0.4,
    stop_atr_mult: float = 1.5,
    entry_atr_low: float = 0.5,
    entry_atr_high: float = 0.25,
    min_res_strength: int = 30,
    total_capital: float = 0.0,
    max_weight_pct: float = 25.0,
) -> "SwingPick":
    close = float(snap.close_price)
    atr_pct = snap.atr_pct
    atr = (atr_pct / 100.0 * close) if atr_pct else close * 0.02

    plan = _compute_trade_plan(
        close, atr_pct, levels, risk_per_trade,
        stop_atr_mult, entry_atr_low, entry_atr_high,
        min_res_strength, total_capital, max_weight_pct,
    )
    res_ceil, res_price = _resistance_ceiling(snap.symbol_id, close, atr, trendlines_by_symbol, today)
    sup_score, sup_touches, sup_slope = _best_support_trendline(snap.symbol_id, close, trendlines_by_symbol, today)

    atv_cr = (float(snap.avg_traded_value) / 1e7) if snap.avg_traded_value else None
    rr = plan["rr_ratio"] or 0.0
    vol_ratio = float(snap.volume_breakout_ratio) if snap.volume_breakout_ratio else 0.0
    is_news_play = vol_ratio >= 4.0 or (snap.price_pct_change and abs(float(snap.price_pct_change)) >= 5.0)

    macd_hist = float(indicator.macd_histogram) if (indicator and indicator.macd_histogram is not None) else None

    # Classification
    if enforce_stage2 and snap.weinstein_stage != 2:
        category = "ELIMINATED"
        reason: str | None = f"Not in Weinstein Stage 2 (Stage {snap.weinstein_stage})"
    elif snap.supertrend_dir == "DOWN":
        category = "ELIMINATED"
        reason = "Supertrend DOWN — hard rule, no entry"
    elif res_ceil:
        category = "ELIMINATED"
        reason = f"CMP on resistance trendline at ₹{res_price} — ceiling at entry"
    elif rr < min_rr_watchlist:
        category = "ELIMINATED"
        reason = f"R:R {rr:.2f} — insufficient upside vs risk"
    elif snap.supertrend_dir == "UP" and rr >= min_rr_buy:
        category = "BUY"
        reason = None
    else:
        category = "WATCHLIST"
        reason = f"R:R {rr:.2f} — wait for pullback to improve entry"

    return SwingPick(
        symbol=snap.symbol.replace(".NS", ""),
        company_name=snap.company_name,
        close_price=close,
        atr_14=round(atr, 2),
        tqs=float(snap.tqs) if snap.tqs else None,
        weinstein_stage=snap.weinstein_stage,
        volume_breakout_ratio=float(snap.volume_breakout_ratio) if snap.volume_breakout_ratio else None,
        cmf_20=float(snap.cmf_20) if snap.cmf_20 is not None else None,
        rsi_14=float(snap.rsi_14) if snap.rsi_14 else None,
        supertrend_dir=snap.supertrend_dir,
        avg_traded_value_cr=round(atv_cr, 1) if atv_cr else None,
        stop_loss=plan["stop_loss"],
        target_1=plan["target_1"],
        target_2=plan["target_2"],
        rr_ratio=plan["rr_ratio"],
        position_size_shares=plan["position_size_shares"],
        entry_zone_low=plan["entry_zone_low"],
        entry_zone_high=plan["entry_zone_high"],
        category=category,
        elimination_reason=reason,
        resistance_ceiling=res_ceil,
        resistance_price=res_price,
        macd_histogram=macd_hist,
        macd_histogram_slope=float(snap.macd_histogram_slope) if snap.macd_histogram_slope is not None else None,
        composite_score=float(snap.composite_score) if snap.composite_score else None,
        support_score=sup_score,
        support_touch_count=sup_touches,
        support_slope_pct=sup_slope,
        is_news_play=bool(is_news_play),
        intermediate_resistance=plan["intermediate_resistance"],
        intermediate_resistance_price=plan["intermediate_resistance_price"],
        notional_capped=plan["notional_capped"],
    )


def _bulk_load_indicators(symbol_ids: list[int], db: Session) -> dict[int, DailyIndicator]:
    max_dates_sub = (
        select(DailyIndicator.symbol_id, func.max(DailyIndicator.trading_date).label("max_date"))
        .where(DailyIndicator.symbol_id.in_(symbol_ids))
        .group_by(DailyIndicator.symbol_id)
        .subquery()
    )
    rows = db.scalars(
        select(DailyIndicator).join(
            max_dates_sub,
            (DailyIndicator.symbol_id == max_dates_sub.c.symbol_id)
            & (DailyIndicator.trading_date == max_dates_sub.c.max_date),
        )
    ).all()
    return {r.symbol_id: r for r in rows}


# ─── Response models ──────────────────────────────────────────────────────────

class SwingPick(BaseModel):
    symbol: str
    company_name: str
    close_price: float
    atr_14: float | None
    tqs: float | None
    weinstein_stage: int | None
    volume_breakout_ratio: float | None
    cmf_20: float | None
    rsi_14: float | None
    supertrend_dir: str | None
    avg_traded_value_cr: float | None
    stop_loss: float | None
    target_1: float | None
    target_2: float | None
    rr_ratio: float | None
    position_size_shares: int | None
    entry_zone_low: float | None
    entry_zone_high: float | None
    category: str
    elimination_reason: str | None
    resistance_ceiling: bool
    resistance_price: float | None
    macd_histogram: float | None
    macd_histogram_slope: float | None
    composite_score: float | None
    support_score: float | None
    support_touch_count: int | None
    support_slope_pct: float | None
    is_news_play: bool
    intermediate_resistance: bool = False
    intermediate_resistance_price: float | None = None
    notional_capped: bool = False


class SwingPicksConfig(BaseModel):
    min_tqs: float
    min_volume_ratio: float
    min_atv_cr: float
    min_rr_buy: float
    min_rr_watchlist: float
    stop_atr_mult: float
    entry_atr_low: float
    entry_atr_high: float
    min_res_strength: int
    risk_per_trade: float


class SwingPicksSummary(BaseModel):
    total_screened: int
    buy_count: int
    watchlist_count: int
    eliminated_count: int


class SwingPicksResponse(BaseModel):
    run_at: str
    config: SwingPicksConfig
    summary: SwingPicksSummary
    buy_picks: list[SwingPick]
    watchlist: list[SwingPick]
    eliminated: list[SwingPick]


class QualifyRequest(BaseModel):
    symbols: list[str]


class NoteRequest(BaseModel):
    note: str


# ─── Notes endpoints ──────────────────────────────────────────────────────────

@router.get("/notes", response_model=dict[str, str])
def get_notes(db: Session = Depends(get_db)):
    """Return all saved swing pick catalyst notes as {symbol: note} dict."""
    rows = db.scalars(select(SwingPickNote)).all()
    return {r.symbol: r.catalyst_note or "" for r in rows}


@router.post("/notes/{symbol}", response_model=dict[str, str])
def save_note(symbol: str, body: NoteRequest, db: Session = Depends(get_db)):
    """Upsert a catalyst note for a symbol."""
    symbol = symbol.upper().replace(".NS", "")
    row = db.get(SwingPickNote, symbol)
    if row is None:
        row = SwingPickNote(symbol=symbol, catalyst_note=body.note)
        db.add(row)
    else:
        row.catalyst_note = body.note
        row.updated_at = datetime.datetime.now()
    db.commit()
    return {"symbol": symbol, "note": body.note}


# ─── Pipeline endpoint ────────────────────────────────────────────────────────

@router.get("", response_model=SwingPicksResponse)
def get_swing_picks(
    # Screening
    min_tqs: float = Query(65.0, description="Min Trend Quality Score"),
    min_volume_ratio: float = Query(1.0, description="Min volume breakout ratio"),
    min_atv_cr: float = Query(20.0, description="Min avg traded value (₹Cr)"),
    # Classification thresholds
    min_rr_buy: float = Query(0.75, description="Min R:R for BUY classification"),
    min_rr_watchlist: float = Query(0.4, description="Min R:R for WATCHLIST (below = ELIMINATED)"),
    # Trade plan parameters
    stop_atr_mult: float = Query(1.5, description="Stop loss = support − N×ATR"),
    entry_atr_low: float = Query(0.5, description="Entry zone low = CMP − N×ATR"),
    entry_atr_high: float = Query(0.25, description="Entry zone high = CMP + N×ATR"),
    min_res_strength: int = Query(30, description="Min strength score for resistance selection"),
    risk_per_trade: float = Query(0.0, description="Risk budget per trade ₹ (0 = use settings)"),
    db: Session = Depends(get_db),
):
    """3-step pipeline: Screen → Qualify (trendlines + trade plan) → Classify."""
    today = datetime.date.today()
    min_atv_raw = min_atv_cr * 1e7

    settings = SettingsService(db)
    if risk_per_trade <= 0:
        risk_per_trade = settings.get_float("PORTFOLIO", "default_risk_amount", 5000.0)
    total_capital = settings.get_float("PORTFOLIO", "capital", 0.0)
    max_weight_pct = settings.get_float("PORTFOLIO", "max_cluster_weight_pct", 25.0)

    snaps = db.scalars(
        select(ScreeningSnapshot)
        .where(~ScreeningSnapshot.symbol.like("^%"))
        .where(ScreeningSnapshot.weinstein_stage == 2)
        .where(ScreeningSnapshot.tqs >= min_tqs)
        .where(ScreeningSnapshot.volume_breakout_ratio >= min_volume_ratio)
        .where(ScreeningSnapshot.avg_traded_value >= min_atv_raw)
        .order_by(ScreeningSnapshot.composite_score.desc())
    ).all()

    if not snaps:
        return SwingPicksResponse(
            run_at=datetime.datetime.now().isoformat(),
            config=SwingPicksConfig(
                min_tqs=min_tqs, min_volume_ratio=min_volume_ratio, min_atv_cr=min_atv_cr,
                min_rr_buy=min_rr_buy, min_rr_watchlist=min_rr_watchlist,
                stop_atr_mult=stop_atr_mult, entry_atr_low=entry_atr_low, entry_atr_high=entry_atr_high,
                min_res_strength=min_res_strength, risk_per_trade=risk_per_trade,
            ),
            summary=SwingPicksSummary(total_screened=0, buy_count=0, watchlist_count=0, eliminated_count=0),
            buy_picks=[], watchlist=[], eliminated=[],
        )

    symbol_ids = [s.symbol_id for s in snaps]

    levels_by_symbol: dict[int, list] = defaultdict(list)
    for lvl in db.scalars(select(SymbolConfluenceLevel).where(SymbolConfluenceLevel.symbol_id.in_(symbol_ids))).all():
        levels_by_symbol[lvl.symbol_id].append(lvl)

    trendlines_by_symbol: dict[int, list] = defaultdict(list)
    for tl in db.scalars(
        select(SymbolTrendline).where(SymbolTrendline.symbol_id.in_(symbol_ids), SymbolTrendline.is_broken == False)
    ).all():
        trendlines_by_symbol[tl.symbol_id].append(tl)

    indicators_by_symbol = _bulk_load_indicators(symbol_ids, db)

    buy_picks, watchlist, eliminated = [], [], []
    for snap in snaps:
        pick = _build_pick(
            snap, indicators_by_symbol.get(snap.symbol_id),
            levels_by_symbol[snap.symbol_id], trendlines_by_symbol,
            risk_per_trade, today, enforce_stage2=False,
            min_rr_buy=min_rr_buy, min_rr_watchlist=min_rr_watchlist,
            stop_atr_mult=stop_atr_mult, entry_atr_low=entry_atr_low, entry_atr_high=entry_atr_high,
            min_res_strength=min_res_strength, total_capital=total_capital, max_weight_pct=max_weight_pct,
        )
        if pick.category == "BUY":
            buy_picks.append(pick)
        elif pick.category == "WATCHLIST":
            watchlist.append(pick)
        else:
            eliminated.append(pick)

    buy_picks.sort(key=lambda x: x.rr_ratio or 0, reverse=True)
    watchlist.sort(key=lambda x: x.rr_ratio or 0, reverse=True)

    return SwingPicksResponse(
        run_at=datetime.datetime.now().isoformat(),
        config=SwingPicksConfig(
            min_tqs=min_tqs, min_volume_ratio=min_volume_ratio, min_atv_cr=min_atv_cr,
            min_rr_buy=min_rr_buy, min_rr_watchlist=min_rr_watchlist,
            stop_atr_mult=stop_atr_mult, entry_atr_low=entry_atr_low, entry_atr_high=entry_atr_high,
            min_res_strength=min_res_strength, risk_per_trade=risk_per_trade,
        ),
        summary=SwingPicksSummary(
            total_screened=len(snaps),
            buy_count=len(buy_picks),
            watchlist_count=len(watchlist),
            eliminated_count=len(eliminated),
        ),
        buy_picks=buy_picks,
        watchlist=watchlist,
        eliminated=eliminated,
    )


# ─── Manual qualify endpoint ──────────────────────────────────────────────────

@router.post("/qualify", response_model=SwingPicksResponse)
def qualify_stocks(
    body: QualifyRequest,
    min_rr_buy: float = Query(1.0),
    min_rr_watchlist: float = Query(0.4),
    stop_atr_mult: float = Query(1.5),
    entry_atr_low: float = Query(0.5),
    entry_atr_high: float = Query(0.25),
    min_res_strength: int = Query(30),
    risk_per_trade: float = Query(0.0),
    db: Session = Depends(get_db),
):
    """Qualify a manually-provided list of symbols through the trade plan pipeline."""
    today = datetime.date.today()
    settings = SettingsService(db)
    if risk_per_trade <= 0:
        risk_per_trade = settings.get_float("PORTFOLIO", "default_risk_amount", 5000.0)
    total_capital = settings.get_float("PORTFOLIO", "capital", 0.0)
    max_weight_pct = settings.get_float("PORTFOLIO", "max_cluster_weight_pct", 25.0)

    raw_syms = [s.strip().upper() for s in body.symbols if s.strip()]
    normalised = [f"{s}.NS" if not s.endswith(".NS") and not s.startswith("^") else s for s in raw_syms]

    snaps = db.scalars(
        select(ScreeningSnapshot).where(ScreeningSnapshot.symbol.in_(normalised))
    ).all()

    found = {s.symbol for s in snaps}
    not_found = [s for s in normalised if s not in found]
    symbol_ids = [s.symbol_id for s in snaps]

    levels_by_symbol: dict[int, list] = defaultdict(list)
    if symbol_ids:
        for lvl in db.scalars(select(SymbolConfluenceLevel).where(SymbolConfluenceLevel.symbol_id.in_(symbol_ids))).all():
            levels_by_symbol[lvl.symbol_id].append(lvl)

    trendlines_by_symbol: dict[int, list] = defaultdict(list)
    if symbol_ids:
        for tl in db.scalars(
            select(SymbolTrendline).where(SymbolTrendline.symbol_id.in_(symbol_ids), SymbolTrendline.is_broken == False)
        ).all():
            trendlines_by_symbol[tl.symbol_id].append(tl)

    indicators_by_symbol = _bulk_load_indicators(symbol_ids, db) if symbol_ids else {}

    buy_picks, watchlist, eliminated = [], [], []
    for snap in snaps:
        pick = _build_pick(
            snap, indicators_by_symbol.get(snap.symbol_id),
            levels_by_symbol[snap.symbol_id], trendlines_by_symbol,
            risk_per_trade, today, enforce_stage2=True,
            min_rr_buy=min_rr_buy, min_rr_watchlist=min_rr_watchlist,
            stop_atr_mult=stop_atr_mult, entry_atr_low=entry_atr_low, entry_atr_high=entry_atr_high,
            min_res_strength=min_res_strength, total_capital=total_capital, max_weight_pct=max_weight_pct,
        )
        if pick.category == "BUY":
            buy_picks.append(pick)
        elif pick.category == "WATCHLIST":
            watchlist.append(pick)
        else:
            eliminated.append(pick)

    for sym in not_found:
        eliminated.append(SwingPick(
            symbol=sym.replace(".NS", ""), company_name="Not found in database",
            close_price=0, atr_14=None, tqs=None, weinstein_stage=None,
            volume_breakout_ratio=None, cmf_20=None, rsi_14=None, supertrend_dir=None,
            avg_traded_value_cr=None, stop_loss=None, target_1=None, target_2=None,
            rr_ratio=None, position_size_shares=None, entry_zone_low=None, entry_zone_high=None,
            category="ELIMINATED",
            elimination_reason="Symbol not found — ensure data is synced",
            resistance_ceiling=False, resistance_price=None,
            macd_histogram=None, macd_histogram_slope=None, composite_score=None,
            support_score=None, support_touch_count=None, support_slope_pct=None,
            is_news_play=False, intermediate_resistance=False, intermediate_resistance_price=None,
            notional_capped=False,
        ))

    buy_picks.sort(key=lambda x: x.rr_ratio or 0, reverse=True)
    watchlist.sort(key=lambda x: x.rr_ratio or 0, reverse=True)

    total = len(buy_picks) + len(watchlist) + len(eliminated)
    return SwingPicksResponse(
        run_at=datetime.datetime.now().isoformat(),
        config=SwingPicksConfig(
            min_tqs=0, min_volume_ratio=0, min_atv_cr=0,
            min_rr_buy=min_rr_buy, min_rr_watchlist=min_rr_watchlist,
            stop_atr_mult=stop_atr_mult, entry_atr_low=entry_atr_low, entry_atr_high=entry_atr_high,
            min_res_strength=min_res_strength, risk_per_trade=risk_per_trade,
        ),
        summary=SwingPicksSummary(
            total_screened=total, buy_count=len(buy_picks),
            watchlist_count=len(watchlist), eliminated_count=len(eliminated),
        ),
        buy_picks=buy_picks,
        watchlist=watchlist,
        eliminated=eliminated,
    )
