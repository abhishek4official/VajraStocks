"""Portfolio service — backend source of truth for imported holdings + risk.

All parsing, persistence and risk/MTF composition lives here. The frontend
only renders the payload produced by :meth:`PortfolioService.get_portfolio`.
"""

from __future__ import annotations

import csv
import re

from loguru import logger
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from stocks.db.models import PortfolioHolding, ScreeningSnapshot, Symbol
from stocks.services.settings_service import SettingsService

# Column-name aliases (matched as substrings, lower-cased) — mirrors the old
# frontend Zerodha CSV parser so existing exports keep working.
_COLS = {
    "instrument": ["instrument", "symbol"],
    "qty": ["qty", "quantity"],
    "avg_cost": ["avg. cost", "avg cost", "average cost", "avg.cost"],
    "ltp": ["ltp", "last traded", "cur. price", "current price"],
    "invested": ["invested", "buy value", "buy val"],
    "current_val": ["cur. val", "curr. val", "current val", "curval", "market value"],
    "pnl": ["p&l", "pnl", "unrealised p&l", "profit"],
}


def _to_num(s: str) -> float:
    """Parses an Indian-formatted number string (strips ₹, commas, unicode minus)."""
    if s is None:
        return 0.0
    clean = re.sub(r"[₹,\s]", "", str(s)).replace("−", "-")
    try:
        return float(clean)
    except ValueError:
        return 0.0


