"""Screener setup presets (V2.0 spec M4).

A small library of named, tradable setups expressed as pure predicates over a snapshot row
(dict) — the "8-10 setups I actually trade" instead of 40 sliders. Each predicate is robust
to missing fields (treats absent/None as not-matching). Snapshots already carry every
indicator, so presets are fast (no price-history scan).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

Predicate = Callable[[Mapping[str, Any]], bool]
_PRESETS: dict[str, tuple[Predicate, str]] = {}


def register_preset(name: str, description: str) -> Callable[[Predicate], Predicate]:
    def deco(fn: Predicate) -> Predicate:
        _PRESETS[name] = (fn, description)
        return fn
    return deco


def list_presets() -> list[dict[str, str]]:
    return [{"name": n, "description": d} for n, (_fn, d) in _PRESETS.items()]


def get_preset(name: str) -> Predicate:
    if name not in _PRESETS:
        raise ValueError(f"Unknown preset '{name}'. Known: {', '.join(_PRESETS)}")
    return _PRESETS[name][0]


def passes(name: str, row: Mapping[str, Any]) -> bool:
    return get_preset(name)(row)


# ── field accessors (robust to missing / Decimal / case) ─────────────────────
def _num(row: Mapping[str, Any], key: str) -> float | None:
    v = row.get(key)
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _str(row: Mapping[str, Any], key: str) -> str:
    v = row.get(key)
    return str(v).upper() if v is not None else ""


def _above_200(row: Mapping[str, Any]) -> bool:
    return _str(row, "sma_200_cross_direction") == "ABOVE"


def _between(v: float | None, lo: float, hi: float) -> bool:
    return v is not None and lo <= v <= hi


# ── presets ──────────────────────────────────────────────────────────────────
@register_preset("stage2_uptrend", "Weinstein Stage 2 advance, above a rising 200-DMA")
def _stage2(row: Mapping[str, Any]) -> bool:
    return _num(row, "weinstein_stage") == 2 and _above_200(row)


@register_preset("pullback_20ema", "Uptrend pullback — above 200-DMA with RSI cooling to 40–55")
def _pullback(row: Mapping[str, Any]) -> bool:
    return _above_200(row) and _between(_num(row, "rsi_14"), 40, 55)


@register_preset("nr7_coil", "NR7 volatility contraction (narrowest range in 7 bars)")
def _nr7(row: Mapping[str, Any]) -> bool:
    return bool(row.get("is_nr7"))


@register_preset("bb_squeeze", "Bollinger Band squeeze — volatility compressed, expansion pending")
def _squeeze(row: Mapping[str, Any]) -> bool:
    return bool(row.get("is_bb_squeeze"))


@register_preset("momentum_leader", "Relative-strength leader in an uptrend (RS≥70, 4-week return positive)")
def _momentum(row: Mapping[str, Any]) -> bool:
    rs = _num(row, "rs_score_val")
    return rs is not None and rs >= 70 and (_num(row, "ret_4w") or 0) > 0 and _above_200(row)


@register_preset("oversold_reversal", "Oversold bounce — RSI<35 with a fresh StochRSI bullish cross")
def _oversold(row: Mapping[str, Any]) -> bool:
    rsi = _num(row, "rsi_14")
    days = _num(row, "stochrsi_bullish_xover_days_ago")
    return rsi is not None and rsi < 35 and days is not None and days <= 2


@register_preset("macd_fresh_bull", "Fresh MACD bullish crossover (within 2 bars)")
def _macd_bull(row: Mapping[str, Any]) -> bool:
    days = _num(row, "days_since_macd_bull")
    return _str(row, "macd_trend") in ("BULLISH", "UP") and days is not None and days <= 2
