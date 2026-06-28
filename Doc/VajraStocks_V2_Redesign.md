# VajraStocks 2.0 — Multi-Agent Architecture & Product Redesign

> A first-principles redesign by four collaborating experts: a Principal Engineer,
> a Quantitative Trader, a Swing Trader, and a Hedge Fund Portfolio Manager.
> Grounded in a full review of the current codebase (June 2026), not a generic template.

---

## 1. Executive Summary

VajraStocks today is a **genuinely capable local-first NSE analysis platform** that has grown well past its README's modest description. It has ~9,700 LOC of backend services, 21 API modules, 30+ DB tables, a LangGraph multi-agent layer, two ML stacks, and a feature-rich React UI. The technical foundations — incremental Yahoo sync + NSE EOD import, a materialized screening snapshot, a real composite-scoring engine, and an academically-sourced swing-strategy library — are stronger than most retail tools.

But it has grown by **accretion, not design**. The four agents reached strong consensus on three structural problems:

1. **The `ScreeningSnapshot` god-table (~100 columns) is the load-bearing wall and the biggest liability.** Every new indicator requires a schema migration and a column. It makes screening blazing fast but ossifies the data model and bloats the post-sync pipeline. → Replace with a **narrow EAV/feature-store + indexed materialized views**.

2. **The backtester is a façade.** `backtester.py` returns hardcoded `sharpe_ratio=1.75 / profit_factor=2.1` even on its "success" path, and `_default_results()` invents a 55.45% win rate / 14.85% CAGR on *any* exception. Meanwhile a real, well-built strategy library (`swing.py`, 5 academic strategies with a proper backtest contract) sits **unconnected** to any engine. This is the single most important fix: **a trustworthy backtest/walk-forward engine** is the difference between a charting toy and a research platform.

3. **The product has no memory of the trader's decisions.** There is no trade journal, no execution log, no realized-P&L history. `PortfolioHolding` is a one-shot Zerodha CSV snapshot; `SwingPickNote` is just free-text. A trader cannot answer "did my setups actually work?" — which is the whole point.

The redesign keeps the local-first soul (single user, SQLite, offline, fast startup) while re-organizing around **four clean layers**: a *data plane* (prices/fundamentals/news), a *feature plane* (indicators as a versioned store), a *decision plane* (screeners, strategies, backtests, scores), and a *workflow plane* (watchlist → plan → journal → review). AI becomes a **read-only research copilot over verified data**, never a source of numbers.

**Headline verdict:** Don't rewrite. **Re-architect the data model, build a real backtest engine, add a trade journal, and collapse the UI into a router-driven workflow.** Everything else is improvement, not replacement.

---

## 2. Current Architecture Review (Principal Engineer)

### What exists
```
React 19 + TS + Vite + Tailwind + Zustand
        ↕ REST / SSE
FastAPI + Python 3.12
        ↕ SQLAlchemy 2.0
SQLite (default) / MSSQL / PostgreSQL
        ↕
LangGraph multi-agent  →  Ollama / OpenAI-compatible LLM
VajraML + VajraML2 (LightGBM / Ridge) — offline training, predictions written to snapshot
PyInstaller installers (Windows / macOS / Linux)
```

### Strengths (keep)
- **Clean service separation** in the backend (`sync_engine`, `indicator_engine`, `screening`, `quant/*`, `strategies/*`). Services are cohesive and mostly testable.
- **Materialized-snapshot pattern** is the right *instinct* for a local app: precompute on sync so the UI never does live joins. `ScreeningSnapshot` and `StrategySignal` both follow it.
- **DB-portable design**: JSON-as-Text, `Numeric` for prices, careful unique constraints and indexes. Runs on SQLite and MSSQL unchanged.
- **Settings in DB** (`AppSetting`) with runtime updates — good for a no-restart desktop UX.
- **LangGraph StateGraph** (`agents/graph.py`) is a clean, modern agent design with conditional routing and per-thread checkpointing.
- **EOD import pipeline** (staging → Yahoo-first resolution → patch) is thoughtful and handles the real-world NSE data-quality problem.

