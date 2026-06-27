"""Portfolio service — backend source of truth for imported holdings + risk.

All parsing, persistence and risk/MTF composition lives here. The frontend
only renders the payload produced by :meth:`PortfolioService.get_portfolio`.
"""

from __future__ import annotations

import csv
import datetime
import re

from collections import defaultdict
from loguru import logger
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from stocks.db.models import DailyIndicator, DailyPrice, PortfolioHolding, ScreeningSnapshot, Symbol, SymbolConfluenceLevel
from stocks.services.quant.confluence_service import ConfluenceService
from stocks.services.quant.portfolio_risk import (
    compute_correlation_clusters,
    compute_diversification_score,
    compute_hhi,
    compute_portfolio_beta,
    compute_risk_contributions,
    compute_var_cvar,
)
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

        risk_per_trade = SettingsService(self.db).get_float("PORTFOLIO", "default_risk_amount", 5000.0)

        # Batch-load snapshots and confluence levels for the held symbols
        snap_by_instr: dict[str, ScreeningSnapshot] = {}
        confl_by_symbol_id: dict[int, list[SymbolConfluenceLevel]] = defaultdict(list)
        rs_threshold_bottom25: float | None = None
        if rows:
            instruments = {r.instrument for r in rows}
            ns_symbols = {f"{i}.NS" for i in instruments} | instruments
            snaps = self.db.scalars(
                select(ScreeningSnapshot).where(ScreeningSnapshot.symbol.in_(ns_symbols))
            ).all()
            for sn in snaps:
                snap_by_instr[sn.symbol.replace(".NS", "")] = sn

            symbol_ids = [r.symbol_id for r in rows if r.symbol_id is not None]
            if symbol_ids:
                confl_levels = self.db.scalars(
                    select(SymbolConfluenceLevel).where(SymbolConfluenceLevel.symbol_id.in_(symbol_ids))
                ).all()
                for lvl in confl_levels:
                    confl_by_symbol_id[lvl.symbol_id].append(lvl)

            # Batch-load latest supertrend price level for dynamic trailing stops
            supertrend_by_sid: dict[int, float | None] = {}
            if symbol_ids:
                _sub = (
                    select(
                        DailyIndicator.symbol_id,
                        func.max(DailyIndicator.trading_date).label("max_date"),
                    )
                    .where(DailyIndicator.symbol_id.in_(symbol_ids))
                    .group_by(DailyIndicator.symbol_id)
                    .subquery()
                )
                latest_inds = self.db.scalars(
                    select(DailyIndicator).join(
                        _sub,
                        (DailyIndicator.symbol_id == _sub.c.symbol_id)
                        & (DailyIndicator.trading_date == _sub.c.max_date),
                    )
                ).all()
                for ind in latest_inds:
                    supertrend_by_sid[ind.symbol_id] = (
                        float(ind.supertrend) if ind.supertrend is not None else None
                    )

            # Pre-compute universe RS bottom-quartile threshold for rotation detection
            all_rs = self.db.scalars(
                select(ScreeningSnapshot.rs_score_1m).where(ScreeningSnapshot.rs_score_1m.is_not(None))
            ).all()
            if all_rs:
                sorted_rs = sorted(float(v) for v in all_rs)
                rs_threshold_bottom25 = sorted_rs[int(len(sorted_rs) * 0.25)]

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

            # Get cached confluence levels
            symbol_levels = confl_by_symbol_id.get(r.symbol_id, [])
            pos_supports = [lvl for lvl in symbol_levels if lvl.level_type == "SUPPORT"]
            pos_resistances = [lvl for lvl in symbol_levels if lvl.level_type == "RESISTANCE"]

            valid_pos_supports = [lvl for lvl in pos_supports if float(lvl.price) < ltp]
            pos_supports_sorted = sorted(valid_pos_supports, key=lambda x: float(x.price), reverse=True)
            support_val = float(pos_supports_sorted[0].price) if pos_supports_sorted else None

            # Per-position open risk via confluence support, plus structural resistance targets
            atr_pct = float(snap.atr_pct) if snap and snap.atr_pct is not None else None
            snap_st_dir = snap.supertrend_dir if snap else None
            st_val = supertrend_by_sid.get(r.symbol_id) if r.symbol_id is not None else None
            stop_type = "structural"
            stop = open_risk = target_1 = target_2 = target_3 = potential_gain_pct = rr_ratio = None
            position_size_shares = None
            if atr_pct is not None and ltp > 0:
                atr_abs = atr_pct / 100.0 * ltp

                # Dynamic trailing stop: prefer Supertrend when it's below price & trending up
                if st_val is not None and snap_st_dir == "UP" and st_val < ltp:
                    if support_val is not None:
                        stop = round(max(st_val, support_val - 1.5 * atr_abs), 2)
                    else:
                        stop = round(st_val, 2)
                    if stop >= ltp:
                        stop = round(ltp - 2.0 * atr_abs, 2)
                    stop_type = "supertrend"
                elif support_val is not None:
                    stop = round(support_val - 1.5 * atr_abs, 2)
                    if stop >= ltp:
                        stop = round(ltp - 2.0 * atr_abs, 2)
                else:
                    stop = round(ltp - 1.5 * atr_abs, 2)

                open_risk = round(float(r.qty) * (ltp - stop), 2)
                total_open_risk += open_risk

                # T1: highest-strength resistance meaningfully above price
                best_r1 = ConfluenceService.select_best_resistance(pos_resistances, ltp, atr_abs)
                if best_r1 is not None:
                    target_1 = round(float(best_r1.price), 2)
                    above_t1 = sorted(
                        [rv for rv in pos_resistances if float(rv.price) > float(best_r1.price)],
                        key=lambda x: float(x.price),
                    )
                    if len(above_t1) >= 1:
                        target_2 = round(float(above_t1[0].price), 2)
                    if len(above_t1) >= 2:
                        target_3 = round(float(above_t1[1].price), 2)
                else:
                    target_1 = round(ltp + 1.5 * atr_abs, 2)
                    target_2 = round(ltp + 3.0 * atr_abs, 2)

                potential_gain_pct = round((target_1 - ltp) / ltp * 100.0, 2) if ltp > 0 else 0.0

                risk_per_share = ltp - stop
                reward_per_share = target_1 - ltp
                rr_ratio = round(reward_per_share / risk_per_share, 2) if risk_per_share > 0 else None
                if risk_per_share > 0 and risk_per_trade > 0:
                    vol_mult = 1.20 if atr_pct < 2.0 else (0.75 if atr_pct > 5.0 else 1.0)
                    position_size_shares = int(risk_per_trade * vol_mult / risk_per_share) or None

            if snap and snap.sma_200_cross_direction == "ABOVE":
                above_sma200 += 1

            total_invested += invested
            total_current += current_val

            # Weakness assessment → drives rotation/replacement suggestions
            bias = snap.regime_bias if snap else None
            mtf_ok = snap.mtf_confirmed if snap else None
            weak = False
            weak_reason = None
            if bias in ("BEARISH", "VERY_BEARISH"):
                weak, weak_reason = True, "Bearish bias"
            elif bias is not None and mtf_ok is False and bias not in ("VERY_BULLISH",):
                weak, weak_reason = True, "Weekly trend not confirmed"
            elif (
                rs_threshold_bottom25 is not None
                and snap is not None
                and snap.rs_score_1m is not None
                and float(snap.rs_score_1m) < rs_threshold_bottom25
                and bias not in ("VERY_BULLISH",)
            ):
                weak, weak_reason = True, "RS bottom quartile"

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
                    "target_2": target_2,
                    "target_3": target_3,
                    "potential_gain_pct": potential_gain_pct,
                    "rr_ratio": rr_ratio,
                    "position_size_shares": position_size_shares,
                    "stop_type": stop_type,
                    "composite_score": round(float(snap.composite_score), 1) if snap and snap.composite_score is not None else None,
                    "ml_label": snap.ml2_signal if snap else None,
                    "supertrend_dir": snap_st_dir,
                }
            )

        # ── Rolling alpha vs NIFTY (1W / 4W / 3M) ─────────────────────────────
        alpha_1w: float | None = None
        alpha_4w: float | None = None
        alpha_3m: float | None = None
        if holdings and total_current > 0:
            _nifty = self.db.scalar(select(ScreeningSnapshot).where(ScreeningSnapshot.symbol == "^NSEI"))
            if _nifty:
                _n1w = float(_nifty.ret_1w) if _nifty.ret_1w is not None else None
                _n4w = float(_nifty.ret_4w) if _nifty.ret_4w is not None else None
                _p1w = sum(h["current_val"] * (h["ret_1w"] or 0.0) for h in holdings) / total_current
                _p4w = sum(h["current_val"] * (h["ret_4w"] or 0.0) for h in holdings) / total_current
                if _n1w is not None and any(h["ret_1w"] is not None for h in holdings):
                    alpha_1w = round(_p1w - _n1w, 2)
                if _n4w is not None and any(h["ret_4w"] is not None for h in holdings):
                    alpha_4w = round(_p4w - _n4w, 2)
                if _nifty.symbol_id is not None:
                    _held_sids = [r.symbol_id for r in rows if r.symbol_id is not None]
                    _cutoff = datetime.date.today() - datetime.timedelta(days=91)
                    _price_rows = self.db.execute(
                        select(DailyPrice.symbol_id, DailyPrice.close)
                        .where(
                            DailyPrice.symbol_id.in_(_held_sids + [_nifty.symbol_id]),
                            DailyPrice.trading_date >= _cutoff,
                            DailyPrice.granularity == "1d",
                        )
                        .order_by(DailyPrice.symbol_id.asc(), DailyPrice.trading_date.asc())
                    ).all()
                    _by_sid: dict[int, list[float]] = {}
                    for _pr in _price_rows:
                        _by_sid.setdefault(_pr.symbol_id, []).append(float(_pr.close))
                    _nc = _by_sid.get(_nifty.symbol_id, [])
                    if len(_nc) >= 2:
                        _nr3m = (_nc[-1] - _nc[0]) / _nc[0] * 100.0
                        _sid2instr = {r.symbol_id: r.instrument for r in rows if r.symbol_id is not None}
                        _ir3m: dict[str, float] = {}
                        for _sid, _cl in _by_sid.items():
                            if _sid == _nifty.symbol_id or len(_cl) < 2:
                                continue
                            _instr = _sid2instr.get(_sid)
                            if _instr:
                                _ir3m[_instr] = (_cl[-1] - _cl[0]) / _cl[0] * 100.0
                        if _ir3m:
                            _p3m = sum(h["current_val"] * _ir3m.get(h["instrument"], 0.0) for h in holdings) / total_current
                            alpha_3m = round(_p3m - _nr3m, 2)

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
            heat_pct=heat_pct,
            heat_limit=heat_limit,
            heat_base=heat_base,
            limit=6,
        )

        # Portfolio-level risk (degrade gracefully on sparse data)
        correlation_clusters: list[dict] = []
        portfolio_beta: float | None = None
        diversification_score: int | None = None
        hhi_result: dict | None = None
        var_cvar: dict | None = None
        try:
            if len(holdings) >= 2:
                correlation_clusters = compute_correlation_clusters(self.db, holdings)
                weights = {
                    h["instrument"]: h["current_val"] / total_current
                    for h in holdings if total_current > 0
                }
                portfolio_beta = compute_portfolio_beta(self.db, holdings, weights)
                diversification_score = compute_diversification_score(
                    correlation_clusters, len(holdings), clusters
                )
                hhi_result = compute_hhi(weights)
                var_cvar = compute_var_cvar(self.db, holdings, weights, total_current)

                # Per-holding contribution to portfolio risk (% of portfolio variance).
                weights_by_id = {
                    h["symbol_id"]: h["current_val"] / total_current
                    for h in holdings
                    if h.get("symbol_id") and total_current > 0
                }
                rc = compute_risk_contributions(self.db, weights_by_id)
                for h in holdings:
                    h["risk_contribution_pct"] = (
                        round(rc[h["symbol_id"]] * 100.0, 2)
                        if h.get("symbol_id") in rc else None
                    )
        except Exception as e:
            logger.warning(f"Portfolio risk calculation failed (non-fatal): {e}")

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
                "correlation_clusters": correlation_clusters,
                "portfolio_beta": portfolio_beta,
                "diversification_score": diversification_score,
                "hhi": hhi_result.get("hhi") if hhi_result else None,
                "hhi_label": hhi_result.get("label") if hhi_result else None,
                "var_1d_pct": var_cvar.get("var_1d_pct") if var_cvar else None,
                "cvar_1d_pct": var_cvar.get("cvar_1d_pct") if var_cvar else None,
                "var_1d_inr": var_cvar.get("var_1d_inr") if var_cvar else None,
                "cvar_1d_inr": var_cvar.get("cvar_1d_inr") if var_cvar else None,
                "alpha_1w": alpha_1w,
                "alpha_4w": alpha_4w,
                "alpha_3m": alpha_3m,
            },
        }

    def _replacement_candidates(
        self,
        held_instruments: set[str],
        heat_pct: float = 0.0,
        heat_limit: float = 8.0,
        heat_base: float = 0.0,
        limit: int = 6,
    ) -> list[dict]:
        """High-quality, bullish, MTF-confirmed names NOT currently held — rotation pool.

        Ranks by risk-adjusted momentum: (ret_4w / atr_pct) + ADX strength + OBV confirmation.
        Candidates are also heat-aware: position_size_shares is capped so adding the position
        won't push total portfolio heat past the heat_limit.
        """
        held_ns = {f"{i}.NS" for i in held_instruments} | set(held_instruments)
        # Fetch a larger pool for client-side ranking, since we can't do the composite
        # score ordering in SQL without helper columns.
        rows = self.db.scalars(
            select(ScreeningSnapshot)
            .where(
                ScreeningSnapshot.regime_bias.in_(["BULLISH", "VERY_BULLISH"]),
                ScreeningSnapshot.mtf_confirmed == True,  # noqa: E712
                ScreeningSnapshot.rsi_14.is_not(None),
                ScreeningSnapshot.rsi_14 < 75,  # avoid badly overbought entries
                ScreeningSnapshot.symbol.not_in(held_ns),
                ScreeningSnapshot.symbol.not_like("^%"),  # exclude indices
                (ScreeningSnapshot.vol_class != "HIGH") | (ScreeningSnapshot.vol_class.is_(None)),
            )
            .order_by(ScreeningSnapshot.rsi_14.desc())
            .limit(limit * 5)  # fetch more, re-rank below
        ).all()

        def _momentum_score(sn: ScreeningSnapshot) -> float:
            score = 0.0
            ret_4w = float(sn.ret_4w) if sn.ret_4w is not None else 0.0
            atr_pct = float(sn.atr_pct) if sn.atr_pct is not None and float(sn.atr_pct) > 0 else 1.0
            score += ret_4w / atr_pct  # momentum per unit of volatility
            adx = float(getattr(sn, "adx_14", None) or 0)
            score += adx / 50.0  # ADX strength (0–1 range)
            if getattr(sn, "obv_trend", None) == "UP":
                score += 0.25  # reduced: confirms price action without dominating
            if sn.regime_bias == "VERY_BULLISH":
                score += 0.5  # highest conviction bonus
            if sn.composite_score is not None:
                score += float(sn.composite_score) * 0.5  # pre-computed multi-factor blend
            if sn.ml2_ev_score is not None:
                score += float(sn.ml2_ev_score) * 1.0  # VajraML signal
            return score

        ranked = sorted(rows, key=_momentum_score, reverse=True)[:limit]
        # Batch-load confluence levels for candidates
        cand_symbol_ids = [sn.symbol_id for sn in rows]
        confl_by_cand_id = defaultdict(list)
        if cand_symbol_ids:
            cand_levels = self.db.scalars(
                select(SymbolConfluenceLevel).where(SymbolConfluenceLevel.symbol_id.in_(cand_symbol_ids))
            ).all()
            for lvl in cand_levels:
                confl_by_cand_id[lvl.symbol_id].append(lvl)

        cand_risk_per_trade = SettingsService(self.db).get_float("PORTFOLIO", "default_risk_amount", 5000.0)

        # Remaining heat budget: how much more open risk can we add?
        remaining_heat_pct = max(0.0, heat_limit - heat_pct)
        remaining_heat_inr = (remaining_heat_pct / 100.0 * heat_base) if heat_base > 0 else None

        out = []
        for sn in ranked:
            close = round(float(sn.close_price), 2)
            atr_pct = round(float(sn.atr_pct), 2) if sn.atr_pct is not None else None

            cand_levels = confl_by_cand_id.get(sn.symbol_id, [])
            cand_supports = [lvl for lvl in cand_levels if lvl.level_type == "SUPPORT"]
            cand_resistances = [lvl for lvl in cand_levels if lvl.level_type == "RESISTANCE"]

            valid_cand_supports = [lvl for lvl in cand_supports if float(lvl.price) < close]
            cand_supports_sorted = sorted(valid_cand_supports, key=lambda x: float(x.price), reverse=True)
            support_val = float(cand_supports_sorted[0].price) if cand_supports_sorted else None

            stop = target_1 = target_2 = target_3 = gain = rr_ratio = position_size_shares = None
            if atr_pct is not None and close > 0:
                atr_abs = atr_pct / 100.0 * close

                # Structural stop-loss
                if support_val is not None:
                    stop = round(support_val - 1.5 * atr_abs, 2)
                    if stop >= close:
                        stop = round(close - 2.0 * atr_abs, 2)
                else:
                    stop = round(close - 1.5 * atr_abs, 2)

                # T1: highest-strength resistance
                best_r1 = ConfluenceService.select_best_resistance(cand_resistances, close, atr_abs)
                if best_r1 is not None:
                    target_1 = round(float(best_r1.price), 2)
                    above_t1 = sorted(
                        [rv for rv in cand_resistances if float(rv.price) > float(best_r1.price)],
                        key=lambda x: float(x.price),
                    )
                    if len(above_t1) >= 1:
                        target_2 = round(float(above_t1[0].price), 2)
                    if len(above_t1) >= 2:
                        target_3 = round(float(above_t1[1].price), 2)
                else:
                    target_1 = round(close + 1.5 * atr_abs, 2)
                    target_2 = round(close + 3.0 * atr_abs, 2)

                gain = round((target_1 - close) / close * 100.0, 2) if close > 0 else 0.0
                risk_per_share = close - stop
                reward_per_share = target_1 - close
                rr_ratio = round(reward_per_share / risk_per_share, 2) if risk_per_share > 0 else None
                if risk_per_share > 0 and cand_risk_per_trade > 0:
                    atr_pct_raw = float(sn.atr_pct) if sn.atr_pct is not None else None
                    vol_mult = 1.0
                    if atr_pct_raw is not None:
                        vol_mult = 1.20 if atr_pct_raw < 2.0 else (0.75 if atr_pct_raw > 5.0 else 1.0)
                    raw_size = int(cand_risk_per_trade * vol_mult / risk_per_share) or None
                    # Heat-aware cap: don't exceed remaining heat budget
                    if raw_size and remaining_heat_inr is not None and risk_per_share > 0:
                        max_by_heat = int(remaining_heat_inr / risk_per_share)
                        position_size_shares = min(raw_size, max_by_heat) if max_by_heat > 0 else raw_size
                    else:
                        position_size_shares = raw_size

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
                    "target_2": target_2,
                    "target_3": target_3,
                    "potential_gain_pct": gain,
                    "rr_ratio": rr_ratio,
                    "position_size_shares": position_size_shares,
                    "adx_14": round(float(getattr(sn, "adx_14", None) or 0), 1) or None,
                    "trend_strength_class": getattr(sn, "trend_strength_class", None),
                    "obv_trend": getattr(sn, "obv_trend", None),
                    "supertrend_dir": getattr(sn, "supertrend_dir", None),
                    "composite_score": round(float(sn.composite_score), 3) if sn.composite_score is not None else None,
                    "ml_prediction": round(float(sn.ml2_ev_score), 3) if sn.ml2_ev_score is not None else None,
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
        return {
            "VERY_BULLISH": "BULL",
            "BULLISH": "BULL",
            "NEUTRAL": "NEUTRAL",
            "BEARISH": "BEAR",
            "VERY_BEARISH": "BEAR",
        }.get(bias or "", "NEUTRAL")