def parse_zerodha_csv(csv_text: str) -> list[dict]:
    """Parses a Zerodha Console holdings CSV export into normalized holding dicts."""
    lines = [ln for ln in csv_text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return []

    header_idx = next((i for i, ln in enumerate(lines) if re.search(r"instrument", ln, re.I)), -1)
    if header_idx == -1:
        return []

    reader = list(csv.reader(lines[header_idx:]))
    if not reader:
        return []
    headers = [h.strip().strip('"').lower() for h in reader[0]]

    def col(row: list[str], keys: list[str]) -> str:
        for k in keys:
            idx = next((i for i, h in enumerate(headers) if k in h), -1)
            if idx != -1 and idx < len(row):
                return row[idx].strip().strip('"')
        return ""

    holdings: list[dict] = []
    for row in reader[1:]:
        if len(row) < 3:
            continue
        instrument = (
            col(row, _COLS["instrument"]).upper().replace(".NS", "").replace(" NS", "").strip()
        )
        if not instrument:
            continue
        qty = _to_num(col(row, _COLS["qty"]))
        avg_cost = _to_num(col(row, _COLS["avg_cost"]))
        ltp = _to_num(col(row, _COLS["ltp"]))
        invested = _to_num(col(row, _COLS["invested"])) or qty * avg_cost
        if qty <= 0:
            continue
        holdings.append(
            {"instrument": instrument, "qty": qty, "avg_cost": avg_cost, "ltp": ltp, "invested": invested}
        )
    return holdings


class PortfolioService:
    def __init__(self, db_session: Session):
        self.db = db_session

    # ── Mutations ───────────────────────────────────────────────────────────

    def import_csv(self, csv_text: str) -> int:
        """Replaces all holdings with the parsed CSV contents. Returns rows imported."""
        parsed = parse_zerodha_csv(csv_text)
        # Replace semantics: clear existing then insert fresh (simplest, deterministic)
        self.db.execute(delete(PortfolioHolding))
        held_symbol_ids: list[int] = []
        for h in parsed:
            sym = self.db.scalar(
                select(Symbol).where(
                    (Symbol.symbol == f"{h['instrument']}.NS") | (Symbol.symbol == h["instrument"])
                )
            )
            if sym:
                held_symbol_ids.append(sym.id)
            self.db.add(
                PortfolioHolding(
                    instrument=h["instrument"],
                    symbol_id=sym.id if sym else None,
                    qty=h["qty"],
                    avg_cost=h["avg_cost"],
                    ltp_imported=h["ltp"],
                    invested=h["invested"],
                    source="zerodha_csv",
                )
            )
        self.db.commit()

        # Ensure the held symbols have fresh MTF/risk fields materialized so the
        # portfolio shows full data immediately — even if the universe-wide
        # snapshot refresh hasn't run yet for these names.
        self._refresh_held_snapshots(held_symbol_ids)

        logger.info(f"Portfolio import: {len(parsed)} holdings stored.")
        return len(parsed)

    def _refresh_held_snapshots(self, symbol_ids: list[int]) -> None:
        """Refreshes screening snapshots (incl. MTF/risk fields) for the given symbols."""
        if not symbol_ids:
            return
        try:
            from stocks.services.screening import ScreeningService

            screener = ScreeningService(config=None, db_session=self.db)  # type: ignore[arg-type]
            nifty_ret = screener._get_nifty_21d_return()
            for sid in symbol_ids:
                screener.refresh_snapshot_for_symbol(sid, nifty_21d_return=nifty_ret)
        except Exception as e:
            logger.warning(f"Could not refresh held snapshots on import: {e}")

    def clear(self) -> None:
        self.db.execute(delete(PortfolioHolding))
        self.db.commit()

    # ── Composed read ───────────────────────────────────────────────────────

    def get_portfolio(self) -> dict:
        """Builds the full backend-computed portfolio payload (holdings + aggregates)."""
        s = SettingsService(self.db)
        capital = s.get_float("PORTFOLIO", "capital", 0.0)
        brokerage_pct = s.get_float("PORTFOLIO", "brokerage_pct", 0.03)
        stt_pct = s.get_float("PORTFOLIO", "stt_pct", 0.1)
        flat_fee = s.get_float("PORTFOLIO", "flat_fee_per_order", 20.0)
        include_charges = s.get_bool("PORTFOLIO", "include_charges_in_pnl", False)
        max_cluster_pct = s.get_float("PORTFOLIO", "max_cluster_weight_pct", 25.0)
        heat_limits = {
            "BULL": s.get_float("PORTFOLIO", "max_bull_heat_pct", 8.0),
            "NEUTRAL": s.get_float("PORTFOLIO", "max_neutral_heat_pct", 6.0),
            "BEAR": s.get_float("PORTFOLIO", "max_bear_heat_pct", 4.0),
        }

        rows = self.db.scalars(select(PortfolioHolding).order_by(PortfolioHolding.instrument.asc())).all()

        # Batch-load snapshots for the held symbols
        snap_by_instr: dict[str, ScreeningSnapshot] = {}
        if rows:
            instruments = {r.instrument for r in rows}
            ns_symbols = {f"{i}.NS" for i in instruments} | instruments
            snaps = self.db.scalars(
                select(ScreeningSnapshot).where(ScreeningSnapshot.symbol.in_(ns_symbols))
            ).all()
            for sn in snaps:
                snap_by_instr[sn.symbol.replace(".NS", "")] = sn

        holdings: list[dict] = []
        total_invested = total_current = total_open_risk = 0.0
        above_sma200 = 0
        for r in rows:
            snap = snap_by_instr.get(r.instrument)
            # Prefer latest synced close; fall back to imported LTP
            ltp = float(snap.close_price) if snap and snap.close_price else float(r.ltp_imported)
            ltp_source = "synced" if (snap and snap.close_price) else "imported"
            invested = float(r.invested) or float(r.qty) * float(r.avg_cost)
            current_val = float(r.qty) * ltp
            pnl = current_val - invested
            return_pct = (pnl / invested * 100.0) if invested else 0.0

            # Per-position open risk via ATR stop (1.5x ATR below LTP),
            # plus an ATR-based first target (T1 = LTP + 1.5x ATR).
            atr_pct = float(snap.atr_pct) if snap and snap.atr_pct is not None else None
            stop = open_risk = target_1 = potential_gain_pct = None
            if atr_pct is not None and ltp > 0:
                atr_abs = atr_pct / 100.0 * ltp
                stop = round(ltp - 1.5 * atr_abs, 2)
                open_risk = round(float(r.qty) * (ltp - stop), 2)
                total_open_risk += open_risk
                target_1 = round(ltp + 1.5 * atr_abs, 2)
                potential_gain_pct = round(1.5 * atr_pct, 2)

            if snap and snap.sma_200_cross_direction == "ABOVE":
                above_sma200 += 1

            total_invested += invested
            total_current += current_val

            # Weakness assessment → drives rotation/replacement suggestions
            bias = snap.regime_bias if snap else None
            mtf_ok = snap.mtf_confirmed if snap else None
            weak = False
            weak_reason = None
            if bias == "BEARISH":
                weak, weak_reason = True, "Bearish bias"
            elif bias is not None and mtf_ok is False:
                weak, weak_reason = True, "Weekly trend not confirmed"

            holdings.append(
                {
                    "instrument": r.instrument,
                    "qty": r.qty,
                    "avg_cost": round(float(r.avg_cost), 2),
                    "ltp": round(ltp, 2),
                    "ltp_source": ltp_source,
                    "invested": round(invested, 2),
                    "current_val": round(current_val, 2),
                    "pnl": round(pnl, 2),
                    "return_pct": round(return_pct, 2),
                    "bias": bias,
                    "mtf_confirmed": mtf_ok,
                    "weekly_trend": snap.weekly_trend if snap else None,
                    "atr_pct": round(atr_pct, 2) if atr_pct is not None else None,
                    "vol_class": snap.vol_class if snap else None,
                    "rs_score_1m": round(float(snap.rs_score_1m), 2) if snap and snap.rs_score_1m is not None else None,
                    "stop": stop,
                    "open_risk": open_risk,
                    "matched": snap is not None,
                    "weak": weak,
                    "weak_reason": weak_reason,
                    "ret_1w": round(float(snap.ret_1w), 2) if snap and snap.ret_1w is not None else None,
                    "ret_2w": round(float(snap.ret_2w), 2) if snap and snap.ret_2w is not None else None,
                    "ret_3w": round(float(snap.ret_3w), 2) if snap and snap.ret_3w is not None else None,
                    "ret_4w": round(float(snap.ret_4w), 2) if snap and snap.ret_4w is not None else None,
                    "target_1": target_1,
                    "potential_gain_pct": potential_gain_pct,
                }
            )

        total_pnl = total_current - total_invested
        # Charges estimate (round-trip): brokerage both legs + STT on sell side
        charges = 0.0
        for h in holdings:
            turnover = h["current_val"]
            brok = min(turnover * brokerage_pct / 100.0, flat_fee) * 2
            stt = turnover * stt_pct / 100.0
            charges += brok + stt
        net_pnl = total_pnl - charges if include_charges else total_pnl

        # Market regime from NIFTY 50 snapshot bias (fallback: holdings majority)
        regime = self._market_regime(holdings)
        heat_limit = heat_limits[regime]
        heat_base = capital if capital > 0 else total_invested
        heat_pct = (total_open_risk / heat_base * 100.0) if heat_base > 0 else 0.0

        # Concentration: single names exceeding the cluster cap
        clusters = []
        if total_current > 0:
            for h in holdings:
                weight = h["current_val"] / total_current * 100.0
                if weight > max_cluster_pct:
                    clusters.append({"instrument": h["instrument"], "weight_pct": round(weight, 1)})

        breadth_pct = (above_sma200 / len(holdings) * 100.0) if holdings else 0.0

        weak_holdings = [h["instrument"] for h in holdings if h["weak"]]
        candidates = self._replacement_candidates(
            held_instruments={h["instrument"] for h in holdings},
            limit=6,
        )

        return {
            "holdings": holdings,
            "aggregates": {
                "total_invested": round(total_invested, 2),
                "total_current": round(total_current, 2),
                "total_pnl": round(total_pnl, 2),
                "total_return_pct": round(total_pnl / total_invested * 100.0, 2) if total_invested else 0.0,
                "net_pnl": round(net_pnl, 2),
                "charges": round(charges, 2),
                "include_charges": include_charges,
                "positions": len(holdings),
                "open_risk": round(total_open_risk, 2),
                "heat_pct": round(heat_pct, 2),
                "heat_limit": heat_limit,
                "heat_base": round(heat_base, 2),
                "heat_base_is_capital": capital > 0,
                "regime": regime,
                "breadth_pct": round(breadth_pct, 1),
                "clusters": clusters,
                "max_cluster_pct": max_cluster_pct,
                "weak_holdings": weak_holdings,
                "replacement_candidates": candidates,
            },
        }

    def _replacement_candidates(self, held_instruments: set[str], limit: int = 6) -> list[dict]:
        """High-RS, bullish, MTF-confirmed names NOT currently held — rotation pool.

        Implements the spirit of SRS Module L (Dynamic Stock Replacement): surface
        strong breakout candidates to rotate weak/stopped positions into.
        """
        held_ns = {f"{i}.NS" for i in held_instruments} | set(held_instruments)
        # Rank within the strong-filtered pool by RSI momentum — regime-robust,
        # unlike rs_score_1m which is unreliable when NIFTY's return is negative.
        rows = self.db.scalars(
            select(ScreeningSnapshot)
            .where(
                ScreeningSnapshot.regime_bias == "BULLISH",
                ScreeningSnapshot.mtf_confirmed == True,  # noqa: E712
                ScreeningSnapshot.rsi_14.is_not(None),
                ScreeningSnapshot.rsi_14 < 75,  # avoid badly overbought entries
                ScreeningSnapshot.symbol.not_in(held_ns),
                ScreeningSnapshot.symbol.not_like("^%"),  # exclude indices
                (ScreeningSnapshot.vol_class != "HIGH") | (ScreeningSnapshot.vol_class.is_(None)),
            )
            .order_by(ScreeningSnapshot.rsi_14.desc())
            .limit(limit)
        ).all()
        out = []
        for sn in rows:
            close = round(float(sn.close_price), 2)
            atr_pct = round(float(sn.atr_pct), 2) if sn.atr_pct is not None else None
            stop = target_1 = gain = None
            if atr_pct is not None and close > 0:
                atr_abs = atr_pct / 100.0 * close
                stop = round(close - 1.5 * atr_abs, 2)
                target_1 = round(close + 1.5 * atr_abs, 2)
                gain = round(1.5 * atr_pct, 2)
            out.append(
                {
                    "symbol": sn.symbol.replace(".NS", ""),
                    "company_name": sn.company_name,
                    "close_price": close,
                    "rsi_14": round(float(sn.rsi_14), 1) if sn.rsi_14 is not None else None,
                    "atr_pct": atr_pct,
                    "vol_class": sn.vol_class,
                    "bias": sn.regime_bias,
                    "weekly_trend": sn.weekly_trend,
                    "ret_1w": round(float(sn.ret_1w), 2) if sn.ret_1w is not None else None,
                    "ret_2w": round(float(sn.ret_2w), 2) if sn.ret_2w is not None else None,
                    "ret_3w": round(float(sn.ret_3w), 2) if sn.ret_3w is not None else None,
                    "ret_4w": round(float(sn.ret_4w), 2) if sn.ret_4w is not None else None,
                    "stop_loss": stop,
                    "target_1": target_1,
                    "potential_gain_pct": gain,
                }
            )
        return out

    def _market_regime(self, holdings: list[dict]) -> str:
        """Returns BULL / NEUTRAL / BEAR from NIFTY 50 bias, else holdings majority."""
        nifty = self.db.scalar(select(ScreeningSnapshot).where(ScreeningSnapshot.symbol == "^NSEI"))
        bias = nifty.regime_bias if nifty else None
        if bias is None and holdings:
            biases = [h["bias"] for h in holdings if h["bias"]]
            if biases:
                bias = max(set(biases), key=biases.count)
        return {"BULLISH": "BULL", "BEARISH": "BEAR", "NEUTRAL": "NEUTRAL"}.get(bias or "", "NEUTRAL")
