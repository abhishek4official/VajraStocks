# src/stocks/services/quant/planner.py
from typing import Any


class TradePlannerService:
    """Calculates deterministic, ATR-based entry, stop loss, and target values.

    Replaces the previous Trade Planner LLM agent.
    """

    def __init__(self, risk_per_trade_inr: float = 5000.0):
        self.risk_per_trade = risk_per_trade_inr

    @staticmethod
    def compute_bias(
        close: float | None,
        sma_50: float | None,
        sma_200: float | None,
        ema_21: float | None,
        macd_histogram: float | None,
        rsi_14: float | None,
        neutral_band_pct: float = 2.0,
        adx_14: float | None = None,
        plus_di: float | None = None,
        minus_di: float | None = None,
    ) -> tuple[str, list[str]]:
        """Multi-factor directional bias with a NEUTRAL deadband around SMA200.

        Returns (bias, reasons) where bias ∈ {VERY_BULLISH, BULLISH, NEUTRAL, BEARISH, VERY_BEARISH}.

        Confirmation factors (0–4):
          1. MACD histogram direction
          2. RSI zone (≥55 bullish / ≤45 bearish)
          3. EMA21 vs SMA50 cross
          4. ADX > 25 with DI alignment (only when adx_14, plus_di, minus_di are available)

        VERY_BULLISH / VERY_BEARISH requires trend out of band AND ≥3 confirms.
        BULLISH / BEARISH requires trend out of band AND ≥1 confirm.
        All other cases → NEUTRAL.
        """
        reasons: list[str] = []

        if close is None or sma_200 is None or sma_200 <= 0:
            return "NEUTRAL", ["Insufficient data — no SMA200 baseline"]

        band = sma_200 * (max(neutral_band_pct, 0.0) / 100.0)
        if close > sma_200 + band:
            trend = "UP"
            reasons.append(f"Price {close:.2f} > SMA200 {sma_200:.2f} by more than {neutral_band_pct:.1f}%")
        elif close < sma_200 - band:
            trend = "DOWN"
            reasons.append(f"Price {close:.2f} < SMA200 {sma_200:.2f} by more than {neutral_band_pct:.1f}%")
        else:
            trend = "FLAT"
            reasons.append(f"Price within ±{neutral_band_pct:.1f}% of SMA200 — neutral band")

        confirms_up = 0
        confirms_down = 0

        if macd_histogram is not None:
            if macd_histogram > 0:
                confirms_up += 1
                reasons.append("MACD histogram positive")
            elif macd_histogram < 0:
                confirms_down += 1
                reasons.append("MACD histogram negative")

        if rsi_14 is not None:
            if rsi_14 >= 55:
                confirms_up += 1
                reasons.append(f"RSI {rsi_14:.0f} ≥ 55")
            elif rsi_14 <= 45:
                confirms_down += 1
                reasons.append(f"RSI {rsi_14:.0f} ≤ 45")

        if ema_21 is not None and sma_50 is not None:
            if ema_21 > sma_50:
                confirms_up += 1
                reasons.append("EMA21 above SMA50")
            elif ema_21 < sma_50:
                confirms_down += 1
                reasons.append("EMA21 below SMA50")

        # 4th factor: ADX trend strength + directional alignment
        if adx_14 is not None and adx_14 > 25 and plus_di is not None and minus_di is not None:
            if plus_di > minus_di:
                confirms_up += 1
                reasons.append(f"ADX {adx_14:.0f} strong — DI+ {plus_di:.0f} > DI- {minus_di:.0f}")
            elif minus_di > plus_di:
                confirms_down += 1
                reasons.append(f"ADX {adx_14:.0f} strong — DI- {minus_di:.0f} > DI+ {plus_di:.0f}")

        if trend == "UP":
            if confirms_up >= 3:
                return "VERY_BULLISH", reasons
            if confirms_up >= 1:
                return "BULLISH", reasons
        elif trend == "DOWN":
            if confirms_down >= 3:
                return "VERY_BEARISH", reasons
            if confirms_down >= 1:
                return "BEARISH", reasons

        return "NEUTRAL", reasons

    def calculate_trade_plan(
        self, symbol: str, latest_price: float, atr_14: float, support: float, resistance: float
    ) -> dict[str, Any]:
        """Calculates precise trading targets using mathematical ATR calculations.

        Calculations:
        - Stop Loss: Support Pivot minus 1.5x ATR.
        - Entry Zone: Channel between latest closing price and SMA pivot support.
        - Target 1: Entry + 1.5x ATR.
        - Target 2: Entry + 3.0x ATR.
        - Position Size: Account Risk Budget divided by Stop Loss Distance.
        """
        # Ensure safe defaults if ATR or support bounds are empty
        if atr_14 is None or atr_14 <= 0:
            atr_14 = latest_price * 0.02
        if support is None or support <= 0:
            support = latest_price * 0.97
        if resistance is None or resistance <= 0:
            resistance = latest_price * 1.05

        stop_loss = support - (1.5 * atr_14)
        if stop_loss >= latest_price:
            stop_loss = latest_price - (2.0 * atr_14)

        entry_lower = round(latest_price * 0.99, 2)
        entry_upper = round(latest_price * 1.005, 2)
        entry_zone = f"{entry_lower:.2f} - {entry_upper:.2f}"

        mid_entry = (entry_lower + entry_upper) / 2.0

        if resistance > mid_entry:
            target_1 = round(resistance, 2)
        else:
            target_1 = round(mid_entry + (1.5 * atr_14), 2)

        target_2 = round(target_1 + (1.5 * atr_14), 2)

        # Calculate Position Sizing
        risk_distance = mid_entry - stop_loss
        position_shares = 0
        if risk_distance > 0:
            position_shares = int(self.risk_per_trade / risk_distance)

        risk_reward = round((target_1 - mid_entry) / risk_distance, 2) if risk_distance > 0 else 1.5

        return {
            "symbol": symbol,
            "setup_name": "Deterministic ATR Breakout Plan",
            "execution": {
                "action": "BUY" if latest_price >= support else "HOLD",
                "entry_zone": entry_zone,
                "stop_loss": round(stop_loss, 2),
                "targets": [target_1, target_2],
                "position_size_shares": position_shares if position_shares > 0 else 1,
                "risk_reward_ratio": risk_reward,
            },
            "tactics": (
                f"Enter long within the key accumulation channel {entry_zone}. "
                f"A hard stop-loss is placed at {stop_loss:.2f} based on 1.5x ATR protection below structural support. "
                f"Take profit at target channels {target_1:.2f} and {target_2:.2f} respectively."
            ),
        }
