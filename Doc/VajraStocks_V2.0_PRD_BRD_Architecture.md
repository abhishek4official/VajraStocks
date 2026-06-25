# VajraStocks 2.0 — Definitive Product & Engineering Specification
### PRD · BRD · Technical Architecture · Implementation Roadmap

> **Authorship.** This document is the *adjudicated* output of a two-person review team — a
> **Senior Business Analyst / Product Strategist** and a **Principal Software Engineer / Solution
> Architect** — working from first principles. It supersedes and reconciles the two prior
> multi-agent redesign drafts in this folder:
> - `VajraStocks_V2_Redesign.md` (the *code-grounded* draft)
> - `vajrastocks_v2_redesign_report.md` (the *generic/aspirational* draft)
>
> **It is not a merge of those drafts.** Every recommendation below was re-verified against the
> actual codebase (June 2026). Where the prior drafts were wrong, over-engineered, or
> aesthetically driven rather than evidence driven, this document **overrules them and says so
> explicitly** in `⚖️ Adjudication` callouts. Where they were right, we endorse and sharpen.

---

## 0. How to read this document

| Section | Owner | Question it answers |
|---|---|---|
| 1–4 Executive + Assessment | BA + Eng | Where are we, what's true, what's the verdict? |
| 5–11 Business Analysis | BA | Who is this for, what must it do, what's in/out? |
| 12–16 Product Design | BA + Eng | What does V2.0 look like and how does a trader move through it? |
| 17–25 Engineering | Eng | How is it built, stored, secured, packaged? |
| 26–29 Delivery | BA + Eng | In what order, at what risk, with what success criteria? |

**Verdict legend:** **Keep** · **Improve** · **Merge** · **Replace** · **Remove** · **Rebuild** · **Add**

---

## 1. Executive Summary

VajraStocks today is a **genuinely strong local-first NSE research platform** — far past what its
README claims. Verified inventory: ~16.5k LOC of backend source, ~22 API endpoint modules, **29
database tables**, a LangGraph multi-agent layer, **two** parallel ML stacks, an MCP server, and a
feature-rich React 19 UI. The instincts are good: incremental Yahoo sync + NSE EOD import, a
**materialized screening snapshot** so the UI never does live joins, a real composite scorer, and an
**academically-sourced swing-strategy library** (`swing.py`, 6 strategies). This is more capable
than most retail tools.

But it has grown **by accretion, not design**, and three problems are load-bearing:

1. **A trust-destroying fake backtester.** `backtester.py` returns `sharpe_ratio=1.75` and
   `profit_factor=2.1` as **hardcoded constants on its success path** (lines 117–118), and
   `_default_results()` fabricates a `55.45%` win rate / `14.85%` CAGR on **any** exception (lines
   124–132). Meanwhile the real, well-built `swing.py` strategy library sits **unconnected to any
   engine.** This is the single most damaging issue in the product: it feeds invented numbers to the
   UI *and* to the AI copilot. **It must be deleted first, before any feature work.**

2. **A 96-column `ScreeningSnapshot` god-table** (verified: 96 `mapped_column` declarations, lines
   291–465). Every new indicator requires a schema migration and a column; the snapshot rebuild is
   monolithic and coupled to sync. Screening is fast but the data model is ossified.

3. **The product has no memory of the trader's decisions.** No trade journal, no execution log, no
   realized-P&L history. `PortfolioHolding` is a one-shot Zerodha CSV snapshot; `SwingPickNote` is
   free text. The trader cannot answer *"did my setups actually work?"* — which is the entire point
   of a research workstation.

**Headline verdict — do not rewrite.** Re-architect the data model *conservatively*, build **one**
trustworthy backtest engine, add a **trade journal**, make the portfolio **live**, and collapse the
11-tab UI into a **5-destination workflow**. Everything else is improvement, not replacement. The
local-first soul (single user, SQLite, offline, fast startup, PyInstaller) is preserved entirely —
**no cloud, no microservices, no Kubernetes, and — overruling the prior drafts — no mandatory
second database and no Polars/Rust rewrite.**

---

## 2. What We Verified (evidence base)

Both prior drafts make claims about the code. We checked them so this document rests on facts, not
on the drafts:

| Claim | Status | Evidence |
|---|---|---|
| Backtester returns fake metrics | ✅ **True** | `services/quant/backtester.py:117-118` (hardcoded), `:124-132` (fabricated defaults) |
| `ScreeningSnapshot` ≈ 100 columns | ✅ **True (96)** | `db/models.py:291-465` |
| Two parallel ML stacks | ✅ **True** | `VajraML/` (ridge+lgbm), `VajraML2/` (triple-barrier); 6 stray `train_*.log` in `VajraML2/` |
| `swing.py` is a real, unconnected library | ✅ **True** | 6 strategy classes w/ `generate_signals/position_size/stop_loss/take_profit` (`strategies/swing.py`) |
| Dual config source of truth | ✅ **True** | `config/config.yaml` (`base_url: 192.168.31.27`, `model: gemma4:e4b` typo) vs `settings_service.py` DB defaults (`localhost:11434`, `qwen2.5-coder:7b`) |
| Mega-components | ✅ **True** | `ScreenerPanel.tsx` 2,802 LOC; `SwingPicksPanel` 1,016; `PortfolioPanel` 827; `PriceChart` 641 |
| Screening uses absolute thresholds, not ranking | ✅ **True** | `screening.py:1238+` (`rsi_14 >= min_rsi`, etc.) |
| Derived-bar tables materialized | ✅ **True** | `DailyHeikinAshi`, `RenkoBrick`, `LineBreakLine` tables exist |
| Thin test coverage vs surface area | ✅ **True** | 81 test functions / 12 files across 29 tables, 16.5k LOC |

