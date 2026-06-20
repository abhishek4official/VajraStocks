"""Programmatic trendline detection and storage service.

Algorithm summary:
  1. Detect N-bar swing highs/lows (N=5) from 2 years of daily closes.
  2. Generate all anchor pairs of the same swing type.
  3. Validate: no candle closes on the wrong side of the line between the anchors (±0.5×ATR tolerance).
  4. Count additional touches (swing points within ±0.5×ATR of the projected line).
  5. Score each valid line: touch_count × recency_decay × log(duration).
  6. Non-max suppression: skip lines whose projected-today price is within 1×ATR of a
     higher-scored line of the same type (de-duplicate near-parallel lines).
  7. Store the top MAX_LINES support + MAX_LINES resistance lines per symbol.
"""

import datetime
import math

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from stocks.db.models import DailyPrice, Symbol, SymbolTrendline

_SWING_N = 5
_LOOKBACK_DAYS = 504   # ~2 years of trading days
_MAX_LINES = 5         # per type (support / resistance)
_TOUCH_ATR_MULT = 0.5  # ±fraction of ATR to count as a "touch"
_MAX_SLOPE_PCT_DAY = 0.5   # reject lines steeper than ±0.5%/day
_NMS_ATR_MULT = 1.0    # suppress duplicate lines within this × ATR at today's projection


# ─── helpers ─────────────────────────────────────────────────────────────────

def _date_ordinal(d: datetime.date) -> int:
    """Days since Unix epoch — used as a linear scale for interpolation."""
    return (d - datetime.date(1970, 1, 1)).days


def _project(d1: datetime.date, p1: float, d2: datetime.date, p2: float, target: datetime.date) -> float:
    o1, o2, ot = _date_ordinal(d1), _date_ordinal(d2), _date_ordinal(target)
    return p1 + (p2 - p1) * (ot - o1) / (o2 - o1)


def _compute_atr(prices: list, n: int = 14) -> float:
    recent = prices[-min(n + 1, len(prices)):]
    trs = []
    for i in range(1, len(recent)):
        h, l, pc = float(recent[i].high), float(recent[i].low), float(recent[i - 1].close)
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs) / len(trs) if trs else 0.0


def _detect_swings(prices: list, n: int) -> tuple[list, list]:
    """Return (swing_lows, swing_highs) as [(date, price), ...]."""
    lows, highs = [], []
    for i in range(n, len(prices) - n):
        window = prices[i - n: i + n + 1]
        low_i = float(prices[i].low)
        high_i = float(prices[i].high)
        if low_i <= min(float(p.low) for p in window):
            lows.append((prices[i].trading_date, low_i))
        if high_i >= max(float(p.high) for p in window):
            highs.append((prices[i].trading_date, high_i))
    return lows, highs


def _is_valid(
    d1: datetime.date, p1: float, d2: datetime.date, p2: float,
    prices: list, tl_type: str, atr: float,
) -> bool:
    """Return True if no close violates the line between the two anchors."""
    tol = atr * _TOUCH_ATR_MULT
    for p in prices:
        dt = p.trading_date
        if dt <= d1 or dt >= d2:
            continue
        proj = _project(d1, p1, d2, p2, dt)
        close = float(p.close)
        if tl_type == "SUPPORT" and close < proj - tol:
            return False
        if tl_type == "RESISTANCE" and close > proj + tol:
            return False
    return True


def _count_touches(
    d1: datetime.date, p1: float, d2: datetime.date, p2: float,
    swings: list, atr: float,
) -> list:
    tol = atr * _TOUCH_ATR_MULT
    return [
        (sd, sp) for sd, sp in swings
        if sd >= d1 and abs(sp - _project(d1, p1, d2, p2, sd)) <= tol
    ]


def _score(touches: list, latest_date: datetime.date, duration_days: int) -> float:
    if not touches:
        return 0.0
    most_recent = max(t[0] for t in touches)
    days_ago = (latest_date - most_recent).days
    recency = math.exp(-days_ago / 30.0)
    return len(touches) * recency * math.log(max(duration_days, 1) + 1)


def _find_break_date(
    d1: datetime.date, p1: float, d2: datetime.date, p2: float,
    prices: list, tl_type: str, atr: float,
) -> datetime.date | None:
    tol = atr * _TOUCH_ATR_MULT
    for p in reversed(prices[-30:]):
        proj = _project(d1, p1, d2, p2, p.trading_date)
        close = float(p.close)
        if tl_type == "SUPPORT" and close >= proj - tol:
            return p.trading_date
        if tl_type == "RESISTANCE" and close <= proj + tol:
            return p.trading_date
    return None


# ─── core computation ─────────────────────────────────────────────────────────