### Weaknesses (fix)
| # | Issue | Evidence | Impact |
|---|-------|----------|--------|
| 1 | **God-table schema** | `ScreeningSnapshot` ~100 columns (`models.py:291–463`); every indicator = new column + migration | Ossified data model; painful evolution; wide-row writes |
| 2 | **Fake backtest results** | `backtester.py:117–118, 124–132` hardcodes Sharpe/PF; fabricates defaults on error | Destroys quant trust; poisons AI context |
| 3 | **Two parallel ML stacks** | `VajraML/` (ridge+lgbm IC regression) and `VajraML2/` (triple-barrier classifier); only V2 is wired in | Confusing; V1 appears abandoned; ~30 stray log files in `VajraML2/` |
| 4 | **Monolithic UI components** | `ScreenerPanel.tsx` 2,802 LOC; `SwingPicksPanel` 1,016; `PortfolioPanel` 827; `PriceChart` 641 | Hard to maintain/test; slow to change |
| 5 | **No client router** | `App.tsx` hand-rolls tab state + `popstate` parsing (`App.tsx:99–104`) | Fragile navigation; no deep links; no code-splitting |
| 6 | **Dual config source of truth** | `config.yaml` *and* `AppSetting` table both hold AI/DB/downloader settings | Drift risk (e.g. `config.yaml` model `gemma4:e4b` looks like a typo; `base_url` is a hardcoded LAN IP) |
| 7 | **No background-job framework** | Sync/indicator recompute run in-process via `scheduler.py` | Long syncs block; no progress/cancel/retry as first-class |
| 8 | **No automated test coverage signal** | `tests/` exists but feature breadth far outpaces it | Regressions on a 30-table schema are likely |

### Architectural smells
- **Snapshot rebuild is monolithic and coupled to sync.** Adding ML2 predictions meant bolting columns onto `ScreeningSnapshot` and adding a post-sync hook. Each new signal increases sync time linearly and is all-or-nothing.
- **Single-writer SQLite with synchronous FastAPI** is fine for one user, but heavy recompute on the request thread will jank the UI. Needs a worker.

---

## 3. Current Product Review

### Navigation (today)
11 top-tabs in a flat bar: **Explorer · Screener · Strategy · Portfolio · Watchlist · Compare · Picks · AI Research · ML Model · About · Settings** + Sync gear + Alerts bell. Keyboard shortcuts exist (`App.tsx:113–122`).

### Feature inventory (observed)
- **Explorer**: chart workspace (cand/ Heikin-Ashi / Renko / Line Break via Lightweight Charts) + metrics table + fundamentals/news/NSE filings tabs + trade-plan card + corporate-actions timeline.
- **Screener**: very deep — RSI/SMA/MACD/CMF/StochRSI/ADX/Supertrend/CPR/AVWAP/Weinstein/divergence/squeeze + composite score + crossover-recency fields. (Reflected in the ~100-col snapshot.)
- **Strategy**: materialized `StrategySignal` per (symbol, strategy) with entry/stop/target/RR.
- **Portfolio**: Zerodha CSV import → holdings + derived risk metrics.
- **Watchlist**: DB-persisted named lists.
- **Compare**: multi-symbol comparison.
- **Picks (Swing Picks)**: curated swing candidates + catalyst notes.
- **AI Research**: LangGraph chat with persistent threads, summaries, annotations.
- **ML Model**: VajraML2 training UI (start run, fold metrics, IC).
- **Alerts**: post-sync triggered alerts (price/stop/target/RSI/MACD/supertrend/volume/bias).

### The product gap, in one sentence
**It is excellent at *finding* and *describing* opportunities, weak at *validating* them (no real backtest), and blind to *outcomes* (no journal/execution log).** The loop from idea → trade → review is broken at both ends.

---

## 4. Individual Agent Reviews

### 4.1 Principal Engineer
> "The bones are good; the joints are stiff. The snapshot table is a brilliant cache and a terrible schema. I want the *speed* of materialization without the *rigidity* of 100 columns. The answer is a feature store + materialized views, plus a real job worker so sync stops being a monolith. Collapse the two ML folders, kill the dual config, and put the UI behind a router with lazy routes. None of this needs cloud anything — it's all local."

Priorities: feature-store refactor · job worker (in-process queue, SQLite-backed) · router + code-split · single config source · test harness on the snapshot/screening path.

### 4.2 Quantitative Trader
> "I can't trust a number I can't reproduce. The backtester literally returns 1.75 Sharpe as a constant — that has to go *first*. But the good news: `swing.py` already implements Jegadeesh-Titman, George-Hwang 52wk-high, Antonacci dual-momentum, Minervini, and Weinstein with a clean signal/position/stop/target contract. Wire that into a **vectorized event-driven backtester with walk-forward and proper cost/slippage**, and this becomes a research platform. I also want regime-aware screening, cross-sectional ranking (not just absolute thresholds), and a deflated-Sharpe / multiple-testing guard so we don't overfit the 100 indicators we already compute."

