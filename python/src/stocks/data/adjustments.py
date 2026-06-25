"""Query-time corporate-action back-adjustment.

Raw/unadjusted OHLCV bars are the immutable system of record. Adjustments are applied
on read so a split never forces rewriting historical Parquet partitions (see
Doc/VajraStocks_V2.0_PRD_BRD_Architecture.md §18).

Back-adjustment convention (CRSP-style, "latest stays raw"):
    factor(d) = product of split ratios for all splits with ex-date STRICTLY AFTER d
    adjusted_price(d)  = raw_price(d)  / factor(d)
    adjusted_volume(d) = raw_volume(d) * factor(d)

So the most-recent bars are unchanged and the series is continuous backwards.

Dividends are intentionally out of scope for this first slice; the API leaves room to
add a dividend factor alongside the split factor in a later increment.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from typing import Any

import pandas as pd

PRICE_COLUMNS = ("open", "high", "low", "close", "adj_close")
SPLIT = "SPLIT"


def _as_date(value: Any) -> dt.date:
    """Coerce a date / datetime / ISO-string into a ``datetime.date``."""
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        return dt.date.fromisoformat(value[:10])
    # pandas Timestamp and similar
    return pd.Timestamp(value).date()


def split_adjustment_factors(
    dates: Sequence[Any],
    actions: Sequence[dict[str, Any]],
) -> dict[dt.date, float]:
    """Return the back-adjustment factor for each date.

    The factor is the product of every split ratio whose ex-date is strictly after the
    date. Dates on/after the most recent split get a factor of ``1.0``.
    """
    splits = sorted(
        (
            (_as_date(a["action_date"]), float(a["value"]))
            for a in actions
            if str(a.get("action_type", "")).upper() == SPLIT and float(a.get("value", 0)) > 0
        ),
        key=lambda x: x[0],
    )

    factors: dict[dt.date, float] = {}
    for raw_date in dates:
        d = _as_date(raw_date)
        factor = 1.0
        for ex_date, ratio in splits:
            if ex_date > d:
                factor *= ratio
        factors[d] = factor
    return factors


def apply_split_adjustments(
    bars: pd.DataFrame,
    actions: Sequence[dict[str, Any]],
) -> pd.DataFrame:
    """Return a copy of ``bars`` with OHLC(+adj_close) and volume back-adjusted for splits.

    ``bars`` must contain a ``trading_date`` column. Any of the price columns and
    ``volume`` that are present get adjusted; all other columns pass through untouched.
    An empty action list (or no splits) returns an unmodified copy.
    """
    out = bars.copy()
    if out.empty or not actions:
        return out

    factors = split_adjustment_factors(out["trading_date"].tolist(), actions)
    if all(f == 1.0 for f in factors.values()):
        return out

    factor_series = out["trading_date"].map(lambda d: factors[_as_date(d)])

    for col in PRICE_COLUMNS:
        if col in out.columns:
            out[col] = out[col] / factor_series

    if "volume" in out.columns:
        adjusted_volume = out["volume"] * factor_series
        # Volume is integral; preserve dtype where the input was integer.
        if pd.api.types.is_integer_dtype(bars["volume"]):
            out["volume"] = adjusted_volume.round().astype(bars["volume"].dtype)
        else:
            out["volume"] = adjusted_volume

    return out
