"""Query-time corporate-action back-adjustment.

Raw/unadjusted OHLCV bars are the immutable system of record. Adjustments are applied
on read so a split never forces rewriting historical Parquet partitions (see
Doc/VajraStocks_V2.0_PRD_BRD_Architecture.md §18).

Back-adjustment convention (CRSP-style, "latest stays raw"):
    factor(d) = product of split ratios for all splits with ex-date STRICTLY AFTER d
    adjusted_price(d)  = raw_price(d)  / factor(d)
    adjusted_volume(d) = raw_volume(d) * factor(d)

So the most-recent bars are unchanged and the series is continuous backwards.

Dividends use the standard back-adjustment factor ``(1 - dividend / prior_close)`` where
``prior_close`` is the close of the last bar strictly before the ex-date; dividends scale
prices only, not volume. Splits scale both (price /= ratio, volume *= ratio).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from typing import Any

import pandas as pd

PRICE_COLUMNS = ("open", "high", "low", "close", "adj_close")
SPLIT = "SPLIT"
DIVIDEND = "DIVIDEND"


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


def _event_multipliers(
    bars: pd.DataFrame,
    norm_dates: pd.Series,
    actions: Sequence[dict[str, Any]],
    *,
    splits: bool,
    dividends: bool,
) -> list[tuple[dt.date, float, float]]:
    """Return ``(ex_date, price_multiplier, volume_multiplier)`` for each applicable event.

    Split:    price *= 1/ratio, volume *= ratio.
    Dividend: price *= (1 - div / prior_close), volume *= 1. A dividend with no prior bar
              (or a non-positive resulting factor) is skipped.
    """
    events: list[tuple[dt.date, float, float]] = []

    prior_close_lookup: list[tuple[dt.date, float]] | None = None
    if dividends and "close" in bars.columns:
        prior_close_lookup = sorted(
            zip(norm_dates.tolist(), bars["close"].tolist(), strict=True),
            key=lambda x: x[0],
        )

    def _prior_close(ex_date: dt.date) -> float | None:
        if not prior_close_lookup:
            return None
        prior = [c for (d, c) in prior_close_lookup if d < ex_date]
        return float(prior[-1]) if prior else None

    for a in actions:
        action_type = str(a.get("action_type", "")).upper()
        value = float(a.get("value", 0))
        ex_date = _as_date(a["action_date"])

        if splits and action_type == SPLIT and value > 0:
            events.append((ex_date, 1.0 / value, value))
        elif dividends and action_type == DIVIDEND and value > 0:
            prior_close = _prior_close(ex_date)
            if prior_close and prior_close > 0:
                factor = 1.0 - value / prior_close
                if factor > 0:
                    events.append((ex_date, factor, 1.0))

    return events


def apply_adjustments(
    bars: pd.DataFrame,
    actions: Sequence[dict[str, Any]],
    *,
    splits: bool = True,
    dividends: bool = True,
) -> pd.DataFrame:
    """Return a copy of ``bars`` back-adjusted for the requested corporate-action types.

    ``bars`` must contain a ``trading_date`` column. Present price columns and ``volume``
    are adjusted; other columns pass through untouched. The cumulative multiplier for a
    bar is the product of the per-event multipliers whose ex-date is strictly after the
    bar's date, so the most-recent bars stay raw.
    """
    out = bars.copy()
    if out.empty or not actions:
        return out

    norm_dates = out["trading_date"].map(_as_date)
    events = _event_multipliers(out, norm_dates, actions, splits=splits, dividends=dividends)
    if not events:
        return out

    price_mult = norm_dates.map(
        lambda d: _prod(pm for (ed, pm, _vm) in events if ed > d)
    )
    vol_mult = norm_dates.map(
        lambda d: _prod(vm for (ed, _pm, vm) in events if ed > d)
    )

    for col in PRICE_COLUMNS:
        if col in out.columns:
            out[col] = out[col] * price_mult

    if "volume" in out.columns:
        adjusted_volume = out["volume"] * vol_mult
        if pd.api.types.is_integer_dtype(bars["volume"]):
            out["volume"] = adjusted_volume.round().astype(bars["volume"].dtype)
        else:
            out["volume"] = adjusted_volume

    return out


def apply_split_adjustments(
    bars: pd.DataFrame,
    actions: Sequence[dict[str, Any]],
) -> pd.DataFrame:
    """Back-adjust ``bars`` for splits only (dividends ignored). See ``apply_adjustments``."""
    return apply_adjustments(bars, actions, splits=True, dividends=False)


def _prod(values) -> float:
    result = 1.0
    for v in values:
        result *= v
    return result
