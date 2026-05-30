# src/stocks/services/quant/planner.py
from typing import Dict, Any, List

class TradePlannerService:
    """Calculates deterministic, ATR-based entry, stop loss, and target values.
    
    Replaces the previous Trade Planner LLM agent.
    """

    def __init__(self, risk_per_trade_inr: float = 5000.0):
        self.risk_per_trade = risk_per_trade_inr

    def calculate_trade_plan(
        self, symbol: str, latest_price: float, atr_14: float, support: float, resistance: float
    ) -> Dict[str, Any]:
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
        
        target_1 = round(mid_entry + (1.5 * atr_14), 2)
        target_2 = round(mid_entry + (3.0 * atr_14), 2)
        
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
                "risk_reward_ratio": risk_reward
            },
            "tactics": (
                f"Enter long within the key accumulation channel {entry_zone}. "
                f"A hard stop-loss is placed at {stop_loss:.2f} based on 1.5x ATR protection below structural support. "
                f"Take profit at target channels {target_1:.2f} and {target_2:.2f} respectively."
            )
        }
