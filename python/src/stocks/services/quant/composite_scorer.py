"""Composite scoring engine — 6-component weighted model.

Scores each symbol across 6 components (0–100 each) and derives a
5-tier bias from the weighted composite.

Weights:
  Trend Score     30%   (EMA alignment, ADX, Supertrend)
  CMF Score       20%   (Chaikin Money Flow — institutional accumulation/distribution)
  RS Score        15%   (Relative Strength vs Nifty, rolling returns)
  Momentum Score  15%   (MACD histogram, Stochastic RSI crossover)
  Volume Score    10%   (Relative Volume, OBV, Delivery %)
  Breakout Score  10%   (ADX, Supertrend, NR7/Inside Bar, Renko, Line Break)

Bias thresholds (composite 0–100):
  VERY_BULLISH  ≥ 75
  BULLISH       ≥ 58
  NEUTRAL       ≥ 40
  BEARISH       ≥ 22
  VERY_BEARISH  < 22
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
    cmf_score: float             # 0–100
    breakout_score: float        # 0–100
    reasons: list[str]


def _cap(v: float) -> float:
    return max(0.0, min(100.0, v))


def score_trend(
    close: float,
    ema_20: float | None,
    sma_50: float | None,
    sma_200: float | None,
    ema_21: float | None,
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
      EMA20 > EMA50 only       8 pts
      EMA50 > EMA200 only      4 pts
      ADX ≥ 40               10 pts
      ADX ≥ 25                5 pts
      DI+ > DI-               5 pts  (when ADX strong)
      Supertrend UP            5 pts
      Supertrend DOWN         -5 pts
    """
    pts = 0.0
    reasons: list[str] = []
    ema20 = ema_20 if ema_20 is not None else ema_21

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

    if adx_14 is not None:
        if adx_14 >= 40:
            pts += 10
            reasons.append(f"ADX {adx_14:.0f} ≥ 40 strong trend (+10)")
        elif adx_14 >= 25:
            pts += 5
            reasons.append(f"ADX {adx_14:.0f} ≥ 25 developing trend (+5)")
        else:
            reasons.append(f"ADX {adx_14:.0f} < 25 weak trend (0)")

        if adx_14 >= 25 and plus_di is not None and minus_di is not None:
            if plus_di > minus_di:
                pts += 5
                reasons.append(f"DI+ {plus_di:.0f} > DI- {minus_di:.0f} (+5)")

    if supertrend_dir == "UP":
        pts += 5
        reasons.append("Supertrend UP — above ATR stop (+5)")
    elif supertrend_dir == "DOWN":
        pts = max(0.0, pts - 5)
        reasons.append("Supertrend DOWN — below ATR stop (-5)")

    return _cap(pts), reasons


def score_cmf(
    cmf_20: float | None,
    cmf_20_prev: float | None = None,
) -> tuple[float, list[str]]:
    """
    Points (base):
      CMF > +0.20   100 pts  (Strong Accumulation)
      CMF +0.10–0.20  80 pts
      CMF 0–+0.10     60 pts
      CMF -0.05–0     40 pts  (Neutral)
      CMF -0.20–-0.05 20 pts  (Distribution)
      CMF < -0.20      0 pts  (Strong Distribution)

    Bonuses / penalties (applied on top, capped at 0–100):
      CMF crossed above zero today        +15
      CMF rising session-on-session        +8
      CMF falling while positive           -8
    """
    if cmf_20 is None:
        return 40.0, ["CMF: data unavailable — neutral (+40)"]

    cmf = float(cmf_20)
    reasons: list[str] = []

    if cmf > 0.20:
        pts = 100.0
        reasons.append(f"CMF {cmf:.3f} > +0.20 — Strong Accumulation (100)")
    elif cmf > 0.10:
        pts = 80.0
        reasons.append(f"CMF {cmf:.3f} +0.10 to +0.20 — Accumulation (80)")
    elif cmf > 0.0:
        pts = 60.0
        reasons.append(f"CMF {cmf:.3f} 0 to +0.10 — Mild Accumulation (60)")
    elif cmf > -0.05:
        pts = 40.0
        reasons.append(f"CMF {cmf:.3f} near zero — Neutral (40)")
    elif cmf > -0.20:
        pts = 20.0
        reasons.append(f"CMF {cmf:.3f} -0.20 to 0 — Distribution (20)")
    else:
        pts = 0.0
        reasons.append(f"CMF {cmf:.3f} < -0.20 — Strong Distribution (0)")

    if cmf_20_prev is not None:
        prev = float(cmf_20_prev)
        if cmf > 0 and prev <= 0:
            pts = min(100.0, pts + 15.0)
            reasons.append(f"CMF crossed above zero from {prev:.3f} (+15 bonus)")
        elif cmf > prev:
            pts = min(100.0, pts + 8.0)
            reasons.append(f"CMF rising {prev:.3f} → {cmf:.3f} (+8 bonus)")
        elif cmf < prev and cmf > 0:
            pts = max(0.0, pts - 8.0)
            reasons.append(f"CMF falling {prev:.3f} → {cmf:.3f} while positive (-8)")

    return _cap(pts), reasons