Priorities: real backtest + walk-forward · cross-sectional rank/z-score screening · regime model as a first-class object · IC/decile reports for every signal · purged/embargoed CV (already partly in VajraML2).

### 4.3 Swing Trader
> "Half these tabs I'd never open mid-session. I open a chart, I want: is the trend up, where's my entry, where's my stop, what's the R, and did this kind of setup work before. The screener is *over-loaded* — 100 columns is analyst cosplay, not a trading tool. Give me 8–10 setups I actually trade (pullback-to-20EMA, Stage-2 breakout, NR7/inside-bar coil, 52wk-high momentum) as one-click presets. And I desperately need a **journal**: snapshot the chart + thesis at entry, log the exit, show me my win rate by setup. Without that I'm just guessing forever."

Priorities: setup-preset screeners (not 40 sliders) · one-screen trade planner (entry/stop/target/size/R) · trade journal with auto-review · alerts that matter (level breaks on *my* watchlist) · remove ML/Compare/AI from the daily path.

### 4.4 Hedge Fund Portfolio Manager
> "As a single-book PM I think in *exposures and attribution*, not single stocks. The portfolio view is a CSV snapshot — useless for decisions. I need: live mark-to-market, sector/factor exposure, concentration and correlation, contribution-to-risk, drawdown and stress scenarios, and **performance attribution** so I know whether I'm making money from stock selection or just beta. The composite score is a decent factor; expose it as one factor among several (value/quality/momentum/low-vol) with an attribution lens. Keep it local — DuckDB over the existing SQLite gives me analytical queries without a server."

Priorities: live portfolio with risk decomposition · factor/sector exposure · correlation & concentration limits · scenario/stress (rate shock, sector shock, 2020-style gap) · attribution report · liquidity (ADV-based) check on position sizing.

---

## 5. Agent Debate & Trade-offs

**Debate 1 — Kill the snapshot table, or keep it?**
- *Swing Trader:* "100 columns is insane, burn it."
- *Engineer:* "The *table* is the problem, the *pattern* is right. We need a narrow feature store (`feature_values(symbol_id, date, feature_id, value)`) plus **materialized views** for the hot screening path. Best of both: schema never changes when we add an indicator, screening stays index-fast."
- *Quant:* "Feature store also gives me point-in-time correctness for backtests — the current wide table only stores *latest*, which is why backtesting is bolted on badly."
- **Resolution:** Feature store + materialized hot-view. Unanimous.

**Debate 2 — How central is AI?**
- *PM & Quant:* "AI must never produce a number. It explains, summarizes, drafts theses over *verified* computed data."
- *Swing Trader:* "Keep it out of my daily loop; make it a copilot I open on demand."
- *Engineer:* "LangGraph layer is good; constrain its tools to read-only DB functions and make every claim cite a computed value."
- **Resolution:** AI = read-only research copilot with tool-calls into the quant layer. Demote from a top tab to a slide-over panel available everywhere.

**Debate 3 — One ML stack or two?**
- *Quant:* "Triple-barrier (V2) is the right labeling; IC-regression (V1) is redundant. Merge to one, keep V1's IC-eval harness."
- *Engineer:* "Collapse `VajraML` + `VajraML2` → `vajra/ml`, delete stray logs, version models in DB (`ml_training_runs` already exists)."
- **Resolution:** One ML module, triple-barrier labels, IC + decile eval, predictions as *one factor* not a hardcoded snapshot column.

**Debate 4 — Backtester scope (the one real conflict).**
- *Quant:* "Full event-driven engine with walk-forward, costs, slippage, purged CV."
- *Swing Trader:* "I just want 'has this setup worked on this stock the last 3 years' in 2 seconds."
- *Engineer:* "These aren't opposed — one vectorized engine, two front-ends: a quick single-name 'setup replay' and a full portfolio walk-forward."
- **Resolution:** Single engine, two entry points. The quick replay is what the swing trader sees; the walk-forward is what the quant/PM see.

