"""
swing_position_strategies.py
================================================================================
RESEARCH-BACKED SWING / POSITION TRADING STRATEGIES  (long-only equity)
Works on BOTH weekly and monthly bars via a single `timeframe` switch.
--------------------------------------------------------------------------------
Five well-documented strategies from the academic and practitioner literature,
each as a drop-in class matching the backtest contract:

    metadata, parameters, initialize(),
    generate_signals(market_data) -> [date, symbol, signal, target_weight],
    position_size(portfolio), stop_loss(trade), take_profit(trade)

All five are LONG-ONLY and designed for end-of-bar rebalancing on WEEKLY or
MONTHLY data. Every look-back is expressed in CALENDAR terms (months /
trading-days) and converted to a bar count from `timeframe`, so the same code
runs on weekly or monthly bars unchanged.

STRATEGIES & SOURCES
--------------------------------------------------------------------------------
1) CrossSectionalMomentum   - Jegadeesh & Titman (1993), 12-1 momentum.
2) FiftyTwoWeekHighMomentum - George & Hwang (2004), 52-week-high anchoring.
3) DualMomentum             - Antonacci GEM (relative + absolute momentum).
4) MinerviniTrendTemplate   - Minervini 8-point Stage-2 trend template.
5) WeinsteinStage2          - Weinstein Stage-2 breakout over a rising 30-week MA.

Dependencies: numpy, pandas only.
================================================================================
"""
from __future__ import annotations

import numpy as np
import pandas as pd


# =============================================================================
# Compact indicator helpers
# =============================================================================
def sma(s, n):
    return s.rolling(n, min_periods=n).mean()

def ema(s, span):
    return s.ewm(span=span, adjust=False, min_periods=span).mean()

def true_range(h, l, c):
    pc = c.shift(1)
    return pd.concat([(h - l), (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)

def atr(h, l, c, n):
    return true_range(h, l, c).ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()

def roc(c, n):
    return c.pct_change(n)

def rsi(c, n):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    rs = up / dn.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50.0)


def adx(h, l, c, length):
    up = h.diff()
    down = -l.diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr = true_range(h, l, c)
    atr_val = tr.ewm(alpha=1.0 / length, adjust=False, min_periods=length).mean()
    plus_di = 100 * pd.Series(plus_dm, index=h.index).ewm(
        alpha=1.0 / length, adjust=False, min_periods=length).mean() / atr_val
    minus_di = 100 * pd.Series(minus_dm, index=h.index).ewm(
        alpha=1.0 / length, adjust=False, min_periods=length).mean() / atr_val
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1.0 / length, adjust=False, min_periods=length).mean()


def bollinger(c, length, mult):
    mid = c.rolling(length, min_periods=length).mean()
    sd = c.rolling(length, min_periods=length).std(ddof=0)
    return mid - mult * sd, mid, mid + mult * sd


def keltner(h, l, c, length, atr_len, mult):
    mid = ema(c, length)
    rng = atr(h, l, c, atr_len)
    return mid - mult * rng, mid, mid + mult * rng


def swing_structure(high, low, left, right):
    n = len(high)
    piv_hi = np.full(n, np.nan)
    piv_lo = np.full(n, np.nan)
    h = high.values
    lo = low.values
    for i in range(left, n - right):
        window_h = h[i - left:i + right + 1]
        window_l = lo[i - left:i + right + 1]
        if h[i] == window_h.max() and (window_h.argmax() == left):
            piv_hi[i] = h[i]
        if lo[i] == window_l.min() and (window_l.argmin() == left):
            piv_lo[i] = lo[i]
    last_hi = pd.Series(piv_hi, index=high.index).ffill()
    prev_hi = pd.Series(piv_hi, index=high.index).ffill().shift(right + 1)
    last_lo = pd.Series(piv_lo, index=low.index).ffill()
    prev_lo = pd.Series(piv_lo, index=low.index).ffill().shift(right + 1)
    structure = pd.Series(0, index=high.index)
    structure[(last_hi > prev_hi) & (last_lo > prev_lo)] = 1
    structure[(last_hi < prev_hi) & (last_lo < prev_lo)] = -1
    return structure


