# VajraStocks 2.0 — Build Progress & Resume Checklist

**Branch:** `feature/v2-hybrid-db` (off `feature/screener-report`)
**Tests:** 203 passing · **Spec:** `Doc/VajraStocks_V2.0_PRD_BRD_Architecture.md`
**Last updated:** 2026-06-26

> Convention: all work is TDD (test first), committed under Abhishek (no Claude co-author).

---

## ✅ DONE

### Foundation / hygiene
- [x] V2.0 spec written (PRD/BRD/architecture/roadmap + DuckDB/1 TB adjudications)
- [x] Fixed `.gitignore` that was hiding the **entire `tests/` suite** + `src/stocks/data/` from VCS; brought existing test suite under version control

### Data plane — `python/src/stocks/data/` (DuckDB + partitioned Parquet)
- [x] `adjustments.py` — split **+ dividend** back-adjustment (CRSP-style, query-time)
- [x] `bar_store.py` — `BarStore`: Hive-partitioned Parquet (`symbol=/year=`), upsert-by-date, year-partition pruning, query-time adjustment, `last_date`, `from_config`
- [x] `backfill.py` — `DailyPrice → BarStore` ETL + `CorporateAction` adapter
- [x] `sync_columnar_store` — post-sync job wired into scheduler (non-fatal), **incremental** (only changed symbols)
- [x] Config — `storage.columnar_data_dir` + deps (`duckdb`, `pyarrow`)

### M0 — Integrity (COMPLETE)
- [x] Deleted fabricated `services/quant/backtester.py` (hardcoded sharpe=1.75 / fake 55.45% win rate)
- [x] Removed `backtest_node` from the agent graph; re-wired `trade_plan → report`; dropped stale SSE label
- [x] Reset `config.yaml` AI seed to localhost defaults (LAN IP + model typo removed)
- [x] Confirmed stray ML logs already gitignored/untracked
- [x] Integrity guard test (`test_no_fake_backtester.py`) prevents regression

### M2 — Real backtest engine (CORE + single-name replay DONE)
- [x] `services/quant/backtest/metrics.py` — pure, reproducible cagr/max_drawdown/win_rate/profit_factor/sharpe + `compute_metrics` (verified vs hand-computed; honest 0.0/inf on degenerate input)
- [x] `services/quant/backtest/engine.py` — `run_backtest`: no-lookahead single-name sim, intrabar stop/target (stop-first), bps costs+slippage, MTM equity curve, deterministic, empty-bars safe
- [x] `services/quant/backtest/signals.py` — pure `sma_crossover_signals` (entries/exits)
- [x] `services/quant/backtest/replay.py` — `run_symbol_backtest`: reads (adjusted) bars from `BarStore` → signal fn → engine. **End-to-end data-plane → backtest path works.**

---

## ⏳ PENDING

### M2 — backtest engine (backend COMPLETE)
- [x] **#1 Single-name setup replay** — `run_symbol_backtest` wired to `BarStore` (adjusted bars)
- [x] Setups + **named signal registry** — `sma_crossover`, Donchian `breakout`; run by name or callable
- [x] **Persist results** — `backtests`/`backtest_metrics`/`backtest_trades` + `BacktestRepository`; reproducibility-on-record test (stored == fresh re-run). *(Tables auto-create via `create_all`; dedicated alembic migration is a nice-to-have.)*
- [x] **Backtest Lab API** — `/backtest/signals`, `/run`, `/runs`, `/runs/{id}`, `/walk-forward`; `get_bar_store` dep
- [x] **Walk-forward** — `walkforward.py` anchored expanding-window WFA (grid-search IS, evaluate OOS) + API
- [x] **#2 Portfolio backtest** — `portfolio.py` weight-based engine + `run_strategy_backtest` adapter + `POST /backtest/portfolio`; **real Minervini swing strategy** runs end-to-end (integration test)
- [x] **Frontend "Backtest Lab" panel** + **Backfill** (`POST /backtest/backfill`, CLI `backfill-columnar`, panel button). Typechecks + prod build clean.
- [x] **EMA crossover** setup (registered + API + panel) — setups now: sma / ema / breakout
- [x] **Statistical guards** — `statistics.py`: probabilistic + deflated Sharpe (multiple-testing / overfitting), scipy cross-checked
- [ ] **Deferred to M4 (AI tool contract):** real backtest node in the agent graph — better as a typed copilot tool than a fixed graph node
- [ ] Optional: RSI setup; purged/embargoed CV; expose PSR/DSR in the `/run` response
- [ ] Make the screener actually **read** `BarStore` (M1/M6 data-model work; mirror written, not yet read)