**Documented disagreement (unresolved):** PM wants factor attribution and stress scenarios as **v2.0 core**; Swing Trader considers them **v2.2 nice-to-have** that shouldn't delay the journal and backtester. *Decision:* journal + backtester ship first (they serve all four personas); attribution/stress land in the next milestone. The PM's exposure/concentration view ships in v2.0 because it's cheap on top of a live portfolio; full stress testing waits.

---

## 6. Consensus Recommendations

1. **Re-model data as a feature store + materialized views.** Retire the 100-column snapshot.
2. **Build one trustworthy backtest engine** (vectorized event-driven, walk-forward, costs/slippage, purged CV) and wire `swing.py` into it. Delete the fake backtester.
3. **Add a Trade Journal + execution log** as a first-class domain (entry snapshot, thesis, exit, realized P&L, auto-review by setup).
4. **Make the portfolio live** (mark-to-market, exposure, concentration, correlation, contribution-to-risk).
5. **Collapse the UI** into a router-driven, workflow-oriented IA (5 primary destinations, not 11 tabs); split the mega-components.
6. **Unify ML** into one module; predictions become one factor among several.
7. **AI = read-only copilot** with tool-calls into verified quant functions; never authors numbers.
8. **Single config source** (DB-backed `AppSetting`, with a typed schema + export/import); `config.yaml` becomes seed-only.
9. **Add an in-process job worker** (SQLite-backed queue) for sync/recompute/backtest with progress, cancel, retry.
10. **Adopt DuckDB** (embedded, local) alongside SQLite for analytical/backtest queries — no server, pure local.

---

## 7. Feature Audit Matrix

Legend: **K**eep · **I**mprove · **R**emove · **Rep**lace · **M**erge · **Rb** Rebuild

| Feature | Eng | Quant | Swing | PM | Verdict |
|---|---|---|---|---|---|
| Explorer chart workspace | K | K | K | K | **Keep** (split component) |
| 4 chart types (HA/Renko/LineBreak) | K | I | K | – | **Keep**; compute on demand, stop materializing bricks/lines |
| Screener (100-col) | Rb | I | R-ish | I | **Rebuild** as presets + cross-sectional rank |
| Strategy signals | K | I | K | K | **Improve** (back it with real backtest) |
| Composite score | K | K | K | I | **Keep**; expose as a factor |
| Swing Picks | M | M | K | – | **Merge** into Screener presets + Journal |
| Portfolio (CSV) | Rb | – | I | Rb | **Rebuild** as live portfolio |
| Watchlist | K | K | K | K | **Keep** (add alerts/levels) |
| Compare | K | I | I | I | **Keep**; add factor/correlation lens |
| AI Research (top tab) | I | I | R(from daily) | I | **Improve**; demote to slide-over copilot |
| ML Model tab | M | M | R(from daily) | – | **Merge** into one ML module, advanced area |
| Alerts | K | I | K | I | **Keep**; scope to watchlist + levels |
| Backtester | Rb | Rb | Rb | Rb | **Rebuild** (currently fake) |
| Fundamentals / News / NSE filings | K | K | K | K | **Keep** |
| Trade Journal | — | — | — | — | **Add (Critical)** |
| Trade Planner | I | I | Rb | I | **Rebuild** as one-screen workflow |
| Regime model | hidden | K | I | K | **Promote** to first-class object |
| Two ML folders | M | M | – | – | **Merge → one** |

---

## 8. Features to Keep (and why)
- **Materialized-on-sync philosophy** — correct for local-first; just narrow the storage.
- **Composite scorer** (`composite_scorer.py`) — real, documented, useful; becomes the "momentum/trend factor."
- **Swing strategy library** (`swing.py`) — academically sound; finally connect it to a real engine.
- **EOD import pipeline** — solves a genuine NSE data-quality problem; keep, harden.
- **LangGraph agent layer** — modern and clean; constrain its tools.
- **DB-persisted settings, watchlists, conversations** — survive cache clears; good.
- **Cross-platform PyInstaller installers** — keep; add auto-update channel.

## 9. Features to Improve
- **Screener** → setup presets + cross-sectional z-score ranking + saved screens; hide the 40-slider mode behind "Advanced."
- **Alerts** → scope to watchlist/holdings, add trendline-break and level-break alerts (data already exists in `symbol_trendlines`, `symbol_confluence_levels`).
- **Compare** → add correlation matrix, relative-strength chart, factor exposure overlay.
- **AI Research** → tool-constrained copilot, citations to computed values, available everywhere via slide-over.
- **Charts** → compute Renko/Line-Break/HA on demand (drop 3 materialized tables).