def score_volume(
    volume_breakout_ratio: float | None,
    obv_trend: str | None,
    delivery_pct: float | None = None,
) -> tuple[float, list[str]]:
    """
    Points:
      OBV trend UP            35 pts  (neutral=17 when absent)
      Vol breakout ≥ 2x       35 pts  (neutral=17 when absent)
      Delivery % ≥ 60%        30 pts  (neutral=15 when absent)
      Delivery % ≥ 40%        15 pts
    """
    pts = 0.0
    reasons: list[str] = []

    if obv_trend == "UP":
        pts += 35
        reasons.append("OBV trend UP (+35)")
    elif obv_trend == "DOWN":
        reasons.append("OBV trend DOWN (0)")
    else:
        pts += 17
        reasons.append("OBV trend: insufficient data — neutral (+17)")

    if volume_breakout_ratio is not None:
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
        pts += 17
        reasons.append("Volume breakout ratio: insufficient data — neutral (+17)")

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
      RS vs Nifty > 1.5       40 pts
      RS vs Nifty > 1.2       30 pts
      RS vs Nifty > 1.0       20 pts
      RS vs Nifty 0.8–1.0     10 pts
      ret_4w > 8%             30 pts
      ret_4w > 3%             20 pts
      ret_4w > 0%             10 pts
      ret_1w > 0%             10 pts
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
    macd_histogram: float | None,
    macd_histogram_prev: float | None = None,
    stochrsi_k: float | None = None,
    stochrsi_d: float | None = None,
    stochrsi_bullish_xover_days_ago: int | None = None,
    stochrsi_bearish_xover_days_ago: int | None = None,
    # Deprecated params kept for backward compatibility — not used
    rsi_14: float | None = None,
    stoch_k: float | None = None,
) -> tuple[float, list[str]]:
    """
    MACD histogram (50 pts max) + StochRSI (50 pts max) = 100 pts.

    MACD:
      hist > 0 and growing    50 pts
      hist > 0 flat           35 pts
      hist < 0 but improving  15 pts
      hist < 0                 0 pts
      missing data            20 pts (neutral)

    StochRSI:
      Bullish xover from oversold (<25) within 3 days   50 pts
      Bullish xover any level within 3 days             40 pts
      %K > %D, %K between 50–80                        35 pts
      %K 30–50 (mid range)                             25 pts
      %K > 80 (overbought — strong momentum)            20 pts
      %K 20–30 (near oversold)                         15 pts
      %K < 20 (oversold — reversal potential)          20 pts
      Bearish xover from overbought within 3 days        5 pts
      Bearish xover any level within 3 days             10 pts
      missing data                                      20 pts (neutral)
    """
    pts = 0.0
    reasons: list[str] = []

    # MACD component (50 pts max)
    if macd_histogram is not None:
        h = float(macd_histogram)
        if h > 0:
            growing = macd_histogram_prev is not None and h > float(macd_histogram_prev)
            if growing:
                pts += 50
                reasons.append(f"MACD hist {h:.4f} positive and growing (+50)")
            else:
                pts += 35
                reasons.append(f"MACD hist {h:.4f} positive (+35)")
        else:
            improving = macd_histogram_prev is not None and h > float(macd_histogram_prev)
            if improving:
                pts += 15
                reasons.append(f"MACD hist {h:.4f} negative but improving (+15)")
            else:
                reasons.append(f"MACD hist {h:.4f} negative (0)")
    else:
        pts += 20
        reasons.append("MACD: data unavailable — neutral (+20)")

    # StochRSI component (50 pts max)
    if stochrsi_k is None:
        pts += 20
        reasons.append("StochRSI: data unavailable — neutral (+20)")
    else:
        k = float(stochrsi_k)
        bullish_recent = stochrsi_bullish_xover_days_ago is not None and stochrsi_bullish_xover_days_ago <= 3
        bearish_recent = stochrsi_bearish_xover_days_ago is not None and stochrsi_bearish_xover_days_ago <= 3
        was_oversold = stochrsi_d is not None and float(stochrsi_d) <= 25

        if bullish_recent and (k <= 30 or was_oversold):
            pts += 50
            reasons.append(f"StochRSI bullish xover from oversold (day {stochrsi_bullish_xover_days_ago}) (+50)")
        elif bullish_recent:
            pts += 40
            reasons.append(f"StochRSI bullish xover (day {stochrsi_bullish_xover_days_ago}) (+40)")
        elif bearish_recent and k >= 75:
            pts += 5
            reasons.append(f"StochRSI bearish xover from overbought (day {stochrsi_bearish_xover_days_ago}) (+5)")
        elif bearish_recent:
            pts += 10
            reasons.append(f"StochRSI bearish xover (day {stochrsi_bearish_xover_days_ago}) (+10)")
        elif k >= 80:
            pts += 20
            reasons.append(f"StochRSI {k:.0f} overbought — strong momentum (+20)")
        elif k >= 50 and stochrsi_d is not None and k > float(stochrsi_d):
            pts += 35
            reasons.append(f"StochRSI {k:.0f} bullish territory K > D (+35)")
        elif k >= 30:
            pts += 25
            reasons.append(f"StochRSI {k:.0f} mid range (+25)")
        elif k >= 20:
            pts += 15
            reasons.append(f"StochRSI {k:.0f} near oversold (+15)")
        else:
            pts += 20
            reasons.append(f"StochRSI {k:.0f} oversold — reversal potential (+20)")

    return _cap(pts), reasons


