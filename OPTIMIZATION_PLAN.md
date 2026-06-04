# VajraStocks — Optimization, Suggestions & Alerts Plan

## Overview

Four workstreams, sequenced A → E → C → B → D. Each ships independently.

---

## Workstream A — New Indicators *(foundation; everything else builds on these)*

### What's being added

| Indicator | pandas-ta call | Why it matters |
|---|---|---|
| ADX(14) + DI± | `ta.adx(high, low, close, 14)` | Trend *strength* gate — `regime_bias` gives direction but not conviction. Filters chop. Feeds Workstream E. |
| OBV | `ta.obv(close, volume)` | Confirms breakouts with accumulation; cuts false signals. |
| Supertrend(10, 3) | `ta.supertrend(...)` | ATR trailing stop — replaces fixed `1.5×ATR` stops in portfolio_service/screening. |
| Stochastic(14, 3, 3) | `ta.stoch(...)` | Divergence / oversold timing for swing candidates. |

### Files to change

**`python/src/stocks/services/indicator_engine.py`**
- Add the 4 indicator computations to `calculate_indicators()`

**`python/src/stocks/db/models.py` — `DailyIndicator` (line 148)**
- Add columns: `adx_14`, `plus_di`, `minus_di`, `obv`, `supertrend`, `supertrend_dir`, `stoch_k`, `stoch_d`
- Auto-migrated via `ensure_columns()` on next startup — no manual migration needed

**`python/src/stocks/db/models.py` — `ScreeningSnapshot` (line 252)**
- Add columns: `adx_14`, `trend_strength_class` (WEAK/MODERATE/STRONG), `obv_trend`, `supertrend_dir`, `stoch_state`

**`python/src/stocks/services/screening.py`**
- Materialize new fields in `refresh_snapshot_for_symbol()`
- Add filter params to `query_screener()`

**`python/src/stocks/api/v1/endpoints/screening.py`**
- Add params to `ScreeningParams` and `ScreenerRowResponse` schemas

### Effort
~1 day. Low risk — purely additive. No existing logic changes.

---

## Workstream E — Bias Recalibration: 5-Tier System *(ships with A)*

### Problem with current system

`compute_bias()` in `planner.py` returns only `BULLISH | NEUTRAL | BEARISH` with a single `confirms_up >= 1` threshold.
- Can't distinguish a mildly bullish stock from one firing on all cylinders
- Can't signal when a stock transitions from merely bullish to very strong

### Target output

```
VERY_BULLISH | BULLISH | NEUTRAL | BEARISH | VERY_BEARISH
```

### New logic in `planner.py:compute_bias()`

```
Confirmation factors (0–4 once ADX from A is available):
  1. MACD histogram direction
  2. RSI zone (>=55 up / <=45 down)
  3. EMA21 vs SMA50 cross
  4. ADX > 25 AND DI+ > DI- (up) / DI- > DI+ (down)

VERY_BULLISH  = trend==UP   AND confirms_up   >= 3
BULLISH       = trend==UP   AND confirms_up   == 1 or 2
NEUTRAL       = price in SMA200 band  OR  mixed/no confirms
BEARISH       = trend==DOWN AND confirms_down == 1 or 2
VERY_BEARISH  = trend==DOWN AND confirms_down >= 3
```

### Schema fix required

`ScreeningSnapshot.regime_bias` is currently `String(10)`.
"VERY_BULLISH" = 12 chars → **must widen to `String(20)`**.

`ensure_columns()` only adds missing columns, it does NOT ALTER width.
Need to add an explicit `ALTER COLUMN` step in `connection.py:ensure_columns()` for this field.

### All consumers to update

