import datetime
from typing import List, Dict, Any, Tuple
from loguru import logger
from stocks.config import Config

class ValidationService:
    """Service to validate and clean incoming daily historical stock pricing records."""

    def __init__(self, config: Config):
        self.config = config
        self.pct_change_limit = config.validation.max_price_pct_change_limit

    def validate_prices(
        self, ticker: str, prices: List[Dict[str, Any]], actions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Validates a list of price records for consistency and returns a list of clean, validated records."""
        if not prices:
            return []

        # Sort prices chronologically to verify day-on-day anomalies
        sorted_prices = sorted(prices, key=lambda x: x["trading_date"])
        
        # Build corporate actions lookup by date
        action_dates = {a["action_date"]: a for a in actions}
        
        validated_prices = []
        
        for i, row in enumerate(sorted_prices):
            t_date = row["trading_date"]
            
            try:
                # 1. Null / Type Checks
                o, h, l, c, ac = row["open"], row["high"], row["low"], row["close"], row["adj_close"]
                v = row["volume"]
                
                if any(x is None for x in [o, h, l, c, ac, v]):
                    logger.warning(f"[{ticker}] Row on {t_date} skipped: Contains null pricing attributes.")
                    continue

                # 2. Positivity check
                if any(x < 0.0 for x in [o, h, l, c, ac]):
                    logger.warning(f"[{ticker}] Row on {t_date} skipped: Price cannot be negative.")
                    continue
                if v < 0:
                    logger.warning(f"[{ticker}] Row on {t_date} skipped: Volume cannot be negative.")
                    continue

                # 3. Logical Bounds Check
                if not (l <= o <= h):
                    logger.warning(f"[{ticker}] Row on {t_date} skipped: Logical inconsistency (Open {o} out of [Low {l}, High {h}] range).")
                    continue
                if not (l <= c <= h):
                    logger.warning(f"[{ticker}] Row on {t_date} skipped: Logical inconsistency (Close {c} out of [Low {l}, High {h}] range).")
                    continue
                if l > h:
                    logger.warning(f"[{ticker}] Row on {t_date} skipped: Low {l} cannot be greater than High {h}.")
                    continue

                # 4. Day-on-Day price spike anomaly check (if not first row)
                if i > 0:
                    prev_close = sorted_prices[i - 1]["close"]
                    if prev_close > 0.0:
                        pct_change = abs(c - prev_close) / prev_close
                        if pct_change > self.pct_change_limit:
                            # Verify if there was an associated corporate action on this date
                            has_action = t_date in action_dates
                            if has_action:
                                action_type = action_dates[t_date]["action_type"]
                                logger.info(
                                    f"[{ticker}] Large price shift of {pct_change:.1%} on {t_date} "
                                    f"justified by concurrent corporate action ({action_type})."
                                )
                            else:
                                logger.warning(
                                    f"[{ticker}] Price spike warning: {prev_close:.2f} -> {c:.2f} "
                                    f"({pct_change:.1%} shift) on {t_date} with no corporate actions recorded."
                                )

                # Row passed all validation filters
                validated_prices.append(row)
                
            except KeyError as e:
                logger.error(f"[{ticker}] Skipped row on {t_date}: Missing required key {e}")
            except Exception as e:
                logger.error(f"[{ticker}] Validation error on row {t_date}: {e}")

        logger.info(f"[{ticker}] Validation complete. {len(validated_prices)}/{len(prices)} rows passed validation checks.")
        return validated_prices
