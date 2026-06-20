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
        rsi_14: float | None = None,      # kept for API compat, ignored in scorer
        neutral_band_pct: float = 2.0,    # kept for API compat, unused
        adx_14: float | None = None,
        plus_di: float | None = None,
        minus_di: float | None = None,
        ema_20: float | None = None,
        volume_breakout_ratio: float | None = None,
        obv_trend: str | None = None,
        rs_score_1m: float | None = None,
        ret_1w: float | None = None,
        ret_4w: float | None = None,
        macd_histogram_prev: float | None = None,
        stoch_k: float | None = None,     # kept for API compat, ignored in scorer
        stochrsi_k: float | None = None,
        stochrsi_d: float | None = None,
        stochrsi_bullish_xover_days_ago: int | None = None,
        stochrsi_bearish_xover_days_ago: int | None = None,
        cmf_20: float | None = None,
        cmf_20_prev: float | None = None,
        supertrend_dir: str | None = None,
    ) -> tuple[str, list[str]]:
        """6-component bias scorer.

        Returns (bias, reasons) where bias in
        {VERY_BULLISH, BULLISH, NEUTRAL, BEARISH, VERY_BEARISH}.

        Delegates to CompositeScorer (Trend 30%, CMF 20%, RS 15%,
        Momentum 15%, Volume 10%, Breakout 10%).
        """
        from stocks.services.quant.composite_scorer import compute_composite

        if close is None or close <= 0:
            return "NEUTRAL", ["Insufficient data — no close price"]

        result = compute_composite(
            close=close,
            ema_20=ema_20,
            sma_50=sma_50,
            sma_200=sma_200,
            ema_21=ema_21,
            adx_14=adx_14,
            plus_di=plus_di,
            minus_di=minus_di,
            volume_breakout_ratio=volume_breakout_ratio,
            obv_trend=obv_trend,
            delivery_pct=None,
            rs_score_1m=rs_score_1m,
            ret_1w=ret_1w,
            ret_4w=ret_4w,
            macd_histogram=macd_histogram,
            macd_histogram_prev=macd_histogram_prev,
            stochrsi_k=stochrsi_k,
            stochrsi_d=stochrsi_d,
            stochrsi_bullish_xover_days_ago=stochrsi_bullish_xover_days_ago,
            stochrsi_bearish_xover_days_ago=stochrsi_bearish_xover_days_ago,
            cmf_20=cmf_20,
            cmf_20_prev=cmf_20_prev,
            supertrend_dir=supertrend_dir,
        )
        return result.bias, result.reasons

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

        # A trade is only worth taking if reward >= risk (R/R >= 1.0)
        if latest_price < support:
            action = "HOLD"
        elif risk_reward < 1.0:
            action = "AVOID"
        else:
            action = "BUY"

        return {
            "symbol": symbol,
            "setup_name": "Deterministic ATR Breakout Plan",
            "execution": {
                "action": action,
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
