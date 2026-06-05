"""Composite scoring engine — replaces the binary compute_bias approach.

Scores each symbol across 4 weighted components (0–100 each) and derives a
5-tier bias from the weighted composite. No hard SMA200 band — every partial
signal contributes proportionally.

Weights:
  Trend Score     40%   (EMA20/50/200 cross, alignment, ADX)
  Volume Score    25%   (Relative Volume, OBV, Delivery % placeholder)
  RS Score        20%   (RS vs Nifty, rolling momentum)
  Momentum Score  15%   (RSI, MACD histogram, Stochastic)

Bias thresholds (composite 0–100):
  VERY_BULLISH  ≥ 72
  BULLISH       ≥ 52
  NEUTRAL       ≥ 35
  BEARISH       ≥ 18
  VERY_BEARISH  < 18
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CompositeResult:
    bias: str                    # VERY_BULLISH / BULLISH / NEUTRAL / BEARISH / VERY_BEARISH
    composite_score: float       # 0–100 weighted total
    trend_score: float           # 0–100
    volume_score: float          # 0–100
    rs_score: float              # 0–100
    momentum_score: float        # 0–100
    reasons: list[str]


def _cap(v: float) -> float:
    return max(0.0, min(100.0, v))


def score_trend(
    close: float,
    ema_20: float | None,
    sma_50: float | None,
    sma_200: float | None,
    ema_21: float | None,      # fallback when ema_20 absent
    adx_14: float | None,
    plus_di: float | None,
    minus_di: float | None,
    supertrend_dir: str | None = None,
) -> tuple[float, list[str]]:
    """
    Points:
      Price > EMA200          30 pts
      Price > EMA50           25 pts
      Price > EMA20           20 pts
      EMA20 > EMA50 > EMA200  15 pts  (full bull alignment)
      EMA20 > EMA50 only       8 pts  (partial)
      ADX ≥ 40               10 pts
      ADX ≥ 25                5 pts
      DI+ > DI-               5 pts  (directional confirmation when ADX strong)
      Supertrend UP            5 pts  (ATR trailing stop not breached)
      Supertrend DOWN         -5 pts
    """
    pts = 0.0
    reasons: list[str] = []
    ema20 = ema_20 if ema_20 is not None else ema_21   # use EMA21 as proxy when EMA20 missing

    if sma_200 is not None and sma_200 > 0:
        if close > sma_200:
            pts += 30
            reasons.append(f"Price {close:.2f} > EMA200 {sma_200:.2f} (+30)")
        else:
            gap = (sma_200 - close) / sma_200 * 100
            reasons.append(f"Price {close:.2f} < EMA200 {sma_200:.2f} by {gap:.1f}% (0)")

    if sma_50 is not None and sma_50 > 0:
        if close > sma_50:
            pts += 25
            reasons.append(f"Price > EMA50 {sma_50:.2f} (+25)")
        else:
            reasons.append(f"Price < EMA50 {sma_50:.2f} (0)")

    if ema20 is not None and ema20 > 0:
        if close > ema20:
            pts += 20
            reasons.append(f"Price > EMA20 {ema20:.2f} (+20)")
        else:
            reasons.append(f"Price < EMA20 {ema20:.2f} (0)")

    # EMA alignment bonus
    if ema20 is not None and sma_50 is not None and sma_200 is not None:
        if ema20 > sma_50 > sma_200:
            pts += 15
            reasons.append("Full bull alignment EMA20>EMA50>EMA200 (+15)")
        elif ema20 > sma_50:
            pts += 8
            reasons.append("Partial alignment EMA20>EMA50 (+8)")
        elif sma_50 > sma_200:
            pts += 4
            reasons.append("EMA50>EMA200 partial alignment (+4)")

    # ADX strength
    if adx_14 is not None:
        if adx_14 >= 40:
            pts += 10
            reasons.append(f"ADX {adx_14:.0f} ≥ 40 strong trend (+10)")
        elif adx_14 >= 25:
            pts += 5
            reasons.append(f"ADX {adx_14:.0f} ≥ 25 developing trend (+5)")
        else:
            reasons.append(f"ADX {adx_14:.0f} < 25 weak trend (0)")

        # DI directional confirmation (only meaningful when ADX is strong)
        if adx_14 >= 25 and plus_di is not None and minus_di is not None:
            if plus_di > minus_di:
                pts += 5
                reasons.append(f"DI+ {plus_di:.0f} > DI- {minus_di:.0f} (+5)")

    # Supertrend direction — price above/below ATR trailing stop
    if supertrend_dir == "UP":
        pts += 5
        reasons.append("Supertrend UP — above ATR stop (+5)")
    elif supertrend_dir == "DOWN":
        pts = max(0.0, pts - 5)
        reasons.append("Supertrend DOWN — below ATR stop (-5)")

    return _cap(pts), reasons


def score_volume(
    volume_breakout_ratio: float | None,
    obv_trend: str | None,
    delivery_pct: float | None = None,   # NSE delivery %, None = not available
) -> tuple[float, list[str]]:
    """
    Points:
      OBV trend UP            35 pts  (neutral=17 when data absent)
      Vol breakout ≥ 2x       35 pts  (neutral=17 when data absent)
      Delivery % ≥ 60%        30 pts  (placeholder=15 when absent)
      Delivery % ≥ 40%        15 pts

    When both OBV and VBR are unavailable, the score falls back to 40 (neutral)
    so missing data does not punish the composite.
    """
    pts = 0.0
    reasons: list[str] = []
    obv_missing = obv_trend is None or obv_trend == "FLAT"
    vbr_missing = volume_breakout_ratio is None

    if obv_trend == "UP":
        pts += 35
        reasons.append("OBV trend UP (+35)")
    elif obv_trend == "DOWN":
        reasons.append("OBV trend DOWN (0)")
    elif obv_missing:
        pts += 17  # neutral when data not yet available
        reasons.append("OBV trend: insufficient data — neutral (+17)")

    if not vbr_missing:
        vbr = float(volume_breakout_ratio)
        if vbr >= 2.0:
            pts += 35
            reasons.append(f"Volume {vbr:.1f}x average (+35)")
        elif vbr >= 1.5:
            pts += 20
            reasons.append(f"Volume {vbr:.1f}x average (+20)")
        elif vbr >= 1.2:
            pts += 10
            reasons.append(f"Volume {vbr:.1f}x average (+10)")
        else:
            reasons.append(f"Volume {vbr:.1f}x average — in-line (0)")
    else:
        pts += 17  # neutral when data not yet available
        reasons.append("Volume breakout ratio: insufficient data — neutral (+17)")

    # Delivery % — placeholder = 15 (neutral) when data not available
    if delivery_pct is not None:
        if delivery_pct >= 60:
            pts += 30
            reasons.append(f"Delivery {delivery_pct:.0f}% >= 60% (+30)")
        elif delivery_pct >= 40:
            pts += 15
            reasons.append(f"Delivery {delivery_pct:.0f}% >= 40% (+15)")
        else:
            reasons.append(f"Delivery {delivery_pct:.0f}% < 40% (0)")
    else:
        pts += 15
        reasons.append("Delivery %: data unavailable — neutral (+15)")

    return _cap(pts), reasons


def score_rs(
    rs_score_1m: float | None,
    ret_1w: float | None,
    ret_4w: float | None,
) -> tuple[float, list[str]]:
    """
    Points:
      RS vs Nifty > 1.5       40 pts  (strongly outperforming)
      RS vs Nifty > 1.2       30 pts
      RS vs Nifty > 1.0       20 pts  (outperforming)
      RS vs Nifty 0.8–1.0     10 pts  (near par)
      ret_4w > 8%             30 pts
      ret_4w > 3%             20 pts
      ret_4w > 0%             10 pts
      ret_1w > 0%             10 pts  (recent positive momentum)
    """
    pts = 0.0
    reasons: list[str] = []

    if rs_score_1m is not None:
        rs = float(rs_score_1m)
        if rs > 1.5:
            pts += 40
            reasons.append(f"RS vs Nifty {rs:.2f} >1.5 strongly outperforming (+40)")
        elif rs > 1.2:
            pts += 30
            reasons.append(f"RS vs Nifty {rs:.2f} >1.2 outperforming (+30)")
        elif rs > 1.0:
            pts += 20
            reasons.append(f"RS vs Nifty {rs:.2f} >1.0 outperforming (+20)")
        elif rs >= 0.8:
            pts += 10
            reasons.append(f"RS vs Nifty {rs:.2f} near par (+10)")
        else:
            reasons.append(f"RS vs Nifty {rs:.2f} underperforming (0)")

    if ret_4w is not None:
        r = float(ret_4w)
        if r > 8:
            pts += 30
            reasons.append(f"4W return {r:.1f}% > 8% (+30)")
        elif r > 3:
            pts += 20
            reasons.append(f"4W return {r:.1f}% > 3% (+20)")
        elif r > 0:
            pts += 10
            reasons.append(f"4W return {r:.1f}% positive (+10)")
        else:
            reasons.append(f"4W return {r:.1f}% negative (0)")

    if ret_1w is not None and float(ret_1w) > 0:
        pts += 10
        reasons.append(f"1W return {float(ret_1w):.1f}% positive (+10)")

    return _cap(pts), reasons


def score_momentum(
    rsi_14: float | None,
    macd_histogram: float | None,
    macd_histogram_prev: float | None = None,  # for growing/shrinking detection
    stoch_k: float | None = None,
) -> tuple[float, list[str]]:
    """
    Points:
      RSI 55–70 (bullish sweet spot)  40 pts
      RSI 70–80 (strong momentum)     30 pts
      RSI 40–55 (mid range)           20 pts
      RSI 80–90 (overbought caution)  15 pts
      RSI < 40 or > 90                 0 pts

      MACD hist > 0 AND growing       35 pts
      MACD hist > 0 flat/unknown      20 pts
      MACD hist < 0                    0 pts

      Stochastic K 40–80 (healthy)    15 pts
      Stochastic K 20–40 (recovering)  8 pts
      Stochastic K < 20 (oversold)     5 pts  (bounce potential)
    """
    pts = 0.0
    reasons: list[str] = []

    if rsi_14 is not None:
        rsi = float(rsi_14)
        if 55 <= rsi <= 70:
            pts += 40
            reasons.append(f"RSI {rsi:.1f} in sweet spot 55–70 (+40)")
        elif 70 < rsi <= 80:
            pts += 30
            reasons.append(f"RSI {rsi:.1f} strong momentum 70–80 (+30)")
        elif 40 <= rsi < 55:
            pts += 20
            reasons.append(f"RSI {rsi:.1f} mid range 40–55 (+20)")
        elif 80 < rsi <= 90:
            pts += 15
            reasons.append(f"RSI {rsi:.1f} overbought zone 80–90 (+15)")
        else:
            reasons.append(f"RSI {rsi:.1f} extreme zone (0)")

    if macd_histogram is not None:
        h = float(macd_histogram)
        if h > 0:
            growing = (
                macd_histogram_prev is not None and h > float(macd_histogram_prev)
            )
            if growing:
                pts += 35
                reasons.append(f"MACD hist {h:.4f} positive and growing (+35)")
            else:
                pts += 20
                reasons.append(f"MACD hist {h:.4f} positive (+20)")
        else:
            reasons.append(f"MACD hist {h:.4f} negative (0)")

    if stoch_k is not None:
        k = float(stoch_k)
        if 40 <= k <= 80:
            pts += 15
            reasons.append(f"Stochastic K {k:.0f} healthy zone 40–80 (+15)")
        elif 20 <= k < 40:
            pts += 8
            reasons.append(f"Stochastic K {k:.0f} recovering 20–40 (+8)")
        elif k < 20:
            pts += 5
            reasons.append(f"Stochastic K {k:.0f} oversold — bounce potential (+5)")

    return _cap(pts), reasons


def compute_composite(
    close: float,
    ema_20: float | None,
    sma_50: float | None,
    sma_200: float | None,
    ema_21: float | None,
    adx_14: float | None,
    plus_di: float | None,
    minus_di: float | None,
    volume_breakout_ratio: float | None,
    obv_trend: str | None,
    delivery_pct: float | None,
    rs_score_1m: float | None,
    ret_1w: float | None,
    ret_4w: float | None,
    rsi_14: float | None,
    macd_histogram: float | None,
    macd_histogram_prev: float | None = None,
    stoch_k: float | None = None,
    supertrend_dir: str | None = None,
) -> CompositeResult:
    """Compute the full 4-component composite score and derive 5-tier bias."""
    trend, t_reasons = score_trend(close, ema_20, sma_50, sma_200, ema_21, adx_14, plus_di, minus_di, supertrend_dir)
    volume, v_reasons = score_volume(volume_breakout_ratio, obv_trend, delivery_pct)
    rs, r_reasons = score_rs(rs_score_1m, ret_1w, ret_4w)
    momentum, m_reasons = score_momentum(rsi_14, macd_histogram, macd_histogram_prev, stoch_k)

    composite = round(0.40 * trend + 0.25 * volume + 0.20 * rs + 0.15 * momentum, 1)

    if composite >= 72:
        bias = "VERY_BULLISH"
    elif composite >= 52:
        bias = "BULLISH"
    elif composite >= 35:
        bias = "NEUTRAL"
    elif composite >= 18:
        bias = "BEARISH"
    else:
        bias = "VERY_BEARISH"

    all_reasons = (
        [f"[TREND {trend:.0f}]"] + t_reasons +
        [f"[VOLUME {volume:.0f}]"] + v_reasons +
        [f"[RS {rs:.0f}]"] + r_reasons +
        [f"[MOMENTUM {momentum:.0f}]"] + m_reasons +
        [f"COMPOSITE={composite:.1f} → {bias}"]
    )

    return CompositeResult(
        bias=bias,
        composite_score=composite,
        trend_score=round(trend, 1),
        volume_score=round(volume, 1),
        rs_score=round(rs, 1),
        momentum_score=round(momentum, 1),
        reasons=all_reasons,
    )