## 10. Features to Remove
- **The fake `backtester.py`** — delete outright; its outputs are misleading and feed the AI.
- **`VajraML` (V1)** — superseded by V2; keep only its IC-eval harness, archive the rest.
- **Stray training logs** in `VajraML2/` (`train_*_output.log`, `train_*_error.log`) — move to `logs/`, gitignore.
- **`config.yaml` runtime settings** — collapse into `AppSetting`; keep only bootstrap seed.
- **ML Model + Compare from the daily nav** — move to an "Advanced/Research" area; they create noise for the swing trader.
- **Redundant materialized derived-bar tables** (`renko_bricks`, `line_break_lines`, `daily_heikin_ashi`) — recompute on demand; they bloat the DB and the sync.

## 11. Features to Add (prioritized)

| Priority | Feature | Why it matters | User value | Complexity |
|---|---|---|---|---|
| **Critical** | **Trade Journal + execution log** | Closes the idea→trade→review loop; the product's missing memory | Swing/PM see what actually works | Medium |
| **Critical** | **Real backtest + walk-forward engine** | Trustworthy validation; replaces fake metrics | All four personas | High |
| **Critical** | **Live portfolio (mark-to-market + exposure)** | CSV snapshot is decision-useless | PM/Swing | Medium |
| **High** | **Setup-preset screeners + cross-sectional ranking** | Turns 100 indicators into 8 tradable setups | Swing/Quant | Medium |
| **High** | **Regime model as first-class object** | Gate signals by market state | Quant/PM | Medium |
| **High** | **One-screen Trade Planner** (entry/stop/target/size/R, ATR-based) | Pre-trade discipline | Swing | Low–Med |
| **Medium** | **Factor library** (value/quality/momentum/low-vol/size) | Institutional lens; attribution | PM/Quant | Medium |
| **Medium** | **Correlation & concentration guardrails** | Avoid hidden single-bet risk | PM | Low–Med |
| **Medium** | **Plugin SDK** (custom indicators/strategies/screens as Python entry-points) | Extensibility without forking | Power users | Medium |
| **Medium** | **Backup/restore + portable profile** (zip of DB + settings) | Local-first resilience | All | Low |
| **Nice** | **Scenario/stress testing** (rate/sector/gap shocks) | Tail-risk awareness | PM | Medium |
| **Nice** | **Auto-update channel** for installers | Friction-free upgrades | All | Low–Med |
| **Nice** | **Options/derivatives data** (NSE F&O) for hedging/position context | Broader workflow | Quant/PM | High |

---

## 12. Complete Product Redesign (Version 2.0)

### Information architecture — 5 primary destinations (down from 11 tabs)
```
┌─ Home / Market         Market regime, breadth, index health, today's signals,
│                        watchlist movers, open-position alerts. The "morning page."
├─ Research              Stock workspace (chart + metrics + fundamentals/news/filings),
│                        Compare, Factor lens. AI copilot slide-over available here.
├─ Discover (Screener)   Setup presets + cross-sectional rank + saved screens.
│                        "Advanced" reveals full indicator filters.
├─ Plan & Trade          Trade Planner (entry/stop/target/size/R) → Watchlist →
│                        Journal (entry snapshot → exit → realized P&L → review).
└─ Portfolio             Live mark-to-market, exposure, concentration, correlation,
                         contribution-to-risk, attribution, scenarios.

Global: ⌘K command palette · Alerts bell · AI copilot · Settings · Sync status.
Advanced/Research area (not in daily flow): Backtest Lab, ML Lab, Strategy Builder.
```

### The ideal trading workflows
- **Find opportunities:** Home regime check → Discover preset (e.g., "Stage-2 breakout, RS>70, above rising 200") → ranked list (cross-sectional, not absolute) → add to Watchlist.
- **Research a stock:** Research workspace → MTF trend, levels (confluence/trendlines already computed), fundamentals, news/filings → AI copilot drafts a thesis citing computed values.
- **Validate a setup:** Backtest Lab "quick replay" → has this setup worked on this name / cross-section over 3y, with costs? → decile/IC if it's a factor.
- **Build a watchlist:** levels + alerts attached; alerts fire on breaks.
- **Plan a trade:** Trade Planner computes ATR-stop, R-multiple targets, position size from account risk %; saves a plan.
- **Manage portfolio:** live exposure/concentration; size new entry respecting correlation & sector limits.
- **Review:** Journal auto-computes win rate, expectancy, and R-distribution **by setup**; Weekly Review surfaces what's working.
- **Improve:** attribution (selection vs beta vs factor) tells you *why* you made money.