def atr_percentile(atr_pct, lookback):
    def _rank(x):
        return (x[-1] >= x).mean()
    return atr_pct.rolling(lookback, min_periods=max(5, lookback // 4)).apply(_rank, raw=True)


# =============================================================================
# Shared base: timeframe scaling, market filter, ATR sizing, portfolio rebalance
# =============================================================================
_BASE = {
    "timeframe": "weekly",          # 'weekly' or 'monthly'  <-- the key switch
    "benchmark_symbol": None,       # e.g. "^NSEI"; else equal-weight proxy
    "use_market_filter": True,      # gate entries by index regime
    "regime_ma_days": 200,          # benchmark long MA for risk-on/off
    "max_open_positions": 10,       # portfolio breadth
    "weighting": "atr",             # 'atr' (vol-scaled) or 'equal'
    "risk_per_trade": 0.01,         # ATR fixed-fractional risk budget
    "stop_atr_mult": 3.0,           # initial catastrophic stop (x ATR)
    "trail_atr_mult": 4.0,          # chandelier trailing stop (x ATR)
    "atr_len_days": 63,             # ~3 months ATR for sizing/stops
    "max_position_weight": 0.20,    # per-name cap
    "max_gross_exposure": 1.0,      # long-only gross cap
    "profit_target_R": 0,           # 0 = let winners run
}


class _PortfolioStrategy:
    """Base class. Subclasses implement `_features(g)` returning per-bar:
    [date, symbol, close, high, low, atr, atr_pct, eligible, score, hold_ok].
    The base performs market gating, ranked selection, ATR sizing and exits."""

    metadata = {"name": "Base", "direction": "long_only", "asset_class": "equity_cash"}
    parameters = dict(_BASE)

    # ---- lifecycle -------------------------------------------------------
    def initialize(self):
        self._init = True

    # ---- timeframe scaling ----------------------------------------------
    def _bpy(self):
        tf = str(self.parameters["timeframe"]).lower()
        if tf.startswith("m"):
            return 12
        if tf.startswith("d"):
            return 252
        return 52

    def _bd(self, days):
        """trading-days -> bar count for the active timeframe."""
        factor = 252.0 / self._bpy()          # weekly~4.85, monthly=21, daily=1
        return max(1, int(round(days / factor)))

    def _bm(self, months):
        """months -> bar count for the active timeframe."""
        return max(1, int(round(months / 12.0 * self._bpy())))

    # ---- benchmark / market regime --------------------------------------
    def _benchmark_series(self, df):
        b = self.parameters.get("benchmark_symbol")
        if b is not None and b in set(df["symbol"].unique()):
            x = df[df["symbol"] == b].sort_values("date")[["date", "close"]]
            return x.rename(columns={"close": "bench_close"})
        piv = df.pivot_table(index="date", columns="symbol", values="close")
        norm = piv / piv.apply(lambda c: c.loc[c.first_valid_index()])
        comp = norm.mean(axis=1)
        return pd.DataFrame({"date": comp.index, "bench_close": comp.values})

    def _market_risk_on(self, df):
        b = self._benchmark_series(df).sort_values("date")
        c = b["bench_close"]
        ma = sma(c, self._bd(self.parameters["regime_ma_days"]))
        on = (c > ma) & (ma.diff() > 0)
        if not self.parameters["use_market_filter"]:
            on = pd.Series(True, index=c.index)
        return dict(zip(b["date"], on.fillna(False).values))

    # ---- main entry point ------------------------------------------------
    def generate_signals(self, market_data):
        if not hasattr(self, "_init"):
            self.initialize()
        df = market_data.copy()
        df["date"] = pd.to_datetime(df["date"])
        for col in ("open", "high", "low"):
            if col not in df.columns:
                df[col] = df["close"]
        if "volume" not in df.columns:
            df["volume"] = np.nan

        self._bench_close = self._benchmark_series(df).set_index("date")["bench_close"]
        risk_on = self._market_risk_on(df)
        bench_sym = self.parameters.get("benchmark_symbol")

        feats = []
        for sym, g in df.groupby("symbol"):
            if sym == bench_sym:
                continue
            feats.append(self._features(g.sort_values("date").reset_index(drop=True)))
        if not feats:
            return pd.DataFrame(columns=["date", "symbol", "signal", "target_weight"])
        F = pd.concat(feats, ignore_index=True)
        F["eligible"] = F["eligible"].fillna(False).astype(bool)
        F["hold_ok"] = F["hold_ok"].fillna(False).astype(bool)
        return self._select_portfolio(F, risk_on)

    # ---- ranked portfolio state machine ---------------------------------
    def _select_portfolio(self, F, risk_on):
        p = self.parameters
        maxpos = int(p["max_open_positions"])
        dates = sorted(F["date"].unique())
        held = {}                          # sym -> {entry_price, highest, entry_atr}
        held_weights = {}                  # date -> {sym: weight}

        by_date = {d: sub for d, sub in F.groupby("date")}
        for d in dates:
            sub = by_date[d]
            rowmap = {r["symbol"]: r for _, r in sub.iterrows()}
            ron = bool(risk_on.get(d, False))

            if not ron:
                held = {}                  # market off -> flat
            else:
                # 1) maintain / exit existing holdings
                for sym in list(held.keys()):
                    r = rowmap.get(sym)
                    if r is None:
                        held.pop(sym); continue
                    h = held[sym]
                    h["highest"] = max(h["highest"], float(r["close"]))
                    a = float(r["atr"]) if not pd.isna(r["atr"]) else 0.0
                    chandelier = h["highest"] - p["trail_atr_mult"] * a
                    init_stop = h["entry_price"] - p["stop_atr_mult"] * h["entry_atr"]
                    stop_line = max(chandelier, init_stop)
                    if (not bool(r["hold_ok"])) or (float(r["close"]) < stop_line):
                        held.pop(sym)
                # 2) fill open slots with top-ranked eligible names
                if len(held) < maxpos:
                    cand = sub[sub["eligible"] & ~sub["symbol"].isin(held.keys())]
                    cand = cand.sort_values("score", ascending=False)
                    for _, r in cand.iterrows():
                        if len(held) >= maxpos:
                            break
                        if pd.isna(r["atr"]) or float(r["atr"]) <= 0:
                            continue
                        held[r["symbol"]] = {
                            "entry_price": float(r["close"]),
                            "highest": float(r["close"]),
                            "entry_atr": float(r["atr"]),
                        }
            # 3) size the book for this date
            held_weights[d] = self._size_book(held, rowmap)

        # 4) build full panel output (row per date/symbol)
        out = F[["date", "symbol"]].copy()
        sig, wt = [], []
        for _, row in out.iterrows():
            w = held_weights.get(row["date"], {}).get(row["symbol"], 0.0)
            sig.append(1 if w > 0 else 0)
            wt.append(round(w, 4))
        out["signal"] = sig
        out["target_weight"] = wt
        return out

    def _size_book(self, held, rowmap):
        p = self.parameters
        maxw = p["max_position_weight"]
        raw = {}
        for sym in held:
            r = rowmap.get(sym)
            if r is None:
                continue
            if p["weighting"] == "equal":
                w = min(maxw, 1.0 / max(int(p["max_open_positions"]), 1))
            else:
                ap = float(r["atr_pct"]) if not pd.isna(r["atr_pct"]) else np.nan
                if not ap or np.isnan(ap) or ap <= 0:
                    w = min(maxw, 1.0 / max(int(p["max_open_positions"]), 1))
                else:
                    w = min(maxw, p["risk_per_trade"] / (p["stop_atr_mult"] * ap))
            raw[sym] = w
        total = sum(raw.values())
        if total > p["max_gross_exposure"] and total > 0:
            scale = p["max_gross_exposure"] / total
            raw = {k: v * scale for k, v in raw.items()}
        return raw

    # ---- relative strength helper (vs benchmark) ------------------------
    def _bench_roc(self, dates, n):
        b = self._bench_close.reindex(self._bench_close.index)
        br = b.pct_change(n)
        return pd.Series(dates).map(br).values

    # ---- per-symbol scaffolding ----------------------------------------
    def _base_cols(self, g):
        h, l, c = g["high"], g["low"], g["close"]
        a = atr(h, l, c, self._bd(self.parameters["atr_len_days"]))
        out = pd.DataFrame({
            "date": g["date"].values, "symbol": g["symbol"].values,
            "close": c.values, "high": h.values, "low": l.values,
            "atr": a.values, "atr_pct": (a / c).values,
        })
        return out, h, l, c

    # ---- framework hooks (shared) ---------------------------------------
    @staticmethod
    def _get(o, k, d=None):
        if o is None:
            return d
        return o.get(k, d) if isinstance(o, dict) else getattr(o, k, d)

    def position_size(self, portfolio):
        p = self.parameters
        eq = self._get(portfolio, "equity", 0.0) or 0.0
        px = self._get(portfolio, "price", 0.0) or 0.0
        a = self._get(portfolio, "atr", 0.0) or 0.0
        if eq <= 0 or px <= 0 or a <= 0:
            return {"shares": 0, "weight": 0.0, "stop_price": np.nan}
        stop_dist = p["stop_atr_mult"] * a
        risk_amt = eq * p["risk_per_trade"]
        w = min(p["max_position_weight"], p["risk_per_trade"] / (p["stop_atr_mult"] * (a / px)))
        shares = min(risk_amt / stop_dist, (w * eq) / px)
        return {"shares": int(max(0, np.floor(shares))), "weight": round(w, 4),
                "stop_price": round(px - stop_dist, 2)}

    def stop_loss(self, trade):
        p = self.parameters
        entry = self._get(trade, "entry_price")
        a = self._get(trade, "atr")
        hi = self._get(trade, "highest_high", entry)
        if entry is None or a is None:
            return None
        return round(max(entry - p["stop_atr_mult"] * a, (hi or entry) - p["trail_atr_mult"] * a), 2)

    def take_profit(self, trade):
        p = self.parameters
        R = p.get("profit_target_R", 0)
        if not R:
            return None
        entry = self._get(trade, "entry_price"); a = self._get(trade, "atr")
        if entry is None or a is None:
            return None
        return round(entry + R * p["stop_atr_mult"] * a, 2)


# =============================================================================
# 1) Cross-sectional momentum  (Jegadeesh & Titman 1993, 12-1)
# =============================================================================
class CrossSectionalMomentum(_PortfolioStrategy):
    metadata = {"name": "Cross-Sectional Momentum (12-1)", "direction": "long_only",
                "source": "Jegadeesh & Titman (1993)"}
    parameters = dict(_BASE, **{
        "formation_months": 12,    # total formation window
        "skip_months": 1,          # skip most recent month (reversal guard)
        "min_momentum": 0.0,       # long only if past return positive
        "trend_filter_days": 200,  # must also be above long MA (quality)
    })

    def _features(self, g):
        out, h, l, c = self._base_cols(g)
        form = self._bm(self.parameters["formation_months"])
        skip = self._bm(self.parameters["skip_months"])
        mom = c.shift(skip) / c.shift(form) - 1.0           # return t-12 .. t-1
        ma = sma(c, self._bd(self.parameters["trend_filter_days"]))
        out["score"] = mom.values
        out["eligible"] = ((mom > self.parameters["min_momentum"]) & (c > ma)).values
        out["hold_ok"] = (mom > self.parameters["min_momentum"]).values
        return out


# =============================================================================
# 2) 52-week high momentum  (George & Hwang 2004)
# =============================================================================
class FiftyTwoWeekHighMomentum(_PortfolioStrategy):
    metadata = {"name": "52-Week High Momentum", "direction": "long_only",
                "source": "George & Hwang (2004)"}
    parameters = dict(_BASE, **{
        "high_window_days": 252,   # 52 weeks
        "near_enter": 0.85,        # buy within 15% of the 52w high
        "near_exit": 0.75,         # exit if it falls >25% off the high
    })

    def _features(self, g):
        out, h, l, c = self._base_cols(g)
        win = self._bd(self.parameters["high_window_days"])
        hi = h.rolling(win, min_periods=win).max()
        near = c / hi
        out["score"] = near.values                          # closer to high ranks higher
        out["eligible"] = (near >= self.parameters["near_enter"]).values
        out["hold_ok"] = (near >= self.parameters["near_exit"]).values
        return out


# =============================================================================
# 3) Dual Momentum  (Antonacci GEM, single-name adaptation)
# =============================================================================
class DualMomentum(_PortfolioStrategy):
    metadata = {"name": "Dual Momentum (Absolute + Relative)", "direction": "long_only",
                "source": "Antonacci, Dual Momentum Investing (GEM)"}
    parameters = dict(_BASE, **{
        "timeframe": "weekly",     # GEM is classically monthly; weekly on daily-sourced data
        "lookback_months": 12,     # absolute & relative momentum window
        "cash_return_annual": 0.0, # absolute hurdle (proxy for T-bill/cash)
        "max_open_positions": 5,   # concentrated leaders
    })

    def _features(self, g):
        out, h, l, c = self._base_cols(g)
        lb = self._bm(self.parameters["lookback_months"])
        mom = c.pct_change(lb)
        # absolute hurdle scaled to the lookback length
        hurdle = (1 + self.parameters["cash_return_annual"]) ** (self.parameters["lookback_months"] / 12.0) - 1
        out["score"] = mom.values                            # relative: rank by strength
        out["eligible"] = (mom > hurdle).values              # absolute: beat cash
        out["hold_ok"] = (mom > hurdle).values
        return out


# =============================================================================
# 4) Minervini Trend Template (8-point Stage-2)
# =============================================================================
class MinerviniTrendTemplate(_PortfolioStrategy):
    metadata = {"name": "Minervini Trend Template", "direction": "long_only",
                "source": "Minervini, Trade/Think Like a Champion"}
    parameters = dict(_BASE, **{
        "ma_fast_days": 50, "ma_mid_days": 150, "ma_slow_days": 200,
        "high_window_days": 252,
        "above_low_pct": 0.30,     # >=30% above 52w low
        "below_high_pct": 0.25,    # within 25% of 52w high
        "rs_window_days": 126,     # ~6 months relative strength vs index
        "ma200_rising_days": 21,   # 200MA up over ~1 month
    })

    def _features(self, g):
        out, h, l, c = self._base_cols(g)
        P = self.parameters
        ma50 = sma(c, self._bd(P["ma_fast_days"]))
        ma150 = sma(c, self._bd(P["ma_mid_days"]))
        ma200 = sma(c, self._bd(P["ma_slow_days"]))
        win = self._bd(P["high_window_days"])
        hi52 = h.rolling(win, min_periods=win).max()
        lo52 = l.rolling(win, min_periods=win).min()
        rsw = self._bd(P["rs_window_days"])
        stock_rs = c.pct_change(rsw)
        bench_rs = pd.Series(g["date"].map(self._bench_close.pct_change(rsw)).values, index=c.index)

        c1 = (c > ma150) & (c > ma200)
        c2 = ma150 > ma200
        c3 = ma200 > ma200.shift(self._bd(P["ma200_rising_days"]))
        c4 = (ma50 > ma150) & (ma150 > ma200)
        c5 = c > ma50
        c6 = c >= (1 + P["above_low_pct"]) * lo52
        c7 = c >= (1 - P["below_high_pct"]) * hi52
        c8 = stock_rs > bench_rs                              # RS proxy for IBD RS>=70
        template = c1 & c2 & c3 & c4 & c5 & c6 & c7 & c8

        out["score"] = stock_rs.values                       # rank strongest leaders first
        out["eligible"] = template.fillna(False).values
        # hold while Stage-2 structure intact (looser than full template)
        out["hold_ok"] = ((c > ma150) & (ma150 > ma200)).fillna(False).values
        return out


# =============================================================================
# 5) Weinstein Stage-2 breakout (30-week MA + volume)
# =============================================================================
class WeinsteinStage2(_PortfolioStrategy):
    metadata = {"name": "Weinstein Stage-2 Breakout", "direction": "long_only",
                "source": "Weinstein, Secrets for Profiting in Bull & Bear Markets"}
    parameters = dict(_BASE, **{
        "ma_long_days": 150,       # 30 weeks
        "ma_short_days": 50,       # 10 weeks
        "high_window_days": 252,
        "near_high_pct": 0.05,     # at / near new highs (within 5%)
        "rvol_mult": 1.5,          # volume expansion on breakout
        "vol_avg_days": 50,
    })

    def _features(self, g):
        out, h, l, c = self._base_cols(g)
        P = self.parameters
        ma30 = sma(c, self._bd(P["ma_long_days"]))
        ma10 = sma(c, self._bd(P["ma_short_days"]))
        win = self._bd(P["high_window_days"])
        hi52 = h.rolling(win, min_periods=win).max()
        v = g["volume"]
        if v.notna().any():
            _vw = self._bd(P["vol_avg_days"])
            rvol = v / v.rolling(_vw, min_periods=min(5, _vw)).mean()
            rvol_ok = rvol >= P["rvol_mult"]
        else:
            rvol_ok = pd.Series(True, index=c.index)
        ma30_rising = ma30 > ma30.shift(self._bd(21))
        ma10_rising = ma10 > ma10.shift(self._bd(21))
        near_high = c >= (1 - P["near_high_pct"]) * hi52

        stage2 = (c > ma30) & ma30_rising & ma10_rising & near_high & rvol_ok
        out["score"] = (c / hi52).values                     # strongest proximity ranks first
        out["eligible"] = stage2.fillna(False).values
        out["hold_ok"] = (c > ma30).fillna(False).values     # stay above the 30-week line
        return out


# =============================================================================
# 6) RS Moving-Average Cross F1 (MA cross gated by a 10-point master score)
# =============================================================================
class RSMovingAverageCrossF1(_PortfolioStrategy):
    metadata = {"name": "RS Moving Average Cross F1", "direction": "long_only",
                "source": "MA crossover + 10-point master score (RS, trend, squeeze, structure)"}
    parameters = dict(_BASE, **{
        "fast_window": 20,             # fast MA (bars on the active timeframe)
        "slow_window": 50,             # slow MA
        "buy_score_min": 7,            # master-score threshold for a BUY (0-10)
        "hold_score_min": 5,           # master-score threshold to keep holding
        "atr_len_days": 20,
        "stop_atr_mult": 3.0,
        "trail_atr_mult": 4.5,
        "crossover_volume_filter": True,
        "max_position_weight": 0.20,
    })

    def _bench_roc_mapped(self, dates, n):
        b = self._bench_close.reindex(pd.to_datetime(dates))
        return b.pct_change(n).values

    def _features(self, g):
        out, h, l, c = self._base_cols(g)
        P = self.parameters
        v = g["volume"] if "volume" in g.columns else pd.Series(np.nan, index=g.index)

        fast = c.rolling(int(P["fast_window"]), min_periods=int(P["fast_window"])).mean()
        slow = c.rolling(int(P["slow_window"]), min_periods=int(P["slow_window"])).mean()

        # ── 10-point master score ───────────────────────────────────────────
        sma200 = sma(c, self._bd(P.get("regime_ma_days", 200)))
        c1 = (c > sma200) & (sma200.diff() > 0)                       # 1 primary trend
        c2 = ema(c, self._bd(10)) > ema(c, self._bd(40))             # 2 golden cross
        v_avg = v.rolling(20, min_periods=5).mean()
        c3 = (v > 1.3 * v_avg) if v.notna().any() else pd.Series(False, index=g.index)  # 3 rvol
        bb_l, _, bb_u = bollinger(c, 20, 2.0)
        kc_l, _, kc_u = keltner(h, l, c, 20, 20, 1.5)
        in_sq = (bb_l > kc_l) & (bb_u < kc_u)
        c4 = in_sq | in_sq.shift(1, fill_value=False) | in_sq.rolling(10, min_periods=1).max().fillna(0).astype(bool)
        c5 = adx(h, l, c, 14) > 18.0                                  # 5 trend strength
        rsi_val = rsi(c, 14)
        c6 = (rsi_val > 50) & (rsi_val <= 75)                        # 6 momentum zone
        hi52 = h.rolling(self._bd(252), min_periods=self._bd(252)).max().bfill().ffill()
        c7 = c >= 0.85 * hi52                                         # 7 near highs
        stock_roc = roc(c, self._bd(126))
        b_roc = pd.Series(self._bench_roc_mapped(g["date"].values, self._bd(126)), index=g.index).fillna(0.0)
        c8 = stock_roc.fillna(0.0) > b_roc                           # 8 relative strength
        atr_rank = atr_percentile(atr(h, l, c, 14) / c, 52)
        c9 = atr_rank.fillna(1.0) < 0.50                            # 9 vol contraction
        c10 = swing_structure(h, l, 3, 3) == 1                       # 10 HH/HL structure
        score = sum(x.astype(int) for x in (c1, c2, c3, c4, c5, c6, c7, c8, c9, c10))

        vol_ok = pd.Series(True, index=g.index)
        if P.get("crossover_volume_filter", True) and v.notna().any():
            vol_ok = v >= 1.2 * v_avg

        out["score"] = score.values
        out["eligible"] = ((fast > slow) & (score >= P["buy_score_min"]) & vol_ok).fillna(False).values
        out["hold_ok"] = ((fast > slow) & (score >= P["hold_score_min"])).fillna(False).values
        return out


# Registry for convenience
STRATEGIES = {
    "momentum": CrossSectionalMomentum,
    "high52": FiftyTwoWeekHighMomentum,
    "dual": DualMomentum,
    "minervini": MinerviniTrendTemplate,
    "weinstein": WeinsteinStage2,
    "rs_ma_cross": RSMovingAverageCrossF1,
}
