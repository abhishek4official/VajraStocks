"""Portfolio-level risk calculations: correlation, beta, diversification score.

All functions are pure — they take price data as input and return dicts.
They degrade gracefully when price history is sparse.
"""

from __future__ import annotations

import datetime
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from stocks.db.models import DailyPrice, ScreeningSnapshot


_MIN_DAYS = 20  # minimum trading days required for correlation/beta to be meaningful


def _fetch_return_series(db: Session, symbol_ids: list[int], days: int = 90) -> dict[int, list[float]]:
    """Returns a dict of symbol_id → list of daily returns (oldest first).

    Fetches last `days` calendar days of closing prices for each symbol.
    """
    cutoff = datetime.date.today() - datetime.timedelta(days=days + 10)
    series: dict[int, list[float]] = {}

    for sid in symbol_ids:
        prices = db.scalars(
            select(DailyPrice)
            .where(DailyPrice.symbol_id == sid, DailyPrice.trading_date >= cutoff)
            .order_by(DailyPrice.trading_date.asc())
        ).all()

        closes = [float(p.close) for p in prices]
        if len(closes) < 2:
            continue
        returns = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes))]
        series[sid] = returns

    return series


def _pearson(x: list[float], y: list[float]) -> float | None:
    """Pearson correlation coefficient for two equal-length lists."""
    n = min(len(x), len(y))
    if n < _MIN_DAYS:
        return None
    x, y = x[-n:], y[-n:]
    mx = sum(x) / n
    my = sum(y) / n
    num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    dx = sum((xi - mx) ** 2 for xi in x) ** 0.5
    dy = sum((yi - my) ** 2 for yi in y) ** 0.5
    if dx == 0 or dy == 0:
        return None
    return round(num / (dx * dy), 3)


def _variance(xs: list[float]) -> float:
    if not xs:
        return 0.0
    m = sum(xs) / len(xs)
    return sum((x - m) ** 2 for x in xs) / len(xs)


def _covariance(x: list[float], y: list[float]) -> float:
    n = min(len(x), len(y))
    if n == 0:
        return 0.0
    x, y = x[-n:], y[-n:]
    mx = sum(x) / n
    my = sum(y) / n
    return sum((xi - mx) * (yi - my) for xi, yi in zip(x, y)) / n


def compute_correlation_clusters(
    db: Session,
    holdings: list[dict[str, Any]],
    rho_threshold: float = 0.70,
) -> list[dict[str, Any]]:
    """Returns list of correlated pairs among holdings (ρ > rho_threshold).

    Each entry: {"pair": ["SYM_A", "SYM_B"], "rho": 0.87}
    Pairs with insufficient price history are silently skipped.
    """
    # Resolve symbol_ids from snapshots
    instruments = [h["instrument"] for h in holdings if h.get("instrument")]
    if len(instruments) < 2:
        return []

    ns_set = {f"{i}.NS" for i in instruments} | set(instruments)
    snaps = db.scalars(
        select(ScreeningSnapshot).where(ScreeningSnapshot.symbol.in_(ns_set))
    ).all()

    sid_to_instr: dict[int, str] = {}
    for sn in snaps:
        bare = sn.symbol.replace(".NS", "")
        if bare in instruments and sn.symbol_id is not None:
            sid_to_instr[sn.symbol_id] = bare

    if len(sid_to_instr) < 2:
        return []

    try:
        series = _fetch_return_series(db, list(sid_to_instr.keys()))
    except Exception as e:
        logger.warning(f"portfolio_risk: could not fetch return series: {e}")
        return []

    sids = list(series.keys())
    clusters: list[dict[str, Any]] = []
    for i in range(len(sids)):
        for j in range(i + 1, len(sids)):
            rho = _pearson(series[sids[i]], series[sids[j]])
            if rho is not None and abs(rho) >= rho_threshold:
                clusters.append({
                    "pair": [
                        sid_to_instr.get(sids[i], str(sids[i])),
                        sid_to_instr.get(sids[j], str(sids[j])),
                    ],
                    "rho": rho,
                })

    return sorted(clusters, key=lambda c: -abs(c["rho"]))


def compute_portfolio_beta(
    db: Session,
    holdings: list[dict[str, Any]],
    weights: dict[str, float],
) -> float | None:
    """Returns portfolio-weighted beta vs NIFTY 50.

    weights: {instrument: weight_fraction} (fractions should sum to ~1).
    Returns None if NIFTY or portfolio data insufficient.
    """
    nifty_snap = db.scalar(select(ScreeningSnapshot).where(ScreeningSnapshot.symbol == "^NSEI"))
    if not nifty_snap or nifty_snap.symbol_id is None:
        return None

    try:
        nifty_series = _fetch_return_series(db, [nifty_snap.symbol_id])
    except Exception:
        return None

    nifty_rets = nifty_series.get(nifty_snap.symbol_id)
    if not nifty_rets or len(nifty_rets) < _MIN_DAYS:
        return None

    nifty_var = _variance(nifty_rets)
    if nifty_var == 0:
        return None

    instruments = [h["instrument"] for h in holdings]
    ns_set = {f"{i}.NS" for i in instruments} | set(instruments)
    snaps = db.scalars(
        select(ScreeningSnapshot).where(ScreeningSnapshot.symbol.in_(ns_set))
    ).all()
    sid_to_instr: dict[int, str] = {}
    for sn in snaps:
        bare = sn.symbol.replace(".NS", "")
        if sn.symbol_id is not None:
            sid_to_instr[sn.symbol_id] = bare

    try:
        series = _fetch_return_series(db, list(sid_to_instr.keys()))
    except Exception:
        return None

    portfolio_beta = 0.0
    total_weight = 0.0
    for sid, rets in series.items():
        instr = sid_to_instr.get(sid, "")
        w = weights.get(instr, 0.0)
        if w <= 0 or len(rets) < _MIN_DAYS:
            continue
        stock_beta = _covariance(rets, nifty_rets) / nifty_var
        portfolio_beta += w * stock_beta
        total_weight += w

    if total_weight == 0:
        return None
    return round(portfolio_beta / total_weight, 2)


def compute_diversification_score(
    correlation_clusters: list[dict[str, Any]],
    n_holdings: int,
    concentration_clusters: list[dict[str, Any]],
) -> int:
    """Returns 0–100 diversification score. Higher = better diversified.

    Penalises:
      - High-rho pairs (especially ρ > 0.85)
      - Single-name concentration clusters
    """
    score = 100

    # Penalty per correlated pair
    for c in correlation_clusters:
        rho = abs(c["rho"])
        if rho >= 0.85:
            score -= 15
        elif rho >= 0.70:
            score -= 8

    # Penalty for concentration
    score -= len(concentration_clusters) * 10

    # Bonus for size (more holdings = more diversified, up to a point)
    if n_holdings >= 10:
        score = min(score + 10, 100)

    return max(0, min(100, score))
