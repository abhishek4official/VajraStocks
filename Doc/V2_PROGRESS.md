# VajraStocks 2.0 — Build Progress & Resume Checklist

**Branch:** `feature/v2-hybrid-db` (off `feature/screener-report`)
**Tests:** 255 passing · **Spec:** `Doc/VajraStocks_V2.0_PRD_BRD_Architecture.md`
**Last updated:** 2026-06-28

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

### Phase 4 — Navigation (COMPLETE)
- [x] React Router v6 wired (`BrowserRouter` + `Routes`)
- [x] 5-destination NavRail: Dashboard · Screener · Charts · Portfolio · Sync
- [x] Deep-link URLs work; active-route highlighting

### Phase 5 — God-table slimming (COMPLETE)
- [x] Dropped `daily_heikin_ashi`, `renko_bricks`, `line_break_lines` materialized tables
- [x] `features_json TEXT` column added to `ScreeningSnapshot` (JSON long-tail for future indicators)
- [x] HA / Renko / LineBreak now computed **on demand** from `DailyPrice` in `charts.py`
- [x] `screening.py` bulk loads 3/4/5 removed; direction carry-over from existing snapshot
- [x] All 9 downstream references cleaned (`database.py`, `sync_engine.py`, `nodes.py`, `models.py`, etc.)

### ScreenerPanel split (COMPLETE)
- [x] 2,424-line `ScreenerPanel.tsx` split into 4 focused files:
  - `ScreenerFilterBar.tsx` (165 lines) — preset menu + active filter chips
  - `ScreenerRow.tsx` (674 lines) — pure `<tr>` renderer
  - `ScreenerResultGrid.tsx` (1,420 lines) — sort/filter/search/export grid
  - `ScreenerPanel.tsx` (216 lines) — slim orchestrator

### Sync fixes (COMPLETE)
- [x] Bootstrap condition changed from `if not active_symbols` → `if no equity symbols` so a DB with only index symbols (`^NSEI` etc.) still triggers the NSE CSV fetch
- [x] NSE equity CSV URL corrected: `EQUITY_L_ACTIVE.csv` → `EQUITY_L.csv` (old path returns 404)
- [x] Fallback path in `symbol.py` now tries both CWD-relative and package-relative paths
- [x] `POST /sync/bootstrap-symbols` endpoint + **Refresh Symbol Registry** button in SyncPanel

### M2 — Real backtest engine (CORE COMPLETE)
- [x] `services/quant/backtest/metrics.py` — pure, reproducible cagr/max_drawdown/win_rate/profit_factor/sharpe + `compute_metrics` (verified vs hand-computed; honest 0.0/inf on degenerate input)
- [x] `services/quant/backtest/engine.py` — `run_backtest`: no-lookahead single-name sim, intrabar stop/target (stop-first), bps costs+slippage, MTM equity curve, deterministic, empty-bars safe
- [x] `services/quant/backtest/signals.py` — pure `sma_crossover_signals` + `ema_crossover_signals` + `breakout_signals`
- [x] `services/quant/backtest/replay.py` — `run_symbol_backtest`: reads (adjusted) bars from `BarStore` → signal fn → engine
- [x] `services/quant/backtest/walkforward.py` — anchored expanding-window WFA (grid-search IS, evaluate OOS)
- [x] `services/quant/backtest/portfolio.py` — weight-based portfolio engine + `run_strategy_backtest` (real Minervini swing strategy end-to-end)
- [x] **Backtest Lab API** — `/backtest/signals`, `/run`, `/runs`, `/runs/{id}`, `/walk-forward`, `/portfolio`, `/backfill`
- [x] **Statistical guards** — `statistics.py`: probabilistic Sharpe (PSR) + deflated Sharpe (DSR); scipy cross-checked
- [x] **Frontend "Backtest Lab" panel** + Backfill button. Typechecks + prod build clean.
- [ ] Deferred to M4 (AI tool contract): real backtest node in agent graph
- [ ] Optional: RSI setup; purged/embargoed CV; expose PSR/DSR in the `/run` response