def compute_trendlines(prices: list) -> list[dict]:
    """
    Given a list of DailyPrice rows (ascending by trading_date), return a list
    of trendline dicts ready to be stored.  Caller is responsible for DB writes.
    """
    if len(prices) < _SWING_N * 2 + 5:
        return []

    atr = _compute_atr(prices)
    if not atr:
        return []

    swing_lows, swing_highs = _detect_swings(prices, _SWING_N)
    latest_date = prices[-1].trading_date
    latest_close = float(prices[-1].close)

    candidates: list[dict] = []

    for tl_type, swings in [("SUPPORT", swing_lows), ("RESISTANCE", swing_highs)]:
        if len(swings) < 2:
            continue

        for i in range(len(swings)):
            for j in range(i + 1, len(swings)):
                d1, p1 = swings[i]
                d2, p2 = swings[j]

                duration = (d2 - d1).days
                if duration < 5:
                    continue

                slope_pct = (p2 - p1) / p1 * 100 / duration
                if abs(slope_pct) > _MAX_SLOPE_PCT_DAY:
                    continue

                if not _is_valid(d1, p1, d2, p2, prices, tl_type, atr):
                    continue

                touches = _count_touches(d1, p1, d2, p2, swings, atr)
                if len(touches) < 2:
                    continue

                score = _score(touches, latest_date, duration)

                proj_latest = _project(d1, p1, d2, p2, latest_date)
                is_broken = False
                break_date = None
                if tl_type == "SUPPORT" and latest_close < proj_latest - atr * _TOUCH_ATR_MULT:
                    is_broken = True
                    break_date = _find_break_date(d1, p1, d2, p2, prices, tl_type, atr)
                elif tl_type == "RESISTANCE" and latest_close > proj_latest + atr * _TOUCH_ATR_MULT:
                    is_broken = True
                    break_date = _find_break_date(d1, p1, d2, p2, prices, tl_type, atr)

                candidates.append({
                    "trendline_type": tl_type,
                    "anchor1_date": d1,
                    "anchor1_price": p1,
                    "anchor2_date": d2,
                    "anchor2_price": p2,
                    "touch_count": len(touches),
                    "score": score,
                    "slope_pct_per_day": slope_pct,
                    "is_broken": is_broken,
                    "break_date": break_date,
                    "_proj_today": proj_latest,
                    "_type": tl_type,
                })

    candidates.sort(key=lambda x: x["score"], reverse=True)

    # Non-max suppression per type
    result: list[dict] = []
    for tl_type in ("SUPPORT", "RESISTANCE"):
        accepted: list[dict] = []
        for c in candidates:
            if c["_type"] != tl_type:
                continue
            too_close = any(
                abs(c["_proj_today"] - a["_proj_today"]) < atr * _NMS_ATR_MULT
                for a in accepted
            )
            if not too_close:
                accepted.append(c)
            if len(accepted) >= _MAX_LINES:
                break
        result.extend(accepted)

    # Strip internal keys before returning
    for c in result:
        c.pop("_proj_today", None)
        c.pop("_type", None)

    return result


# ─── service class ────────────────────────────────────────────────────────────

class TrendlineService:

    def __init__(self, db: Session):
        self.db = db

    def refresh_for_symbol(self, symbol_id: int, symbol_str: str, prices: list | None = None) -> None:
        if prices is None:
            cutoff = datetime.date.today() - datetime.timedelta(days=_LOOKBACK_DAYS)
            prices = list(
                self.db.scalars(
                    select(DailyPrice)
                    .where(
                        DailyPrice.symbol_id == symbol_id,
                        DailyPrice.trading_date >= cutoff,
                        DailyPrice.granularity == "1d",
                    )
                    .order_by(DailyPrice.trading_date.asc())
                ).all()
            )

        lines = compute_trendlines(prices)

        # Delete existing rows
        for existing in self.db.scalars(
            select(SymbolTrendline).where(SymbolTrendline.symbol_id == symbol_id)
        ).all():
            self.db.delete(existing)

        now = datetime.datetime.now()
        for line in lines:
            self.db.add(SymbolTrendline(symbol_id=symbol_id, symbol=symbol_str, computed_at=now, **line))

        self.db.flush()

    def refresh_all(self) -> int:
        """Refresh trendlines for all active symbols. Returns count of symbols processed."""
        active = list(self.db.scalars(select(Symbol).where(Symbol.is_active == True)).all())
        if not active:
            return 0

        logger.info(f"Computing trendlines for {len(active)} symbols ...")

        # Process one symbol at a time — each call fetches its own prices and commits.
        # This keeps transactions small and avoids MSSQL LocalDB pipe-closing timeouts
        # that occur with large bulk IN-clause loads.
        count = 0
        for sym in active:
            try:
                self.refresh_for_symbol(sym.id, sym.symbol)
                self.db.commit()
                count += 1
            except Exception as e:
                try:
                    self.db.rollback()
                except Exception:
                    pass
                logger.error(f"Trendline refresh failed for {sym.symbol}: {e}")

        logger.info(f"Trendlines computed for {count}/{len(active)} symbols.")
        return count
