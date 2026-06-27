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


def compute_hhi(weights: dict[str, float]) -> dict[str, Any]:
    """HHI = ∑wᵢ² (normalised). <0.10 = LOW, 0.10–0.25 = MODERATE, >0.25 = HIGH."""
    total = sum(weights.values())
    if total <= 0:
        return {"hhi": None, "label": None}
    norm = [v / total for v in weights.values()]
    hhi = round(sum(w ** 2 for w in norm), 4)
    label = "HIGH" if hhi > 0.25 else ("MODERATE" if hhi > 0.10 else "LOW")
    return {"hhi": hhi, "label": label}


def compute_var_cvar(
    db: Session,
    holdings: list[dict[str, Any]],
    weights: dict[str, float],
    portfolio_value: float,
    days: int = 252,
    confidence: float = 0.05,
) -> dict[str, Any]:
    """Historical 1-day VaR and CVaR at `confidence` level (default 5 %).

    Aligns per-symbol daily returns on common trading dates, then weights them
    into a single portfolio return series.  Returns pct values (negative = loss)
    and absolute INR amounts.
    """
    instruments = [h["instrument"] for h in holdings]
    ns_set = {f"{i}.NS" for i in instruments} | set(instruments)
    snaps = db.scalars(
        select(ScreeningSnapshot).where(ScreeningSnapshot.symbol.in_(ns_set))
    ).all()

    instr_to_sid: dict[str, int] = {}
    for sn in snaps:
        bare = sn.symbol.replace(".NS", "")
        if bare in instruments and sn.symbol_id is not None:
            instr_to_sid[bare] = sn.symbol_id

    _empty: dict[str, Any] = {
        "var_1d_pct": None, "cvar_1d_pct": None,
        "var_1d_inr": None, "cvar_1d_inr": None,
    }
    if not instr_to_sid:
        return _empty

    cutoff = datetime.date.today() - datetime.timedelta(days=days + 15)
    sid_list = list(instr_to_sid.values())

    all_prices = db.scalars(
        select(DailyPrice)
        .where(DailyPrice.symbol_id.in_(sid_list), DailyPrice.trading_date >= cutoff)
        .order_by(DailyPrice.trading_date.asc())
    ).all()

    price_by_sid: dict[int, dict[datetime.date, float]] = {sid: {} for sid in sid_list}
    for p in all_prices:
        price_by_sid[p.symbol_id][p.trading_date] = float(p.close)

    # Daily return dicts keyed by date
    ret_by_sid: dict[int, dict[datetime.date, float]] = {}
    for sid, daily in price_by_sid.items():
        sorted_dates = sorted(daily.keys())
        rets: dict[datetime.date, float] = {}
        for i in range(1, len(sorted_dates)):
            d0, d1 = sorted_dates[i - 1], sorted_dates[i]
            p0 = daily[d0]
            if p0 > 0:
                rets[d1] = (daily[d1] - p0) / p0
        ret_by_sid[sid] = rets

    # Intersect dates only for instruments with positive weight
    total_w = sum(weights.values()) or 1.0
    active = [(instr, sid) for instr, sid in instr_to_sid.items() if weights.get(instr, 0) > 0]
    if not active:
        return _empty

    date_sets = [set(ret_by_sid[sid].keys()) for _, sid in active]
    common_dates = sorted(set.intersection(*date_sets))
    if len(common_dates) < _MIN_DAYS:
        return _empty

    portfolio_rets: list[float] = []
    for d in common_dates:
        port_ret = sum(
            (weights[instr] / total_w) * ret_by_sid[sid][d]
            for instr, sid in active
        )
        portfolio_rets.append(port_ret)

    sorted_rets = sorted(portfolio_rets)
    n = len(sorted_rets)
    var_idx = max(0, int(n * confidence) - 1)
    var_ret = sorted_rets[var_idx]
    tail = [r for r in sorted_rets if r <= var_ret]
    cvar_ret = sum(tail) / len(tail) if tail else var_ret

    return {
        "var_1d_pct": round(var_ret * 100, 3),
        "cvar_1d_pct": round(cvar_ret * 100, 3),
        "var_1d_inr": round(abs(var_ret) * portfolio_value, 2) if portfolio_value > 0 else None,
        "cvar_1d_inr": round(abs(cvar_ret) * portfolio_value, 2) if portfolio_value > 0 else None,
    }


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


def risk_contributions(
    weights: dict[Any, float],
    cov: dict[Any, dict[Any, float]],
) -> dict[Any, float]:
    """Percentage contribution to portfolio variance per holding (sums to ~1.0).

    Pure: ``weights`` maps key→weight, ``cov`` is a symmetric covariance matrix keyed the
    same way. A holding's contribution is ``w_i * (Σw)_i / (wᵀΣw)``. Returns {} when the
    portfolio variance is non-positive (e.g. no usable history).
    """
    keys = [k for k in weights if k in cov]
    port_var = sum(
        weights[i] * weights[j] * cov[i].get(j, 0.0) for i in keys for j in keys
    )
    if port_var <= 0:
        return {}
    out: dict[Any, float] = {}
    for i in keys:
        marginal = sum(weights[j] * cov[i].get(j, 0.0) for j in keys)
        out[i] = weights[i] * marginal / port_var
    return out


def compute_risk_contributions(
    db: Session,
    weights_by_symbol_id: dict[int, float],
    days: int = 90,
) -> dict[int, float]:
    """Build a covariance matrix from return history and return per-symbol risk contributions."""
    ids = list(weights_by_symbol_id)
    series = _fetch_return_series(db, ids, days)
    usable = [i for i in ids if len(series.get(i, [])) >= _MIN_DAYS]
    if len(usable) < 2:
        return {}
    n = min(len(series[i]) for i in usable)
    aligned = {i: series[i][-n:] for i in usable}
    cov = {
        i: {j: _covariance(aligned[i], aligned[j]) for j in usable}
        for i in usable
    }
    weights = {i: weights_by_symbol_id[i] for i in usable}
    return risk_contributions(weights, cov)