---

## 13. UI/UX Recommendations
- **Router + lazy routes** (React Router or TanStack Router); each destination code-split.
- **⌘K command palette** for symbol jump, screen run, "plan trade for X," "backtest X."
- **Split the mega-components**: `ScreenerPanel` (2,802 LOC) → `ScreenerFilters / ResultGrid / PresetBar / SavedScreens`; same for Portfolio/Picks/PriceChart.
- **Density presets**: a "Trader" mode (sparse, decision-focused) vs "Analyst" mode (full indicator wall). The 100-indicator view is opt-in.
- **Consistent signal language**: every signal shows *value + as-of date + how it was computed* (no opaque verdicts).
- **Keep the keyboard-first ethos** (already present) and extend to the palette.
- **Charts**: single chart component with pluggable series (candles/HA/Renko/LineBreak/overlays), levels and trendlines drawn from the computed tables.

---

## 14. Engineering Architecture (V2)

### Proposed folder structure
```
vajra/
├── apps/
│   ├── desktop/                 # PyInstaller shell + auto-update
│   └── web/                     # React (Vite) — router-driven, code-split routes
├── core/
│   ├── data/                    # sync_engine, eod_import, fundamentals, news, announcements
│   ├── features/                # indicator engine → feature store (versioned)
│   ├── quant/
│   │   ├── factors/             # value/quality/momentum/low-vol/size + composite
│   │   ├── screening/           # cross-sectional rank, presets, saved screens
│   │   ├── strategies/          # swing.py library + registry (the real ones)
│   │   ├── backtest/            # ONE engine: vectorized + walk-forward + costs/CV
│   │   ├── regime/              # first-class regime model
│   │   └── risk/                # position sizing, portfolio risk, exposure, attribution
│   ├── ml/                      # unified (triple-barrier labels, IC/decile eval)
│   ├── journal/                 # trades, executions, reviews   ← NEW domain
│   ├── portfolio/               # live mark-to-market, holdings, lots
│   └── ai/                      # LangGraph copilot (read-only tools)
├── platform/
│   ├── db/                      # SQLite (OLTP) + DuckDB (OLAP) + migrations
│   ├── jobs/                    # SQLite-backed queue worker (progress/cancel/retry)
│   ├── config/                  # single typed settings source
│   ├── logging/  observability/ telemetry/
│   └── plugins/                 # entry-point based plugin SDK
└── api/                         # FastAPI thin layer over core/*
```

### Key engineering decisions
- **Two embedded DBs, zero servers:** SQLite remains the OLTP store; **DuckDB** runs analytical/backtest queries directly over Parquet/SQLite — fully local, no daemon. This resolves the "single-writer SQLite + heavy analytics" tension.
- **In-process job worker** backed by a `jobs` table: sync, indicator recompute, backtests, ML training all become cancellable jobs with progress and retry. Removes request-thread jank.
- **Feature store** replaces the snapshot god-table (see §15). Hot screening served by a materialized view refreshed by the worker.
- **Plugin SDK**: indicators, strategies, screens, and factors register via Python entry-points; the registry pattern already in `strategies/registry.py` generalizes cleanly.
- **AI tool contract**: the copilot can only call typed, read-only functions (`get_indicators`, `run_screen`, `backtest_setup`, `portfolio_exposure`). Every response cites the computed values it used.
- **Testing**: golden-file tests on the feature/screening path; property tests on indicators; a backtest reproducibility test (same inputs → same metrics — directly preventing the fake-results regression).
- **Config**: one typed settings module reading `AppSetting`; `config.yaml` is seed-only. Add export/import for portable profiles.

---

## 15. Database Redesign

### Problem
`ScreeningSnapshot` (~100 columns) and the derived-bar tables (`renko_bricks`, `line_break_lines`, `daily_heikin_ashi`) make the schema brittle and the sync monolithic. Backtests can't be point-in-time because only *latest* values are stored.

