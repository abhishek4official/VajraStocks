"""AlertService — evaluates post-sync conditions and persists triggered alerts.

Called by the scheduler immediately after each EOD sync completes. Checks every
holding and all screened symbols for actionable state changes and inserts Alert
rows for any that fire. Existing TRIGGERED alerts for the same symbol+type from
the same calendar day are skipped (idempotent within a day).
"""

from __future__ import annotations

import datetime
from collections import defaultdict

from loguru import logger
from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from stocks.db.models import (
    Alert,
    PortfolioHolding,
    ScreeningSnapshot,
    SymbolConfluenceLevel,
)


_BIAS_ORDER = {
    "VERY_BEARISH": 0,
    "BEARISH": 1,
    "NEUTRAL": 2,
    "BULLISH": 3,
    "VERY_BULLISH": 4,
}

_BIAS_LABELS = {
    "VERY_BULLISH": "Very Bullish",
    "BULLISH": "Bullish",
    "NEUTRAL": "Neutral",
    "BEARISH": "Bearish",
    "VERY_BEARISH": "Very Bearish",
}


class AlertService:
    def __init__(self, db_session: Session):
        self.db = db_session

    # ── Public entry point ───────────────────────────────────────────────────

    def evaluate_all(self) -> int:
        """Evaluate all alert conditions for held symbols. Returns count of new alerts."""
        today = datetime.date.today()
        new_count = 0

        # Pre-load already-triggered alerts for today to avoid duplicates
        today_start = datetime.datetime.combine(today, datetime.time.min)
        existing_today = self.db.scalars(
            select(Alert).where(
                Alert.triggered_at >= today_start,
                Alert.status == "TRIGGERED",
            )
        ).all()
        fired_today: set[tuple[str, str]] = {(a.symbol, a.alert_type) for a in existing_today}

        # Load held symbols
        holdings = self.db.scalars(select(PortfolioHolding)).all()
        held_symbols: set[str] = set()
        for h in holdings:
            held_symbols.add(h.instrument)
            if h.instrument and not h.instrument.endswith(".NS"):
                held_symbols.add(f"{h.instrument}.NS")

        if not held_symbols:
            return 0

        # Batch-load snapshots and confluence levels
        snaps = self.db.scalars(
            select(ScreeningSnapshot).where(ScreeningSnapshot.symbol.in_(held_symbols))
        ).all()
        snap_by_symbol: dict[str, ScreeningSnapshot] = {s.symbol: s for s in snaps}
        # Also index without .NS suffix
        for s in snaps:
            bare = s.symbol.replace(".NS", "")
            snap_by_symbol.setdefault(bare, s)

        symbol_ids = [s.symbol_id for s in snaps if s.symbol_id is not None]
        confl_by_sid: dict[int, list[SymbolConfluenceLevel]] = defaultdict(list)
        if symbol_ids:
            for lvl in self.db.scalars(
                select(SymbolConfluenceLevel).where(SymbolConfluenceLevel.symbol_id.in_(symbol_ids))
            ).all():
                confl_by_sid[lvl.symbol_id].append(lvl)

        # Load previous snapshot states from yesterday's alerts for bias comparison
        yesterday_start = today_start - datetime.timedelta(days=1)
        prev_bias_alerts = self.db.scalars(
            select(Alert).where(
                Alert.alert_type.in_(["BIAS_UPGRADE", "BIAS_DOWNGRADE"]),
                Alert.triggered_at >= yesterday_start,
                Alert.triggered_at < today_start,
            )
        ).all()
        # Not needed for directional logic — we derive prev bias from the snapshot message below

        new_alerts: list[Alert] = []

        for h in holdings:
            instrument = h.instrument
            snap = snap_by_symbol.get(instrument) or snap_by_symbol.get(f"{instrument}.NS")
            if snap is None:
                continue

            close = float(snap.close_price)
            atr_pct = float(snap.atr_pct) if snap.atr_pct is not None else None
            atr_abs = (atr_pct / 100.0 * close) if atr_pct else close * 0.02
            symbol = snap.symbol

            lvls = confl_by_sid.get(snap.symbol_id, [])
            supports = sorted([l for l in lvls if l.level_type == "SUPPORT"], key=lambda x: float(x.price), reverse=True)
            resistances = sorted([l for l in lvls if l.level_type == "RESISTANCE"], key=lambda x: float(x.price))

            def _fire(alert_type: str, message: str, condition_value: float | None = None) -> None:
                key = (symbol, alert_type)
                if key in fired_today:
                    return
                new_alerts.append(Alert(
                    symbol_id=snap.symbol_id,
                    symbol=symbol,
                    alert_type=alert_type,
                    condition_value=condition_value,
                    status="TRIGGERED",
                    scope="HOLDING",
                    message=message,
                ))
                fired_today.add(key)
                nonlocal new_count
                new_count += 1

            # 1. Price crossed support
            if supports:
                nearest_sup = float(supports[0].price)
                if close < nearest_sup * 0.998:
                    _fire(
                        "PRICE_CROSS_SUPPORT",
                        f"{instrument} broke support ₹{nearest_sup:,.2f} (now ₹{close:,.2f})",
                        nearest_sup,
                    )

            # 2. Price crossed resistance
            if resistances:
                nearest_res = float(resistances[0].price)
                if close > nearest_res * 1.002:
                    _fire(
                        "PRICE_CROSS_RESISTANCE",
                        f"{instrument} broke resistance ₹{nearest_res:,.2f} (now ₹{close:,.2f})",
                        nearest_res,
                    )

            # 3. Stop-loss hit (structural stop = nearest support - 1.5×ATR)
            if supports:
                stop = round(float(supports[0].price) - 1.5 * atr_abs, 2)
                if close <= stop:
                    _fire(
                        "STOP_HIT",
                        f"{instrument} hit stop-loss ₹{stop:,.2f} (now ₹{close:,.2f})",
                        stop,
                    )

            # 4. Target hit (nearest resistance)
            if resistances:
                t1 = float(resistances[0].price)
                if close >= t1 * 0.998:
                    _fire(
                        "TARGET_HIT",
                        f"{instrument} reached target ₹{t1:,.2f} (now ₹{close:,.2f})",
                        t1,
                    )

            # 5. RSI extreme
            if snap.rsi_14 is not None:
                rsi = float(snap.rsi_14)
                if rsi < 30:
                    _fire("RSI_EXTREME", f"{instrument} RSI oversold at {rsi:.1f}", rsi)
                elif rsi > 75:
                    _fire("RSI_EXTREME", f"{instrument} RSI overbought at {rsi:.1f}", rsi)

            # 6. MACD cross (macd_trend changed — compare to holding's avg_cost era via vol flag)
            # We detect cross when MACD line just crossed signal (histogram flips sign)
            # Since we only have current snapshot, flag when histogram is near zero (fresh cross)
            # A proper cross alert needs yesterday's snapshot — skip for now, flag when macd_trend
            # is BULLISH and price_pct_change > 0, or use a simple fresh-cross heuristic
            # We use the existing macd_trend field as the state; the alert fires once per day anyway.

            # 7. Supertrend flip
            st_dir = getattr(snap, "supertrend_dir", None)
            if st_dir == "DOWN":
                _fire(
                    "SUPERTREND_FLIP",
                    f"{instrument} Supertrend flipped DOWN — trailing stop breached (₹{close:,.2f})",
                )

            # 8. Volume breakout
            vbr = getattr(snap, "volume_breakout_ratio", None)
            if vbr is not None and float(vbr) >= 2.0:
                _fire(
                    "VOLUME_BREAKOUT",
                    f"{instrument} volume surge {float(vbr):.1f}× average (₹{close:,.2f})",
                    float(vbr),
                )

            # 9. Bias upgrade / downgrade — compare to yesterday's alert if present
            # Find the most recent bias alert for this symbol to get its prior level
            prev_bias_alert = self.db.scalar(
                select(Alert)
                .where(
                    Alert.symbol == symbol,
                    Alert.alert_type.in_(["BIAS_UPGRADE", "BIAS_DOWNGRADE", "BIAS_INIT"]),
                )
                .order_by(Alert.triggered_at.desc())
                .limit(1)
            )

            current_bias = snap.regime_bias
            if current_bias and prev_bias_alert:
                prev_bias = prev_bias_alert.message.split("→")[-1].strip().split(" ")[0] if "→" in prev_bias_alert.message else None
                if prev_bias and prev_bias in _BIAS_ORDER and current_bias in _BIAS_ORDER:
                    prev_rank = _BIAS_ORDER[prev_bias]
                    curr_rank = _BIAS_ORDER[current_bias]
                    if curr_rank > prev_rank:
                        _fire(
                            "BIAS_UPGRADE",
                            f"{instrument} bias upgraded {_BIAS_LABELS.get(prev_bias, prev_bias)} → {_BIAS_LABELS.get(current_bias, current_bias)}",
                        )
                    elif curr_rank < prev_rank:
                        _fire(
                            "BIAS_DOWNGRADE",
                            f"{instrument} bias downgraded {_BIAS_LABELS.get(prev_bias, prev_bias)} → {_BIAS_LABELS.get(current_bias, current_bias)}",
                        )
            elif current_bias and not prev_bias_alert:
                # Seed the bias state — fire a silent init record
                new_alerts.append(Alert(
                    symbol_id=snap.symbol_id,
                    symbol=symbol,
                    alert_type="BIAS_INIT",
                    condition_value=None,
                    status="TRIGGERED",
                    scope="HOLDING",
                    message=f"{instrument} bias initialized → {current_bias}",
                ))

        if new_alerts:
            for a in new_alerts:
                self.db.add(a)
            self.db.commit()
            logger.info(f"AlertService: {new_count} new alerts triggered.")
        else:
            logger.debug("AlertService: No new alerts.")

        return new_count

    def get_alerts(self, status: str | None = None, limit: int = 100) -> list[Alert]:
        stmt = select(Alert).order_by(Alert.triggered_at.desc()).limit(limit)
        if status:
            stmt = stmt.where(Alert.status == status)
        return list(self.db.scalars(stmt).all())

    def dismiss(self, alert_id: int) -> bool:
        alert = self.db.get(Alert, alert_id)
        if not alert:
            return False
        alert.status = "DISMISSED"
        self.db.commit()
        return True

    def dismiss_all(self) -> int:
        alerts = self.db.scalars(select(Alert).where(Alert.status == "TRIGGERED")).all()
        count = 0
        for a in alerts:
            a.status = "DISMISSED"
            count += 1
        self.db.commit()
        return count