def score_breakout(
    supertrend_dir: str | None = None,
    adx_14: float | None = None,
    plus_di: float | None = None,
    minus_di: float | None = None,
    is_nr7: bool | None = None,
    is_inside_bar: bool | None = None,
    is_gap_up: bool | None = None,
    renko_dir: str | None = None,
    line_break_dir: str | None = None,
) -> tuple[float, list[str]]:
    """
    Points (starting from 0; neutral=40 when no data at all):
      Supertrend UP      +30
      ADX >= 30          +25  (strong trend)
      ADX >= 20          +15  (developing)
      NR7 pattern        +20  (range compression)
      Inside Bar         +15  (compression)
      Gap Up             +10
      Renko UP           +15
      Line Break UP      +10
      Supertrend DOWN    -20
      Strong bearish ADX -15  (ADX>=30 with DI- > DI+)
      Renko DOWN         -10
    """
    pts = 0.0
    reasons: list[str] = []
    has_data = False

    if supertrend_dir == "UP":
        pts += 30
        has_data = True
        reasons.append("Supertrend UP (+30)")
    elif supertrend_dir == "DOWN":
        pts -= 20
        has_data = True
        reasons.append("Supertrend DOWN (-20)")

    if adx_14 is not None:
        has_data = True
        adx = float(adx_14)
        if adx >= 30:
            pts += 25
            reasons.append(f"ADX {adx:.0f} >= 30 strong trend (+25)")
            if plus_di is not None and minus_di is not None and float(minus_di) > float(plus_di):
                pts -= 15
                reasons.append(f"DI- {float(minus_di):.0f} > DI+ {float(plus_di):.0f} bearish direction (-15)")
        elif adx >= 20:
            pts += 15
            reasons.append(f"ADX {adx:.0f} >= 20 developing trend (+15)")
        else:
            reasons.append(f"ADX {adx:.0f} < 20 weak (0)")

    if is_nr7:
        pts += 20
        has_data = True
        reasons.append("NR7 — range compression (+20)")

    if is_inside_bar:
        pts += 15
        has_data = True
        reasons.append("Inside Bar — compression (+15)")

    if is_gap_up:
        pts += 10
        has_data = True
        reasons.append("Gap Up (+10)")

    if renko_dir == "UP":
        pts += 15
        has_data = True
        reasons.append("Renko UP (+15)")
    elif renko_dir == "DOWN":
        pts -= 10
        has_data = True
        reasons.append("Renko DOWN (-10)")

    if line_break_dir == "UP":
        pts += 10
        has_data = True
        reasons.append("Line Break UP (+10)")

    if not has_data:
        return 40.0, ["Breakout: no pattern data — neutral (+40)"]

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
    volume_breakout_ratio: float | None = None,
    obv_trend: str | None = None,
    delivery_pct: float | None = None,
    rs_score_1m: float | None = None,
    ret_1w: float | None = None,
    ret_4w: float | None = None,
    macd_histogram: float | None = None,
    macd_histogram_prev: float | None = None,
    stochrsi_k: float | None = None,
    stochrsi_d: float | None = None,
    stochrsi_bullish_xover_days_ago: int | None = None,
    stochrsi_bearish_xover_days_ago: int | None = None,
    cmf_20: float | None = None,
    cmf_20_prev: float | None = None,
    supertrend_dir: str | None = None,
    is_nr7: bool | None = None,
    is_inside_bar: bool | None = None,
    is_gap_up: bool | None = None,
    renko_dir: str | None = None,
    line_break_dir: str | None = None,
    # Deprecated — ignored, kept for backward compatibility
    rsi_14: float | None = None,
    stoch_k: float | None = None,
) -> CompositeResult:
    """Compute the full 6-component composite score and derive 5-tier bias.

    Weights: Trend 30% | CMF 20% | RS 15% | Momentum 15% | Volume 10% | Breakout 10%
    """
    trend, t_reasons = score_trend(close, ema_20, sma_50, sma_200, ema_21, adx_14, plus_di, minus_di, supertrend_dir)
    cmf, c_reasons = score_cmf(cmf_20, cmf_20_prev)
    rs, r_reasons = score_rs(rs_score_1m, ret_1w, ret_4w)
    momentum, m_reasons = score_momentum(
        macd_histogram, macd_histogram_prev,
        stochrsi_k, stochrsi_d,
        stochrsi_bullish_xover_days_ago, stochrsi_bearish_xover_days_ago,
    )
    volume, v_reasons = score_volume(volume_breakout_ratio, obv_trend, delivery_pct)
    breakout, b_reasons = score_breakout(
        supertrend_dir, adx_14, plus_di, minus_di,
        is_nr7, is_inside_bar, is_gap_up, renko_dir, line_break_dir,
    )

    composite = round(
        0.30 * trend +
        0.20 * cmf +
        0.15 * rs +
        0.15 * momentum +
        0.10 * volume +
        0.10 * breakout,
        1,
    )

    if composite >= 75:
        bias = "VERY_BULLISH"
    elif composite >= 58:
        bias = "BULLISH"
    elif composite >= 40:
        bias = "NEUTRAL"
    elif composite >= 22:
        bias = "BEARISH"
    else:
        bias = "VERY_BEARISH"

    all_reasons = (
        [f"[TREND {trend:.0f}]"] + t_reasons +
        [f"[CMF {cmf:.0f}]"] + c_reasons +
        [f"[RS {rs:.0f}]"] + r_reasons +
        [f"[MOMENTUM {momentum:.0f}]"] + m_reasons +
        [f"[VOLUME {volume:.0f}]"] + v_reasons +
        [f"[BREAKOUT {breakout:.0f}]"] + b_reasons +
        [f"COMPOSITE={composite:.1f} → {bias}"]
    )

    return CompositeResult(
        bias=bias,
        composite_score=composite,
        trend_score=round(trend, 1),
        volume_score=round(volume, 1),
        rs_score=round(rs, 1),
        momentum_score=round(momentum, 1),
        cmf_score=round(cmf, 1),
        breakout_score=round(breakout, 1),
        reasons=all_reasons,
    )