**Implication:** the *code-grounded* prior draft (`VajraStocks_V2_Redesign.md`) is substantially
correct and should be the spine. The *generic* draft (`vajrastocks_v2_redesign_report.md`)
contributed several good ideas (OS notifications, persistent agent checkpoints, correlation/VaR
risk) but also several recommendations we reject on evidence (see §3).

---

## 3. ⚖️ Adjudications — Where We Overrule the Prior Drafts

These are the decisions that make this document *definitive* rather than a synthesis. Each is a
case where at least one prior draft is wrong or premature, and we rule against it.

### ⚖️ A. DuckDB is **optional and backtest-only**, not a mandatory second database.
- *Generic draft claims:* SQLite is "extremely slow" for screening; move **all** price history to
  DuckDB and drop SQLite price tables.
- **Ruling: rejected as stated.** Screening reads **one indexed row per symbol** from the
  materialized snapshot — it never scans price history, so "SQLite is slow for screening" is false
  on this architecture. The genuinely slow paths are (a) indicator **recompute** and (b) the
  backtester's per-bar `df.iloc` loop. DuckDB helps **backtests**, not screening.
- **Decision:** Keep **SQLite as the single source of truth.** Introduce DuckDB *only if* backtest
  profiling proves a pandas/Polars in-memory pass is insufficient — and even then as a **read-only
  analytical attach over the same data**, never a second persistent store to keep in sync.
  Maintaining two synchronized databases on a single-user desktop is complexity with negative ROI
  until proven otherwise. **Measure before adopting.**

### ⚖️ B. Do **not** rewrite the indicator engine in Polars.
- *Generic draft claims:* replace pandas with Polars everywhere.
- **Ruling: rejected.** The bottleneck is **full recompute vs incremental**, not pandas-vs-Polars.
  Rewriting working, tested indicators is high-risk churn with no user-visible benefit.
- **Decision:** Implement **incremental recompute** (only new bars). Reach for Polars/NumPy
  **only** inside the new backtest engine's hot loop, where vectorization actually pays.

### ⚖️ C. The feature store should be a **JSON long-tail column first**, not full EAV.
- *Code-grounded draft proposes:* replace the 96-col snapshot with an EAV `feature_values` table +
  materialized views.
- **Ruling: partially overruled — too much machinery, too early.** EAV + materialized-view refresh
  is real infrastructure to maintain, and the hot view re-introduces a wide structure anyway. At
  **~2,000 symbols × one latest row**, the snapshot is not a *performance* problem; it's an
  *evolution* problem ("adding an indicator needs a migration").
- **Decision (simpler, SQLite-native):**
  1. Keep a **slim typed snapshot** (~15–20 columns) for the default-screen hot path — indexed,
     fast.
  2. Store the **long tail of indicators in a single JSON column** (`features_json`) using SQLite's
     JSON1 functions. *Adding an indicator no longer needs a migration.* This kills the god-table
     pain with a fraction of the EAV effort.
  3. Build a **narrow historical feature table only for the point-in-time series the backtester
     needs** — that is the one place where a long, point-in-time table genuinely earns its keep.
  - Adopt full EAV **only if** profiling the JSON approach on the default screen proves too slow
    (unlikely at this scale).

### ⚖️ D. Reject glassmorphism / neon-decorative UI.
- *Generic draft proposes:* 80%-opacity glass sidebars, backdrop blur, neon purple/green accents.
- **Ruling: rejected.** A dense, number-heavy analytical UI needs **high contrast, high data
  density, and fast rendering.** Translucency and blur reduce legibility, hurt GPU performance on
  large tables/charts, and add cognitive load — the opposite of "reduce research time."
- **Decision:** A disciplined, boring-on-purpose design system: tabular numerals, semantic
  up/down/neutral color, consistent spacing scale, and **Trader (sparse) vs Analyst (full
  indicator wall) density modes**. Looks should serve the data.

### ⚖️ E. Don't build a JSON/Python "custom strategy builder" on the critical path.
- *Generic draft puts it in Phase 2.*
- **Ruling: deferred.** For a single user, a full strategy-DSL is over-engineering relative to
  value. The **plugin SDK via Python entry-points** (code-grounded draft) serves the same power-user
  need more simply. Neither is foundational. Critical path is: kill fake backtester → wire the
  **existing** `swing.py` into a real engine → journal → live portfolio.

### ⚖️ F. Don't rip out MSSQL/PostgreSQL in v2.0 — **freeze** it.
- *Generic draft:* remove enterprise DB support immediately.
- **Ruling: nuanced.** Three-DB portability is real maintenance tax with near-zero single-user
  value — but actively removing it is also effort that helps no one *today*.
- **Decision:** **Default hard to SQLite, stop testing/advertising MSSQL/PG, mark them frozen.**
  Plan removal for a later milestone (it unlocks SQLite-native FTS5/JSON1). Don't spend v2.0 effort
  ripping it out.

### ⚖️ G. Persistent agent checkpoints — the generic draft caught a real nuance.
- Conversations **are** already persisted (`ConversationThread/Message/Summary` tables), so history
  survives restart. But the LangGraph **checkpointer** is in-memory (`MemorySaver`), so mid-graph
  state is not durable.
- **Decision:** Adopt `SqliteSaver` for durable graph checkpoints. Endorse the generic draft here.

### ⚖️ H. Both drafts' timelines are optimistic for a solo developer.
- 12 weeks "for everything" is not realistic. §28 gives a **risk-adjusted, sequenced** roadmap with
  an explicit integrity fix shipping *first* and independently.

---

## 4. Current Product Assessment

### 4.1 Navigation today
11 flat top-tabs: **Explorer · Screener · Strategy · Portfolio · Watchlist · Compare · Picks · AI
Research · ML Model · About · Settings** + Sync gear + Alerts bell. Keyboard shortcuts exist.