| File | Location | Change needed |
|---|---|---|
| `python/src/stocks/services/quant/planner.py` | `compute_bias()` | Extend to return 5 tiers |
| `python/src/stocks/db/models.py` | `ScreeningSnapshot.regime_bias` | `String(10)` → `String(20)` |
| `python/src/stocks/db/connection.py` | `ensure_columns()` | Add ALTER COLUMN for `regime_bias` width |
| `python/src/stocks/services/portfolio_service.py` | `_market_regime()` line 467 | Map VERY_BULLISH→BULL, VERY_BEARISH→BEAR |
| `python/src/stocks/services/portfolio_service.py` | `heat_limits` dict line 158 | VERY_BULL → lower heat limit (more aggressive), VERY_BEAR → tighter |
| `python/src/stocks/services/portfolio_service.py` | weak detection line 261 | Flag VERY_BEARISH as weak too |
| `python/src/stocks/services/portfolio_service.py` | `_replacement_candidates()` line 372 | Include VERY_BULLISH in filter |
| `python/src/stocks/api/v1/endpoints/screening.py` | `compute_trade_quality_score()` line 109 | VERY_BULLISH trend score = 50 (vs 35 for BULLISH); VERY_BEARISH = 0 |
| `python/src/stocks/services/screening.py` | `query_screener()` | Accept the new values in regime_bias filter |
| `frontend/src/components/PortfolioPanel.tsx` | Bias badge | Add deep-green (VERY_BULLISH) and deep-red (VERY_BEARISH) color tiers |
| `frontend/src/components/ScreenerPanel.tsx` | Bias badge | Same |

### Effort
~0.5 day (ships alongside A, shares the same files). Medium risk — touches many consumers but changes are mechanical.

---

## Workstream C — Alerts System *(highest visible value)*

### What's missing today
No alert model, no scheduler-driven evaluation. The app is "I go check it" not "it tells me."

### New `Alert` model (`models.py` — auto-created by `create_all`)

```python
id                 INT PK autoincrement
symbol_id          INT FK → symbols (nullable for global alerts)
alert_type         VARCHAR(30)  # PRICE_CROSS_SUPPORT, PRICE_CROSS_RESISTANCE,
                                # STOP_HIT, TARGET_HIT, RSI_EXTREME,
                                # MACD_CROSS, SUPERTREND_FLIP,
                                # VOLUME_BREAKOUT, BIAS_UPGRADE, BIAS_DOWNGRADE
condition_value    FLOAT        # the threshold price/value that triggered
status             VARCHAR(15)  # ARMED / TRIGGERED / DISMISSED
scope              VARCHAR(15)  # HOLDING / WATCHLIST / GLOBAL
triggered_at       DATETIME nullable
message            TEXT         # human-readable e.g. "RELIANCE crossed support ₹2,410"
created_at         DATETIME
```

### New file: `python/src/stocks/services/alert_service.py`

`AlertService.evaluate_all()` — runs post-sync, checks every holding and watchlist symbol:

| Alert type | Logic |
|---|---|
| PRICE_CROSS_SUPPORT | `close < confluence_support * 0.995` |
| PRICE_CROSS_RESISTANCE | `close > confluence_resistance * 1.005` |
| STOP_HIT | `close <= computed_stop_loss` |
| TARGET_HIT | `close >= target_1` |
| RSI_EXTREME | `rsi < 30` or `rsi > 75` |
| MACD_CROSS | `macd_trend` changed vs previous snapshot |
| SUPERTREND_FLIP | `supertrend_dir` changed (from A) |
| VOLUME_BREAKOUT | `volume_breakout_ratio >= 2.0` |
| BIAS_UPGRADE | `regime_bias` moved up a tier vs last (e.g. BULLISH → VERY_BULLISH) |
| BIAS_DOWNGRADE | `regime_bias` moved down a tier (e.g. BULLISH → NEUTRAL) |

### Scheduler hook (`scheduler.py`)

```python
# After engine.run_sync() completes:
from stocks.services.alert_service import AlertService
alert_service = AlertService(db_session)
alert_service.evaluate_all()
```

### API endpoint: `python/src/stocks/api/v1/endpoints/alerts.py`

- `GET /alerts` — list triggered/armed alerts (filterable by status, scope, symbol)
- `POST /alerts/{id}/dismiss` — mark dismissed

### Frontend
- Alert count badge on nav/header
- Alert panel listing triggered alerts with dismiss button
- Bias tier change alerts benefit directly from Workstream E's 5-tier system

### Effort
~2–3 days. Medium risk. Evaluation logic reuses existing confluence/snapshot data — the math is already done.