### M1 — rest of Foundation (not started)
- [ ] Real **job worker** (SQLite-backed queue: progress / cancel / retry) — replaces the thin post-sync hook
- [ ] **Incremental indicator recompute** (only new bars)
- [ ] **Kill the 96-col god-table**: slim typed snapshot + JSON long-tail (`features_json`)

### M3 — Memory (DONE — core loop)
- [x] **Trade journal** — `JournalTrade` model (verified `create_all` builds it on real MSSQL, 17 cols)
- [x] `services/journal/analytics.py` — pure realized_pnl / return_pct / r_multiple + `review_by_setup` (win rate, expectancy-in-R, R distribution)
- [x] `services/journal/repository.py` — log / close / list / delete / review
- [x] **API** `/journal/trades` (+ `/{id}/close`, `/{id}`, DELETE), `/journal/review`
- [x] **Frontend Journal panel** — log form, inline close, per-setup review table, computed P&L/R. Typechecks + prod build clean.
- [ ] Later: separate execution log (partial fills), entry chart snapshot, mistake-tag analytics

### M4 — Clarity / UI (not started)
- [ ] Router IA (5 destinations, down from 11 tabs), code-split lazy routes
- [ ] Preset screeners + **cross-sectional ranking** (z-scores, not just absolute thresholds)
- [ ] AI copilot demoted to slide-over; numeric guardrail; `SqliteSaver` durable checkpoints
- [ ] Split mega-components (ScreenerPanel 2,802 LOC, etc.)

### M5 — Portfolio & risk (ALREADY LARGELY IMPLEMENTED — discovered 2026-06-27)
- [x] **Live mark-to-market** — `get_portfolio` values holdings at the latest synced close (`snap.close_price`), not stale CSV LTP
- [x] **Risk metrics wired** — `portfolio_risk.py`: correlation clustering, portfolio beta, HHI concentration, diversification score, VaR/CVaR — called from `get_portfolio`, exposed via `GET /api/v1/portfolio`
- [ ] Genuinely missing (optional): tax lots, contribution-to-risk decomposition, stress/scenario shocks
- NOTE: spec drafts understated this — described as a CSV snapshot but it's a full risk dashboard.

### M6 — Edge / scale (not started)
- [ ] Factor library (value/quality/momentum/low-vol/size) + regime model as first-class object
- [ ] Drop derived-bar tables (HA/Renko/LineBreak) → compute on demand
- [ ] Drop wide snapshot columns after cutover; plugin SDK (entry-points)

### M7 / M8 — Polish (not started)
- [ ] OS notifications for alerts; backup/restore portable profile; auto-update channel
- [ ] VaR / scenario / stress / attribution
- [ ] Unify the two ML stacks (`VajraML` + `VajraML2`) → one module
- [ ] Freeze then remove MSSQL/PostgreSQL support

---

## Known small debts (deferred, non-blocking)
- [ ] `scheduler.py` — 10 pre-existing ruff errors (`datetime.timezone.utc` → `datetime.UTC`); `ruff --fix` clears 9
- [ ] `nodes.py` / `agents.py` — pre-existing ruff debt (try/except/pass → contextlib.suppress, etc.)

## Recommended resume point
**M2 #1** — single-name setup replay wired to `BarStore`. It makes the data plane + engine immediately useful (the swing trader's "has this setup worked on this stock?"), then tackle **#2** (swing.py portfolio + walk-forward) for the quant.

---
## RESOLVED (2026-06-27): backtest SAVE on MSSQL
- Compute/run is correct (real metrics verified on RELIANCE). Only `save=true` fails on **MSSQL LocalDB** (the app's real DB via `%APPDATA%/VajraStocks/config.yaml`), not on SQLite dev DB.
- Error: `Invalid column name 'backtest_id'/'metric'/'value'` — the `backtest_metrics`/`backtest_trades` tables exist in MSSQL with a **stale/mismatched schema**; `create_all` skips tables that already exist by name.
- **Resolved:** the MSSQL `backtest_metrics`/`backtest_trades` had a pre-existing *draft* schema (`run_id`/`metric_name`/`quantity`…) that `create_all` skipped. Dropped & rebuilt the 3 tables → columns now match the models; a full adjusted+save run on RELIANCE succeeds on MSSQL. No code change (models were correct). LESSON: `create_all` only creates absent-by-name tables — it won't fix a name collision with a stale schema.