### 4.2 Strengths (preserve)
- **Materialize-on-sync philosophy** — correct for local-first; just narrow the storage (§3C).
- **Clean backend service separation** (`sync_engine`, `indicator_engine`, `screening`, `quant/*`,
  `strategies/*`) — cohesive, mostly testable.
- **EOD import pipeline** (staging → Yahoo-first resolution → patch) — solves a real NSE
  data-quality problem.
- **Composite scorer** — real and documented; becomes a first-class *factor*.
- **`swing.py`** — academically sound (Jegadeesh-Titman, 52-wk-high, dual momentum, Minervini,
  Weinstein, RS/MA) — finally connect it to a real engine.
- **DB-persisted settings/watchlists/conversations**, LangGraph StateGraph, cross-platform
  PyInstaller installers, an MCP server already exposing trade-plan/indicator tools.

### 4.3 Weaknesses (fix)
- Fake backtester (integrity emergency). · 96-col god-table. · No journal / no live portfolio /
  no execution log. · Two ML stacks + stray logs. · Mega-components (2,802-LOC `ScreenerPanel`). ·
  Hand-rolled tab routing (no router, no deep links, no code-split). · Dual config drift. · No
  first-class background-job framework (sync runs in-process). · Thin tests vs surface area. ·
  Screening is absolute-threshold only (no cross-sectional ranking).

### 4.4 The gap in one sentence
**The product is excellent at *finding* and *describing* opportunities, weak at *validating* them
(no real backtest), and blind to *outcomes* (no journal).** The loop idea → trade → review is
broken at both ends.

---

## 5. Business Requirements (BRD)

**Product mission.** Be the best **local-first** stock-research and trade-management workstation for
the Indian (NSE) swing/position trader and quant researcher — one that **reduces research time per
decision** and **improves decision quality**, while running entirely offline on the user's own
machine with their own data.

| ID | Business requirement | Rationale |
|---|---|---|
| BR-1 | Every number shown must be **computed and reproducible** — never fabricated, never LLM-authored. | Trust is the product. The fake backtester violates this today. |
| BR-2 | Close the **idea → plan → trade → review** loop with a trade journal and live portfolio. | Without outcomes, the tool cannot improve the trader. |
| BR-3 | Remain **fully functional offline** using last-synced data; internet is sync-only. | Core constraint; research must work on a plane. |
| BR-4 | **Single-user desktop**: zero external services, one-click install/upgrade/backup/restore. | Local-first philosophy; resilience. |
| BR-5 | **Reduce clicks and cognitive load** in the daily trading loop. | Productivity is the value proposition. |
| BR-6 | AI is an **optional, read-only copilot** that never compromises offline use or data integrity. | Differentiator without dependency. |
| BR-7 | Architecture must **absorb new indicators/strategies/factors without schema migrations or UI rewrites.** | The god-table pain is structural debt. |

---

## 6. User Personas

| # | Persona | Frequency | Core need | Anti-need (don't make them wade through) |
|---|---|---|---|---|
| **P1 — Arjun, the Disciplined Swing Trader** *(primary)* | Daily | 5–20 positions, days-to-weeks holds. Setups, one-screen trade plan, alerts on *his* levels, journal-by-setup. | The 96-indicator wall, ML internals, raw SQL. |
| **P2 — Maya, the Quant Researcher** | Weekly-intensive | Trustworthy backtest + walk-forward, cross-sectional ranking, factor IC/decile, overfit guards. | Pretty charts; she wants reproducible metrics. |
| **P3 — Raghav, the Position Trader / Long-term Investor** | Weekly | Stage analysis, fundamentals, trend persistence, position-level risk, fewer-but-bigger decisions. | Intraday noise, scalping tooling. |
| **P4 — Priya, the Single-Book PM** *(power/aspirational)* | Periodic, high-value | Exposure, concentration, correlation, contribution-to-risk, attribution (selection vs beta vs factor). | Single-stock minutiae without a portfolio lens. |

Design tie-break order when needs conflict: **P1 > P2 > P3 > P4** (daily users win the default;
power features live in an Advanced area).

---

## 7. Functional Requirements