### Target model
```
-- Stable core (keep, mostly as-is)
symbols, daily_prices, corporate_actions, symbol_fundamentals,
nse_announcements, news_items, watchlists/items, app_settings,
conversation_* , sync_jobs, eod_import_jobs, ml_training_runs

-- NEW: narrow, point-in-time feature store (replaces wide snapshot + per-indicator columns)
features(id, key, kind, params_json, version)             -- catalog of indicators/factors
feature_values(symbol_id, trading_date, feature_id, value_num, value_str)
  PK (symbol_id, trading_date, feature_id); covering index for screening

-- HOT path: materialized view rebuilt by the worker (not a hand-maintained table)
mv_screening_latest  -- one row/symbol, only the columns the default screen needs

-- NEW: decision + outcome domain
trade_plans(id, symbol_id, setup, entry, stop, target, size, risk_pct, rr, created_at, status)
trades(id, plan_id, symbol_id, side, opened_at, closed_at, ...)
trade_executions(id, trade_id, ts, price, qty, fees)       -- realized fills
trade_reviews(id, trade_id, outcome, lessons, r_multiple)
journal_snapshots(id, trade_id, chart_png/levels_json, thesis, taken_at)

-- NEW: live portfolio
portfolio_accounts(id, name, base_ccy)
positions(id, account_id, symbol_id, qty, avg_cost, opened_at)   -- supersedes CSV-only PortfolioHolding
position_lots(...)                                               -- tax-lot / FIFO support

-- Backtest results (reproducible, stored)
backtests(id, strategy_id, params_json, universe, period, costs_json, created_at)
backtest_metrics(backtest_id, metric, value)        -- real metrics only, computed
backtest_trades(backtest_id, ...)                   -- audit trail
```
- **Derived bars (Renko/LineBreak/HA) become compute-on-demand** services, not tables.
- **Migration is additive then subtractive**: build feature store alongside the snapshot, dual-write, cut the screener over to the materialized view, then drop the wide columns.

---

## 16. Plugin Architecture
- **Mechanism:** Python entry-points (`vajra.indicators`, `vajra.strategies`, `vajra.screens`, `vajra.factors`). Discovered at startup; registered into typed registries (extend `strategies/registry.py`).
- **Contract per plugin type:**
  - *Indicator:* `compute(ohlcv) -> Series/DataFrame`, declares feature keys + params + version.
  - *Strategy:* the existing `swing.py` contract (`generate_signals / position_size / stop_loss / take_profit`).
  - *Screen:* `predicate(feature_frame) -> mask` + UI hints.
  - *Factor:* `score(cross_section) -> z-scores`.
- **Safety:** plugins run in the worker, declared inputs only, time-boxed; signed/first-party plugins trusted, third-party sandboxed and opt-in.
- **UI:** plugins surface as new presets/strategies/factors automatically — no frontend change needed for a new indicator (the wide-table pain disappears).

---

## 17. AI Agent Architecture
- **Keep LangGraph StateGraph** (`agents/graph.py`) — it's the right abstraction.
- **Re-scope to a read-only research copilot.** Tools are typed functions into `core/quant` and `core/data`; the LLM **cannot emit numbers**, only orchestrate tool calls and narrate results with citations.
- **Workflows:** `explain_stock`, `draft_thesis`, `compare`, `screen_in_english` ("show me Stage-2 breakouts with RS>70"), `review_journal` (summarize what setups worked). The fake `backtest_node` is replaced by a tool call into the real engine.
- **Memory:** existing `conversation_threads/messages/summaries` + MemorySaver — keep.
- **Local-first:** Ollama / OpenAI-compatible; fix the `config.yaml` model typo and stop hardcoding a LAN IP — resolve from settings with a localhost default.
- **Guardrail:** a post-generation check that any figure in the reply matches a tool-returned value; otherwise strip/flag it.

---

## 18. Performance Optimizations
- **Move recompute off the request thread** into the job worker; stream progress over SSE (already used for AI).
- **Incremental feature computation**: only recompute features for symbols with new bars since last run (the feature store makes this trivial; the wide snapshot forced full-row rewrites).
- **DuckDB for screening/backtests**: vectorized columnar scans over the feature store beat row-by-row pandas loops (the current backtester iterates `df.iloc` per bar).
- **Drop 3 derived-bar tables** → smaller DB, faster sync, faster backup.
- **Frontend code-splitting** per route; virtualize the long symbol/result lists; memoize the chart series.
- **Connection pooling** already configured; add a read-only DuckDB attach for analytics so OLTP writes aren't blocked.

---