---

## Workstream B — Portfolio-Level Risk *(correctness deepening)*

### What's missing
Everything today is per-position then summed. There's no portfolio-level math.

### New file: `python/src/stocks/services/quant/portfolio_risk.py`

**Correlation matrix**
- Pull 60–90 days of `DailyPrice` for all held symbols
- Compute pairwise Pearson correlation on daily returns
- Flag pairs with ρ > 0.7 as "hidden concentration" (two PSU banks at 12% weight each = one 24% bet)
- Degrade gracefully when price history is sparse (<20 days: skip)

**Portfolio beta vs ^NSEI**
- `beta = cov(portfolio_returns, nifty_returns) / var(nifty_returns)` over 60 days
- Makes `heat_pct` market-adjusted instead of raw stop-distance sum

**Heat-aware position sizing**
- `position_size_shares` in `portfolio_service.py` and `screening.py` currently ignores total portfolio heat
- Cap: if adding the new position at suggested size would push `heat_pct > heat_limit`, reduce size

### New `aggregates` fields in `get_portfolio()` response

```python
"correlation_clusters": [{"pair": ["HDFCBANK", "ICICIBANK"], "rho": 0.87}],
"portfolio_beta": 1.12,
"diversification_score": 68,   # 0–100; penalises correlated clusters
"heat_aware_sizing_applied": True/False,
```

### Effort
~2 days. Medium risk — correlation needs enough price history; graceful degradation when sparse.

> Sector analysis skipped (per decision: correlation alone catches 90% of real concentration risk without needing a sector-mapping dependency).

---

## Workstream D — Better Suggestions *(quick polish, last)*

### Replacement candidate ranking (`portfolio_service.py:_replacement_candidates`)

Currently ranks by raw RSI. Switch to a risk-adjusted blend:

```python
score = (ret_4w / atr_pct)          # momentum per unit of volatility
      + (adx_14 / 50.0)             # trend strength confirmation (from A)
      + (1.0 if obv_trend=="UP" else 0.0)  # accumulation confirmation (from A)
```

### Trade quality score (`screening.py:compute_trade_quality_score`)

Add ADX and Supertrend factors:
- ADX > 25 AND Supertrend direction matches bias → `trend` component +10
- VERY_BULLISH bias (from E) → `trend` component starts at 50 (vs 35 for BULLISH)

### LLM orchestrator prompts (`orchestrator.py`)

Feed new indicators and 5-tier bias into `_step_stock_analysis_dynamic` and `_step_trade_planner_dynamic` prompts:
- ADX strength, Supertrend direction, Stochastic state in the analysis prompt
- Bias tier (VERY_BULLISH etc.) in the trade planner context

### Effort
~1 day. Low risk — pure improvements to scoring weights.

---

## Sequencing Summary

```
Week 1:  A + E  —  New indicators + 5-tier bias (same files, ship together)
Week 2:  C      —  Alerts system
Week 3:  B      —  Portfolio-level risk
Week 4:  D      —  Suggestion polish + LLM prompt upgrades
```

Total: ~6–8 focused days. Each workstream is independently reviewable and mergeable.

---

## Key Files Reference

| File | Role |
|---|---|
| `python/src/stocks/services/indicator_engine.py` | Compute indicators from OHLCV |
| `python/src/stocks/services/quant/planner.py` | `compute_bias()` — 3-tier → 5-tier |
| `python/src/stocks/services/screening.py` | Snapshot materialization + screener queries |
| `python/src/stocks/services/portfolio_service.py` | Portfolio aggregates + replacement candidates |
| `python/src/stocks/db/models.py` | SQLAlchemy models + schema |
| `python/src/stocks/db/connection.py` | `ensure_columns()` — auto-migration patcher |
| `python/src/stocks/services/scheduler.py` | Background sync scheduler — hook alerts here |
| `python/src/stocks/api/v1/endpoints/screening.py` | Screener API + trade quality score |
| `frontend/src/components/PortfolioPanel.tsx` | Portfolio UI |
| `frontend/src/components/ScreenerPanel.tsx` | Screener UI |