Grouped by module; **MoSCoW** priority (M=Must, S=Should, C=Could, W=Won't-yet).

**Data & Sync**
- FR-D1 (M): Incremental EOD sync (Yahoo + NSE EOD import) with staging, resolution, patch.
- FR-D2 (M): **Incremental indicator recompute** — only new bars, not full-history rebuild.
- FR-D3 (M): All sync/recompute runs as a **cancellable background job** with progress.
- FR-D4 (S): Compute Heikin-Ashi / Renko / Line-Break **on demand** (drop materialized tables).

**Discover (Screener)**
- FR-S1 (M): **Setup presets** (8–10 tradable setups) as one-click screens.
- FR-S2 (M): **Cross-sectional ranking / z-scores**, not only absolute thresholds.
- FR-S3 (S): Saved screens; "Advanced" reveals the full indicator filter wall (opt-in).

**Research**
- FR-R1 (M): Stock workspace: chart (pluggable series) + metrics + fundamentals + news + NSE
  filings + computed levels/trendlines.
- FR-R2 (S): Compare with correlation matrix + relative-strength + factor overlay.

**Validate (Backtest)**
- FR-B1 (M): **One real backtest engine** — vectorized with intrabar high/low fill simulation,
  costs, slippage, position sizing; results **stored and reproducible**.
- FR-B2 (M): Wire `swing.py` strategies into it; **delete the fake backtester**.
- FR-B3 (S): Walk-forward analysis; purged/embargoed CV; deflated-Sharpe / multiple-testing guard.
- FR-B4 (C): Monte-Carlo trade-shuffle confidence bands.

**Plan & Trade**
- FR-P1 (M): One-screen **Trade Planner** — ATR-based stop, R-multiple targets, position size from
  account risk %.
- FR-P2 (M): **Trade Journal** — entry snapshot (chart + thesis + setup tag), exit, realized P&L,
  mistake tags; **auto-review: win rate / expectancy / R-distribution by setup**.

**Portfolio & Risk**
- FR-PF1 (M): **Live mark-to-market** portfolio (supersede CSV-only holding) with tax-lot support.
- FR-PF2 (S): Sector/factor exposure, concentration, correlation clustering, contribution-to-risk.
- FR-PF3 (C): VaR (historical + parametric), scenario/stress (2020-gap, sector shock, rate shock),
  attribution.

**Alerts**
- FR-A1 (M): Alerts scoped to **watchlist/holdings**; level-break and trendline-break (data already
  computed in `SymbolConfluenceLevel`, `SymbolTrendline`).
- FR-A2 (S): **OS-level system notifications** (endorse generic draft).

**AI Copilot**
- FR-AI1 (M): Read-only, tool-constrained copilot; **cannot emit numbers** — only orchestrate typed
  tool calls and narrate with citations to computed values.
- FR-AI2 (M): Durable graph checkpoints (`SqliteSaver`).
- FR-AI3 (S): Available everywhere as a slide-over, not a top-level tab.

**Platform**
- FR-X1 (M): One-click **backup/restore** (zip of DB + settings + journal) → portability.
- FR-X2 (S): Optional delta **auto-update** channel for installers.
- FR-X3 (C): **Plugin SDK** (indicators/strategies/screens/factors via entry-points).

---

## 8. Non-Functional Requirements

| Category | Requirement (target) |
|---|---|
| **Integrity** | No fabricated/placeholder metrics anywhere. A reproducibility test asserts: same inputs → identical backtest metrics. AI numeric guardrail strips any figure not traceable to a tool result. |
| **Performance** | Cold start < 3 s (lazy-load ML/backtest deps). Default screen < 1 s @ ~2,000 symbols. Quick single-name backtest (3 yr daily) < 2 s. UI never blocks on recompute (job worker). |
| **Offline** | All research/analysis functions work with last-synced data and no network. |
| **Footprint** | Idle CPU ≈ 0; steady-state RAM modest for a desktop app; DB shrinks after dropping 3 derived-bar tables. |
| **Portability** | SQLite single-file store; backup = copy/zip; cross-platform (Win/macOS/Linux) identical behavior. |
| **Security** | Bind `127.0.0.1` only; local API auth token; secrets encrypted at rest (DPAPI/Keychain); copilot has no SQL/shell/file access. |
| **Maintainability** | New indicator added with **no migration** (JSON long-tail). Mega-components split (<~400 LOC). Single config source. |
| **Testability** | Golden-file tests on feature/screening path; property tests on indicators; backtest reproducibility test; smoke test of the daily workflow. |

---

## 9. Representative User Stories (with acceptance criteria)

- **US-1 (P1):** *As a swing trader, I run a "Stage-2 breakout, RS>70, above rising 200-DMA" preset
  and get a ranked list in under a second.* **AC:** preset exists; results ranked cross-sectionally;
  one click to add to watchlist; < 1 s.
- **US-2 (P1):** *I plan a trade and the app computes my stop (ATR), targets (R-multiples), and size
  (1% account risk) without manual math.* **AC:** planner pre-fills from chart levels; size respects
  account risk %; plan is saved and linked to the symbol.
- **US-3 (P1):** *I log the trade; on exit the journal shows my realized R and updates my win rate
  for that setup.* **AC:** entry snapshot stored; exit logged; per-setup expectancy/R-distribution
  recomputed.
- **US-4 (P2):** *I backtest a `swing.py` strategy with costs and walk-forward and the numbers are
  reproducible.* **AC:** identical inputs → identical metrics; costs/slippage applied; no constant
  appears in output; result row persisted with params.
- **US-5 (P4):** *I see that my "diversified" book is actually 30% correlated Indian banking.* **AC:**
  correlation clustering + sector concentration surfaced on the portfolio view.
- **US-6 (all):** *I ask the copilot "why is X a Stage-2 setup?" and every figure it cites matches a
  computed value.* **AC:** guardrail flags/strips any unverifiable number.

---

## 10. Feature Audit Matrix

| Feature | Verdict | Why (challenged, not inherited) |
|---|---|---|
| Explorer chart workspace | **Keep** (split component) | Core; `PriceChart` 641 LOC → pluggable series + overlays. |
| 4 chart types (HA/Renko/LineBreak) | **Improve** | Compute on demand; **drop** 3 materialized tables. |
| Screener (96-col) | **Rebuild** | Presets + cross-sectional rank; slim hot snapshot + JSON long-tail (§3C). |
| Strategy signals | **Improve** | Back with the real backtest engine. |
| Composite score | **Keep** | Expose as one factor among several. |
| Swing Picks | **Merge** | Fold into Screener presets + Journal. |
| Portfolio (CSV) | **Rebuild** | Live mark-to-market + lots; CSV is decision-useless. |
| Watchlist | **Keep** | Add level/trendline alerts. |
| Compare | **Keep** | Add correlation + RS + factor lens. |
| AI Research (top tab) | **Improve / demote** | Read-only copilot slide-over; never authors numbers. |
| ML Model tab | **Merge** | One ML module in an Advanced area; predictions = one factor. |
| Alerts | **Improve** | Scope to watchlist/holdings + levels; add **OS notifications**. |
| **Backtester** | **Remove → Rebuild** | **Delete the fake one immediately**; build one real engine. |
| Fundamentals / News / Filings | **Keep** | Genuine swing-trade context. |
| Two ML folders + stray logs | **Merge → one** | `VajraML`+`VajraML2` → one `core/ml`; logs to `logs/`, gitignore. |
| `config.yaml` runtime settings | **Remove** | Collapse into `AppSetting`; yaml = bootstrap seed only. |
| MSSQL / PostgreSQL | **Freeze** (remove later) | Maintenance tax, ~0 single-user value (§3F). |
| Hand-rolled tab routing | **Replace** | Router + lazy routes + deep links. |
| **Trade Journal** | **Add (Critical)** | The product's missing memory. |
| **Live Portfolio + Risk** | **Add (Critical/High)** | Exposure/concentration/correlation. |
| **Cross-sectional ranking** | **Add (High)** | Relative strength beats absolute thresholds. |
| **Regime model** (first-class) | **Add (High)** | Gate signals by market state. |
| **Background job worker** | **Add (High)** | Sync/recompute/backtest as cancellable jobs. |
| **Plugin SDK** | **Add (Later)** | Extensibility without forking. |
| **Backup/restore + auto-update** | **Add (Med)** | Local-first resilience & low-friction upgrades. |

---

## 11. Missing Features (prioritized)

| Priority | Feature | Problem solved | Complexity | ROI |
|---|---|---|---|---|
| **Critical** | Trade Journal + execution log + auto-review | No decision memory | Medium | Very high (all personas learn) |
| **Critical** | Real backtest + walk-forward engine | Fake metrics destroy trust | High | Very high (unlocks the platform) |
| **High** | Live portfolio + exposure/concentration/correlation | CSV is useless for decisions | Medium | High |
| **High** | Setup-preset screeners + cross-sectional ranking | 96 indicators → 8 tradable setups | Medium | High |
| **High** | Regime model as a first-class object | Signals fire in the wrong market | Medium | High |
| **High** | Background job worker | UI jank on sync/recompute | Medium | High (enables everything else) |
| **Medium** | OS notifications for alerts | In-app badge is missable | Low | Medium |
| **Medium** | Factor library (value/quality/momentum/low-vol/size) | Institutional lens + attribution | Medium | Medium |
| **Medium** | Backup/restore + portable profile | Local-first resilience | Low | Medium |
| **Medium** | Plugin SDK (entry-points) | Extensibility without forking | Medium | Medium |
| **Low** | VaR / scenario / stress / attribution | Tail-risk awareness | Medium | Medium (P4) |
| **Low** | Auto-update channel | Upgrade friction | Low–Med | Medium |
| **Won't-yet** | NSE F&O / options data | Hedging/position context | High | Defer |

---

## 12. Product Vision 2.0

> **VajraStocks 2.0 is the local-first research workstation that turns NSE data into trustworthy,
> repeatable trading decisions — and remembers how those decisions turned out.**

- **Target audience:** disciplined Indian swing/position traders and quant researchers who want a
  private, offline, own-your-data alternative to cloud screeners and spreadsheets.
- **Competitive advantages / USP:**
  1. **Trust by construction** — every number computed and reproducible; AI never invents figures.
  2. **The full loop in one app** — discover → research → validate → plan → trade → review →
     improve, all local.
  3. **Offline & private** — your watchlists, journal, and theses never leave your machine.
  4. **Extensible** — add indicators/strategies/factors without forking or migrations.
- **Success metrics:**
  - *Activation:* time from install → first synced + first saved screen.
  - *Core-loop adoption:* % of users who log ≥1 journaled trade in week 1.
  - *Trust:* zero fabricated metrics (enforced by test); backtest reproducibility = 100%.
  - *Productivity:* median clicks/time from "open app" → "trade planned."
  - *Retention:* weekly active use of the journal/portfolio review.

---

## 13. Information Architecture & Navigation

**Five primary destinations (down from 11 tabs):**

```
┌─ Home / Market    Regime, breadth, index health, today's signals, watchlist movers,
│                   open-position alerts. The "morning page."
├─ Research         Stock workspace (chart + metrics + fundamentals/news/filings + levels),
│                   Compare, Factor lens. AI copilot slide-over lives here (and everywhere).
├─ Discover         Setup presets + cross-sectional rank + saved screens.
│                   "Advanced" reveals the full indicator filter wall (opt-in).
├─ Plan & Trade     Trade Planner (entry/stop/target/size/R) → Watchlist →
│                   Journal (entry snapshot → exit → realized P&L → review-by-setup).
└─ Portfolio        Live mark-to-market, exposure, concentration, correlation,
                    contribution-to-risk, (later) attribution & scenarios.

Global:   ⌘K command palette · Alerts bell (+OS notifications) · AI copilot · Settings · Sync status
Advanced: Backtest Lab · ML Lab · Strategy/Plugin registry  (out of the daily flow)
```

**Why this IA:** it maps 1:1 to the trader's loop, demotes power tooling (ML/Backtest/Compare) out
of the daily path for P1, and keeps everything one ⌘K away.

---

## 14. User Workflow (end-to-end)

```
First launch → Setup wizard (data dir, provider, first sync)
   → Data sync (background job, progress)
      → Home/Market (regime + breadth + movers + open-position alerts)
         → Discover (preset, e.g. Stage-2 breakout, RS>70 → ranked list → watchlist)
            → Research (MTF trend, levels, fundamentals, news; copilot drafts cited thesis)
               → Validate (Backtest Lab quick replay: "has this setup worked on this name 3y, w/ costs?")
                  → Plan & Trade (ATR stop, R-targets, size from risk %; save plan)
                     → Journal (entry snapshot + thesis + setup tag)
                        → Portfolio (exposure/concentration check before sizing the entry)
                           → (exit) Journal logs realized R → auto-review by setup
                              → Continuous improvement (what's working, what to stop trading)
```

Design rules: **reduce clicks, reduce cognitive load, one screen per decision, keyboard-first.**

---

## 15. Screen-by-Screen Review (deltas from today)

| Screen | Today | V2.0 change |
|---|---|---|
| **Home/Market** | *(absent)* | New "morning page": regime, breadth, index health, movers, open-position alerts. |
| **Research** | Explorer (good) | Split `PriceChart`; pluggable series; copilot slide-over; factor lens. |
| **Discover** | Screener (2,802-LOC, 40 sliders) | Presets + cross-sectional rank; advanced wall opt-in; split into `PresetBar/Filters/ResultGrid/SavedScreens`. |
| **Plan & Trade** | Isolated TradePlanCard + free-text picks | Unified planner → journal; entry snapshots; auto-review. |
| **Portfolio** | CSV snapshot (827-LOC) | Live mark-to-market, lots, exposure, concentration, correlation. |
| **Backtest Lab** | Fake results | Real engine; quick-replay (P1) + walk-forward (P2/P4). |
| **AI Research** | Top tab | Demoted to slide-over; read-only tools; numeric guardrail; `SqliteSaver`. |
| **ML Lab** | Top tab, two stacks | One module in Advanced; predictions = one factor. |
| **Settings** | Dual config | Single typed source; export/import portable profile. |

---

## 16. UI/UX Guidelines

- **Router + lazy routes** (TanStack/React Router); each destination code-split; deep links.
- **⌘K command palette**: symbol jump, run screen, "plan trade for X", "backtest X".
- **Split mega-components** (target <~400 LOC each).
- **Density modes:** Trader (sparse) default for P1; Analyst (full wall) opt-in.
- **Signal language:** every signal shows *value + as-of date + how computed* — no opaque verdicts.
- **Design system, not decoration** (§3D): tabular numerals, semantic color, consistent spacing.
- **Keyboard-first** ethos retained and extended to the palette.

---

## 17. Target Engineering Architecture

```
vajra/
├── apps/
│   ├── desktop/        # PyInstaller shell + (optional) delta auto-update
│   └── web/            # React (Vite) — router-driven, code-split routes
├── core/
│   ├── data/           # sync_engine, eod_import, fundamentals, news, announcements
│   ├── features/       # indicator engine → slim snapshot + JSON long-tail + historical feature table
│   ├── quant/
│   │   ├── factors/    # value/quality/momentum/low-vol/size + composite
│   │   ├── screening/  # cross-sectional rank, presets, saved screens
│   │   ├── strategies/ # swing.py library + registry (the real ones)
│   │   ├── backtest/   # ONE engine: vectorized + intrabar fill + costs + walk-forward + CV
│   │   ├── regime/     # first-class regime model
│   │   └── risk/       # sizing, exposure, concentration, correlation, (later) VaR/attribution
│   ├── ml/             # unified (triple-barrier labels, IC/decile eval)
│   ├── journal/        # trades, executions, reviews        ← NEW domain
│   ├── portfolio/      # live mark-to-market, holdings, lots ← NEW domain
│   └── ai/             # LangGraph copilot (read-only tools, numeric guardrail, SqliteSaver)
├── platform/
│   ├── db/             # SQLite (single source of truth) + migrations; optional DuckDB attach (backtest-only)
│   ├── jobs/           # SQLite-backed job queue worker (progress / cancel / retry)
│   ├── config/         # single typed settings source (AppSetting); yaml = seed only
│   ├── logging/ observability/ telemetry/
│   └── plugins/        # entry-point based plugin SDK (later)
└── api/                # FastAPI thin layer over core/*
```

**Key decisions (and the reasoning):**
- **One database (SQLite), not two.** DuckDB is an optional, backtest-only analytical attach added
  *after* profiling proves the need (§3A).
- **In-process job worker** backed by a `jobs` table: sync, recompute, backtests, ML training become
  cancellable jobs with progress/retry — removes request-thread jank (sync runs in-process today).
- **Features:** slim typed snapshot (hot path) + JSON long-tail (no-migration indicators) + narrow
  historical table (point-in-time backtests) (§3C).
- **AI tool contract:** copilot calls only typed read-only functions (`get_indicators`,
  `run_screen`, `backtest_setup`, `portfolio_exposure`); a post-generation guardrail strips any
  figure not returned by a tool. No SQL, no shell, no file writes.
- **Incremental everything:** recompute only new bars; backtests vectorized; Polars/NumPy only in
  the backtest hot loop (§3B).

---

## 18. Database Architecture

**Principle:** SQLite single-file source of truth; additive-then-subtractive migration; nothing
fabricated.

```
-- Stable core (keep)
symbols, daily_prices, corporate_actions, symbol_fundamentals,
nse_announcements, news_items, watchlists/items, app_settings,
conversation_* , sync_jobs, eod_import_jobs, ml_training_runs,
symbol_trendlines, symbol_confluence_levels, strategy_signals

-- Features: slim hot snapshot + JSON long-tail (replaces the 96-col god-table)
screening_snapshot_core(symbol_id PK, trading_date, <~15-20 hot columns>, features_json)   -- JSON1 long-tail
feature_history(symbol_id, trading_date, feature_key, value_num)   -- point-in-time, backtest-only

-- NEW decision + outcome domain
trade_plans(id, symbol_id, setup, entry, stop, target, size, risk_pct, rr, created_at, status)
trades(id, plan_id, symbol_id, side, opened_at, closed_at, ...)
trade_executions(id, trade_id, ts, price, qty, fees)
trade_reviews(id, trade_id, outcome, lessons, r_multiple, mistake_tags)
journal_snapshots(id, trade_id, chart_png|levels_json, thesis, taken_at)

-- NEW live portfolio
portfolio_accounts(id, name, base_ccy)
positions(id, account_id, symbol_id, qty, avg_cost, opened_at)     -- supersedes CSV-only PortfolioHolding
position_lots(...)                                                  -- tax-lot / FIFO

-- Backtests (reproducible, stored — NO constants)
backtests(id, strategy_id, params_json, universe, period, costs_json, created_at)
backtest_metrics(backtest_id, metric, value)
backtest_trades(backtest_id, ...)

-- Jobs
jobs(id, kind, status, progress, params_json, error, created_at, finished_at)

-- DROP (compute on demand): daily_heikin_ashi, renko_bricks, line_break_lines
```

- **Migration:** build the new feature columns/tables **alongside** the snapshot, dual-write, cut
  the screener over to the slim core + JSON, then drop the wide columns and the 3 derived-bar tables.
  Every step shippable and reversible.

---

## 19. AI / Agent Architecture

- **Keep LangGraph StateGraph** — right abstraction.
- **Re-scope to a read-only research copilot.** Tools are typed functions into `core/quant` and
  `core/data`. The LLM **cannot emit numbers** — only orchestrate tool calls and narrate with
  citations. The fake `backtest_node` becomes a tool call into the **real** engine.
- **Workflows:** `explain_stock`, `draft_thesis`, `compare`, `screen_in_english`
  ("Stage-2 breakouts with RS>70"), `review_journal`.
- **Memory:** keep `conversation_*` tables; add **`SqliteSaver`** for durable graph checkpoints (§3G).
- **Local-first:** Ollama / OpenAI-compatible; fix the `config.yaml` model typo (`gemma4:e4b`) and
  the hardcoded LAN IP — resolve from settings with a **localhost default**.
- **Guardrail:** post-generation numeric check — any figure not matching a tool-returned value is
  stripped/flagged. This is the technical enforcement of BR-1.
- **AI stays optional**: app is fully usable offline with the copilot disabled.

---

## 20. Plugin Architecture (later milestone)

- **Mechanism:** Python entry-points (`vajra.indicators`, `vajra.strategies`, `vajra.screens`,
  `vajra.factors`); discovered at startup; registered into typed registries (generalize the existing
  `strategies/registry.py`).
- **Contracts:** *Indicator* `compute(ohlcv)→Series/DataFrame` + declared feature keys/version;
  *Strategy* = existing `swing.py` contract; *Screen* `predicate(frame)→mask`; *Factor*
  `score(cross_section)→z-scores`.
- **Safety:** run in the worker, declared inputs only, time-boxed; first-party trusted, third-party
  opt-in/sandboxed.
- **Payoff:** a new indicator surfaces as a preset/factor with **no frontend change and no
  migration** — the JSON long-tail makes this clean.

---

## 21. Configuration Strategy

- **Single typed source:** `AppSetting` (DB), runtime-updatable, with a typed schema.
- `config.yaml` becomes **bootstrap seed only** (first-run defaults), not a parallel runtime store.
- **Fix the drift now:** correct the model typo, drop the hardcoded LAN IP, default AI base URL to
  `localhost`.
- **Portable profile:** export/import settings (with secrets handled per §23) for machine moves.

---

## 22. Installer, Backup/Restore, Local Deployment

- **Single desktop process** (FastAPI + worker thread) serving the bundled React build; opens
  `127.0.0.1:<port>` in the default browser — keep this model.
- **Embedded storage** under the platform data dir (`%APPDATA%` / `~/.local/share` /
  `~/Library`). No external services; fully offline after sync.
- **Installers:** keep PyInstaller per-OS (Inno Setup/WiX on Windows; DMG signed on macOS;
  AppImage on Linux). Add an **optional, user-controlled delta auto-update** channel.
- **Backup/restore:** one-click export of `{db + settings + journal}` to a zip; import on a new
  machine = full portability. Encryptable (profile zips may contain keys).
- **Resource posture:** lazy-load ML/backtest deps so cold start stays fast; worker idles at 0 CPU.

---

## 23. Security Review

- **Bind `127.0.0.1` only** (never `0.0.0.0`); add a **local API auth token** so a malicious local
  web page can't drive `127.0.0.1:<port>` (CSRF on localhost).
- **Secrets at rest:** `AppSetting.is_secret` exists — store API keys via OS keychain (DPAPI /
  Keychain / Secret Service), not plain text. `keyring` is a clean fit.
- **External fetches** (Yahoo/NSE/news): validate, timeout, rate-limit; treat all fetched HTML/URLs
  as untrusted in the UI (no raw injection).
- **AI:** typed read-only tools only — no arbitrary SQL, shell, or file writes.
- **Plugins:** sandbox third-party code (§20).
- **Backups:** encryptable; warn before exporting secrets.

---

## 24. Performance Plan

- Move recompute/backtests **off the request thread** into the job worker; stream progress over SSE
  (already used for AI).
- **Incremental feature computation** — only symbols with new bars (the JSON/feature design makes
  this trivial; the wide snapshot forced full-row rewrites).
- Vectorize the backtest hot loop (the current backtester iterates `df.iloc` per bar); reach for
  Polars/NumPy here only.
- **Drop 3 derived-bar tables** → smaller DB, faster sync, faster backup.
- **Frontend:** code-split per route; virtualize long lists; memoize chart series.
- DuckDB analytical attach **only if** profiling proves the in-memory pass insufficient (§3A).

---

## 25. Technical-Debt Register

| Debt | Action |
|---|---|
| Fake `backtester.py` (fabricated metrics) | **Delete immediately**; mark UI "coming soon" until real engine lands. |
| 96-col `ScreeningSnapshot` | Slim core + JSON long-tail; drop wide columns post-cutover. |
| `DailyHeikinAshi`/`RenkoBrick`/`LineBreakLine` tables | Compute on demand; drop tables. |
| Two ML stacks + 6 stray logs | Merge → one `core/ml`; logs to `logs/`, gitignore. |
| Mega-components (2,802-LOC `ScreenerPanel`, etc.) | Split into focused components. |
| Hand-rolled tab routing | Replace with router + lazy routes. |
| Dual config / model typo / LAN IP | Single typed source; fix values. |
| In-process sync (jank risk) | Job worker. |
| Thin tests vs 29 tables | Golden-file + property + reproducibility + smoke tests. |
| `swing.py` unconnected | Wire into the real backtest engine. |
| MSSQL/PG portability tax | Freeze now; remove later. |

---

## 26. Coding Standards & Dev Experience

- **Layering:** `api` → `core` → `platform`; no upward imports; AI/ML are leaf modules.
- **Determinism first:** any displayed metric must be produced by a pure, testable function with a
  reproducibility test. **No constants masquerading as results — ever.**
- **Migrations:** additive-then-subtractive; never destructive in one step.
- **Components:** target <~400 LOC; container/presentational split; typed API client.
- **Tests as gates:** the reproducibility test and the daily-workflow smoke test run in CI before any
  backtest/feature change merges.
- **Logs:** structured, rotated, under `logs/`, gitignored.

---

## 27. Migration Strategy (non-breaking, incremental)

**Phase 0 — Integrity (days):** delete the fake backtester (UI → "coming soon"); fix config
typo/LAN-IP; route AI config through settings; move ML logs to `logs/`; pick one ML stack canonical.
**Phase 1 — Foundation:** job worker; incremental recompute; slim snapshot + JSON long-tail
(dual-write).
**Phase 2 — Trust:** real backtest engine; wire `swing.py`; reproducibility test.
**Phase 3 — Memory:** trade journal + execution log (new domain, no migration risk).
**Phase 4 — Clarity:** router + 5-destination IA; preset screener + cross-sectional rank; copilot
slide-over; split mega-components.
**Phase 5 — Portfolio:** live mark-to-market + exposure/concentration/correlation.
**Phase 6 — Edge & scale:** factor library + regime object; drop wide columns + derived-bar tables;
plugin SDK; (optional) DuckDB attach if profiling demands.
**Phase 7 — Polish:** OS notifications, backup/restore, auto-update; (later) VaR/attribution/stress.

Each phase is independently shippable and reversible; the snapshot stays until the slim core + JSON
fully replaces it.

---

## 28. Implementation Roadmap (risk-adjusted, solo-dev realistic)

> Effort bands assume a single developer; they are **sequenced**, not parallel. "Weeks" are
> deliberately conservative — both prior drafts under-estimated solo effort (§3H).

| Milestone | Theme | Ships | Effort | Risk | Persona |
|---|---|---|---|---|---|
| **M0** | **Integrity** | Kill fake backtester, fix config, unify ML/logs | ~3–5 days | Low | Quant/trust |
| **M1** | Foundation | Job worker + incremental recompute + slim/JSON features (dual-write) | ~2–3 wks | Med | Engineer |
| **M2** | Trust | Real backtest + walk-forward + reproducibility test | ~3–4 wks | High | All |
| **M3** | Memory | Trade journal + execution log + auto-review | ~2–3 wks | Low | P1/P4 |
| **M4** | Clarity | Router IA, preset screener + cross-sectional rank, copilot slide-over | ~2–3 wks | Med | P1/all |
| **M5** | Portfolio | Live mark-to-market + exposure/concentration/correlation | ~2 wks | Med | P4/P1 |
| **M6** | Edge | Factor library + regime object; drop snapshot/derived tables; plugin SDK | ~3 wks | Med | P2/P4 |
| **M7** | Polish | OS notifications, backup/restore, auto-update; VaR/attribution/stress | ~2–3 wks | Low–Med | All |

**Dependencies & risks:**
- M2 depends on M1 (point-in-time features) — *the* high-risk milestone; de-risk with the
  reproducibility test from day one.
- M3 is low-risk (new domain, no migration) — **good morale/value win to ship right after M2.**
- DuckDB stays a *conditional* M6 item gated on profiling, not a commitment.
- Biggest schedule risk: walk-forward/CV correctness in M2. Biggest scope risk: P4 risk analytics —
  keep them in M7 so they never block the daily loop (the documented BA/Quant-vs-Swing
  disagreement: journal+backtester ship before attribution/stress).

---

## 29. Final Recommendations

1. **Delete the fake backtester today.** It is an active integrity breach that poisons both the UI
   and the AI. Nothing else should ship before this.
2. **Build one real, reproducible backtest engine** and wire the existing `swing.py` into it. This is
   the difference between a charting toy and a research platform.
3. **Add the trade journal and live portfolio** — give the product memory of outcomes.
4. **Collapse 11 tabs into 5 workflow destinations**; split the mega-components; add a router.
5. **Solve the god-table the simple way** (slim snapshot + JSON long-tail) — *not* full EAV, *not* a
   second database, *not* a Polars rewrite. Add complexity only when profiling demands it.
6. **Keep AI read-only and number-free**, with a numeric guardrail enforcing it.
7. **One config source, one ML module, localhost-by-default, backup/restore for portability.**

**Local-first preserved?** Entirely — one SQLite file, in-process worker, PyInstaller, offline by
default; no cloud, no microservices, no Kubernetes, no mandatory second DB.

**Net effect:** V2.0 *removes* a 96-column table, 3 derived-bar tables, one ML stack, a fake
backtester, a dual config, and 6 nav tabs — while *adding* the only two things that truly matter:
**trustworthy validation** and **decision memory.**

> *Single most important next step:* **delete `backtester.py`'s fabricated outputs and start the
> job-worker + real-backtest + journal track.** Everything else compounds from there.