## 19. Security Improvements
- **Secrets:** `AppSetting.is_secret` exists — ensure API keys are encrypted at rest (OS keychain / DPAPI on Windows) not plain Text.
- **Bind to localhost only** by default (it does 8000–8019); never 0.0.0.0. Add an auth token for the local API to prevent CSRF from a malicious local webpage hitting `127.0.0.1:8000`.
- **External fetches** (Yahoo, NSE, news): validate/normalize, timeout, and rate-limit (mostly present); treat all fetched HTML/URLs as untrusted in the UI (no raw injection).
- **Plugin sandbox** for third-party code (see §16).
- **AI:** never let the copilot execute arbitrary SQL — only typed tools. No shell, no file writes.
- **Backups** should be encryptable; portable profile zips may contain keys.

---

## 20. Local Deployment Architecture
- **Single desktop process** (FastAPI + worker thread) serving a bundled React build; opens `127.0.0.1:<port>` in the default browser — keep this model, it's ideal for local-first.
- **Embedded storage**: SQLite (OLTP) + DuckDB (OLAP), both file-based under the platform data dir (`%APPDATA%`/`~/.local/share`/`~/Library`). No external services, fully offline after data sync.
- **Installers**: keep PyInstaller per-OS; add a **delta auto-update** channel (optional, user-controlled).
- **Backup/restore**: one-click export of `{db files + settings + journal}` to a zip; import on a new machine = full portability.
- **Resource posture**: lazy-load ML/backtest deps so cold start stays fast; worker idles at zero CPU.

---

## 21. Migration Plan (non-breaking, incremental)

**Phase 0 — Stop the bleeding (days)**
- Delete/neutralize the fake `backtester.py`; mark backtest UI "coming soon" rather than show invented numbers.
- Move stray ML logs to `logs/`, gitignore; pick one ML stack as canonical.
- Fix `config.yaml` AI typo + LAN-IP; route AI config through settings with localhost default.

**Phase 1 — Data model (1–2 weeks)**
- Introduce feature store + `mv_screening_latest`; **dual-write** alongside the snapshot.
- Add the job worker; move sync/recompute onto it.

**Phase 2 — Trust & outcomes (2–3 weeks)**
- Build the real backtest engine; wire `swing.py`; reproducibility test.
- Ship the Trade Journal + execution log (new domain, no migration risk).

**Phase 3 — UI re-IA (2–3 weeks)**
- Router + 5 destinations; split mega-components; demote AI to slide-over copilot; presets screener.

**Phase 4 — Portfolio & risk (2 weeks)**
- Live portfolio (mark-to-market, exposure, concentration, correlation); cut over from CSV-only `PortfolioHolding`.

**Phase 5 — Cleanup (1 week)**
- Drop the wide snapshot columns and derived-bar tables; DuckDB analytics; plugin SDK GA.

Each phase is shippable and reversible; the snapshot stays until §15's view fully replaces it.

---

## 22. Prioritized Roadmap

| Milestone | Theme | Ships | Persona served |
|---|---|---|---|
| **M0** (now) | Integrity | Kill fake backtester, fix config, unify ML logs | Quant (trust) |
| **M1** | Foundation | Feature store + job worker (dual-write) | Engineer |
| **M2** | Trust | Real backtest + walk-forward engine | Quant, all |
| **M3** | Memory | Trade Journal + execution log + auto-review | Swing, PM |
| **M4** | Clarity | Router IA, preset screener, copilot slide-over | Swing, all |
| **M5** | Portfolio | Live mark-to-market + exposure + concentration | PM, Swing |
| **M6** | Edge | Factor library + regime object + cross-sectional rank | Quant, PM |
| **M7** | Scale | Drop snapshot/derived tables, DuckDB, plugin SDK GA | Engineer |
| **M8** | Polish | Attribution, scenario/stress, auto-update, backup/restore | PM, all |

---

## Guiding-Principle Check
- **Would the four of us use it daily?** Yes — once the journal and real backtester exist, all four loops (find/validate/trade/review) close.
- **Local-first preserved?** Entirely — SQLite + DuckDB + in-process worker + PyInstaller. No cloud, no Kubernetes, no microservices.
- **Simplicity over complexity?** The redesign *removes* a 100-column table, 3 derived-bar tables, one ML stack, a fake backtester, and 6 nav tabs — while adding the two things that actually matter: trustworthy validation and decision memory.

*Single most important next step:* **delete the fake backtester and start the feature-store + journal work.** Everything else compounds from there.