### M3 — Trade journal (COMPLETE)
- [x] `JournalTrade` model (verified `create_all` builds it on real MSSQL, 17 cols)
- [x] `services/journal/analytics.py` — realized_pnl / return_pct / r_multiple + `review_by_setup`
- [x] `services/journal/repository.py` — log / close / list / delete / review
- [x] **API** `/journal/trades` (+ `/{id}/close`, `/{id}`, DELETE), `/journal/review`
- [x] **Frontend Journal panel** — log form, inline close, per-setup review table, computed P&L/R
- [ ] Later: execution log (partial fills), entry chart snapshot, mistake-tag analytics

### M4 — Clarity / UI (partial)
- [x] **Cross-sectional ranking (end-to-end)** — `quant/factors.py` + `quant/ranking.py` + API + Ranking panel
- [x] **Preset screeners (end-to-end)** — `quant/presets.py` (7 setup predicates) + API + Setups tab
- [ ] AI copilot demoted to slide-over; numeric guardrail; `SqliteSaver` durable checkpoints

### M5 — Portfolio & risk (LARGELY COMPLETE)
- [x] **Live mark-to-market** — holdings valued at latest synced close
- [x] **Risk metrics** — `portfolio_risk.py`: correlation clustering, beta, HHI concentration, diversification score, VaR/CVaR
- [x] **Contribution-to-risk** — `portfolio_risk.risk_contributions` (pure) + `compute_risk_contributions` wired into `get_portfolio`; `risk_contribution_pct` per holding in API response
- [ ] **Frontend risk_contribution_pct column** — backend done, UI column missing
- [ ] Optional: tax lots, stress/scenario shocks

### M6 — Edge / scale (partial)
- [x] **Factor ranking primitives** — `quant/factors.py` (cross-sectional zscore/percentile/composite)
- [x] **Raw academic factor extractors** — `quant/factor_extractors.py` (momentum 12-1, low-vol, 52wk proximity) + API + Ranking panel "Watchlist (academic factors)" mode
- [ ] Value/quality/size factors (need fundamentals); regime object
- [ ] Screener reads BarStore (M1/M6 data-model work — mirror written, not yet read)
- [ ] Plugin SDK (entry-points)

### M7 / M8 — Polish (partial)
- [x] **Backup/restore** — `services/backup.py` + API + Settings panel section
- [ ] OS notifications for alerts; auto-update channel
- [ ] VaR / scenario / stress / attribution
- [ ] Unify `VajraML` + `VajraML2` → one module
- [ ] Freeze then remove MSSQL/PostgreSQL support

---

## ⏳ PENDING (ordered by priority)

1. **Full sync to completion** — production DB has 0 equity prices; run Refresh Symbol Registry → Trigger Crawl Sync and let it finish (takes 20–30 min cold start)
2. **M5: contribution-to-risk frontend column** — add `risk_contribution_pct` to portfolio holdings table; backend already computes it
3. **M1: incremental indicator recompute** — only recompute indicators for new bars, not full 300-day window every sync
4. **M4: AI copilot** — demote to slide-over, numeric guardrail, `SqliteSaver` durable checkpoints
5. **M1: Migrate EOD sync onto job worker** — deferred; worker exists, sync not yet enqueued through it
6. **`features_json` population** — column on `ScreeningSnapshot` exists but nothing writes to it

---

## Known small debts (deferred, non-blocking)
- [ ] `scheduler.py` — 10 pre-existing ruff errors (`datetime.timezone.utc` → `datetime.UTC`); `ruff --fix` clears 9
- [ ] `nodes.py` / `agents.py` — pre-existing ruff debt (try/except/pass → contextlib.suppress, etc.)

---

## RESOLVED (2026-06-27): backtest SAVE on MSSQL
- Compute/run is correct. Only `save=true` failed on MSSQL LocalDB — `backtest_metrics`/`backtest_trades` had a stale draft schema that `create_all` skipped.
- **Fixed:** dropped & rebuilt the 3 tables; columns now match models. LESSON: `create_all` only creates absent-by-name tables — won't fix a name collision with a stale schema.
