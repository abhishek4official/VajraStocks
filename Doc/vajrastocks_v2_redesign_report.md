# VajraStocks V2.0: Multi-Agent Architecture & Product Redesign
## Local-First NSE Quantitative Analysis & Trading Platform

---

## 1. Executive Summary

This report outlines the comprehensive redesign plan for **VajraStocks V2.0**, transitioning the current application from a basic stock screening tool into an institutional-grade, local-first quantitative research and swing trading workstation. 

By leveraging the collective expertise of a **Principal Software Engineer**, a **Quantitative Trader**, a **Swing Trader**, and a **Hedge Fund Portfolio Manager**, we have challenged every core architectural and product design decision. The resulting consensus prioritizes high performance, advanced statistical validation, institutional-grade risk management, and a streamlined trading workflow—all executed locally on the user's machine with zero cloud dependencies.

### Key Architectural Shifts
* **Hybrid Database Engine**: Splitting storage between **SQLite** (for transactional state, user watchlists, portfolio entries, and journals) and **DuckDB** (for analytical queries, historical price storage, indicator computation, and high-speed backtesting).
* **Multi-Threaded Sync Engine**: Replacing single-threaded downloads with a parallelized downloader using `yfinance` batches and local caching, reducing sync times by up to 80%.
* **Strategy & Backtesting Lab**: Transitioning from a hardcoded golden-cross backtester to a vectorized and event-driven backtesting engine powered by Polars, supporting user-defined JSON/Python strategies.
* **Institutional Risk Terminal**: Implementing correlation clustering, portfolio beta estimation, Value at Risk (VaR), and sector-level concentration controls.

---

## 2. Current Architecture Review

The current VajraStocks V1.0 architecture is structured as a local multi-tier application:

```
+-------------------------------------------------------------+
|                        React 19 UI                          |
|         (Lightweight TradingView Charts, Tailwind)          |
+-------------------------------------------------------------+
                              | REST / SSE
                              v
+-------------------------------------------------------------+
|                      FastAPI Backend                        |
|   (Python 3.12, Uvicorn, LangGraph Agentic Orchestrator)    |
+-------------------------------------------------------------+
                              | SQLAlchemy 2.0
                              v
+-------------------------------------------------------------+
|               SQLite (default) / MSSQL / PG                 |
|             (DailyPrices, DailyIndicators)                  |
+-------------------------------------------------------------+
```

### Current System Bottlenecks
1. **Database Contention**: Storing millions of rows of historical NSE equity data in SQLite leads to slow screening queries and long indicator recalculation times. Using client-server databases like PostgreSQL/MSSQL violates the "zero setup local-first" design principle.
2. **Single-Threaded Downloading**: The data sync engine fetches symbols in small batches with aggressive rate limits, resulting in a slow daily sync process.
3. **Hardcoded Logic**: Technical indicators and screening strategies are hardcoded in python files (`indicator_engine.py`, `backtester.py`), making it impossible for users to build custom strategies.
4. **Ephemereal Agent Memory**: The LangGraph AI research agent uses `MemorySaver` which stores chat state in-memory, losing history whenever the application is restarted.

---

## 3. Current Product Review

The product currently offers several panels (Explorer, Screener, Strategy, Portfolio, Watchlists, Picks, AI Research, ML Training). While feature-rich, it suffers from several product gaps:

* **Disjointed Workflows**: The Trade Planner is isolated from the main charting workspace. A trader must manually copy levels from the chart to the Trade Planner.
* **Under-Engineered Risk Management**: Portfolio risk is calculated as a simple sum of stops. There is no correlation analysis or beta-adjusted exposure.
* **Rudimentary Backtester**: The backtester is hardcoded to a Golden Cross strategy and does not support transaction costs, slippage, or position sizing rules.
* **Aesthetic Inconsistencies**: The UI relies on standard browser fonts and Tailwind utilities without a cohesive design system, making the interface look cluttered during heavy analytical tasks.

---

## 4. Individual Reviews from Each Agent

### Agent 1 — Principal Software Engineer (Architecture & Performance)
> **Verdict**: *Rebuild Backend Data Engine; Improve Installer & State Management.*
* **SQLite for Analytics is a Mistake**: SQLite is perfect for configuration and user data, but querying years of daily price history for 2000+ symbols is extremely slow. We must introduce **DuckDB** to store OHLCV data. DuckDB is a local columnar database that can run aggregations on millions of rows in milliseconds.
* **Parallel Sync Engine**: Yahoo Finance API rate limits can be mitigated by grouping requests into batch ticks and using Python's `asyncio` or `multiprocessing` to download parallel streams, writing raw parquets to disk before bulk loading into DuckDB.
* **State Management**: The UI should migrate state from Zustand to a more structured local routing framework to prevent performance degradation when rendering large tables.
* **Local Agent State**: LangGraph's `MemorySaver` must be replaced with `SqliteSaver` to persist AI conversations across application restarts.

### Agent 2 — Quantitative Trader (Research & Strategy)
> **Verdict**: *Rebuild Backtester; Replace Static Indicator Calculations.*
* **Lightweight Vectorized Backtesting**: We need a local engine that calculates metrics (CAGR, Sharpe Ratio, Max Drawdown, Profit Factor) using vectorized operations in **Polars**.
* **Statistical Validation**: A quant needs to know if a strategy's returns are statistically significant. We must implement **Monte Carlo simulations** (randomly shuffling trade returns to check for lucky runs) and print p-values for strategy backtests.
* **Walk-Forward Analysis (WFA)**: Enable optimization of strategy parameters (e.g. SMA lengths) using a rolling walk-forward window to prevent overfitting to historical data.

### Agent 3 — Swing Trader (Usability & Discretionary Execution)
> **Verdict**: *Improve Trade Planner; Add Interactive Charting; Rebuild Trade Journal.*
* **Unified Workspace**: I need to see the chart, the screener alerts, and the Trade Planner on a single screen. I want to click on a chart, draw my support/resistance line, and have the app auto-populate the entry and stop-loss levels in my Trade Planner.
* **Multi-Timeframe (MTF) Charts**: Charting must support tabbed sub-charts (Daily/Weekly/Monthly) side-by-side to verify trend alignment.
* **Alert Notifications**: Alerts shouldn't just be an in-app badge. They must trigger OS-level system notifications so I can act immediately.
* **Trade Journaling with Catalysts**: I need a structured trade journal where I can log my entries, attach chart screenshots, write catalyst notes, and tag trades by "Setup Type" (e.g. Volatility Contraction Pattern, Pullback to 20EMA) and "Mistakes" (e.g. FOMO, early exit).

### Agent 4 — Hedge Fund Portfolio Manager (Risk & Allocation)
> **Verdict**: *Replace Portfolio Risk Logic; Add Exposure Analysis.*
* **Correlation Clustering**: If a trader holds 12% in HDFC Bank, 10% in ICICI Bank, and 8% in SBI, they don't have a diversified portfolio. They have a 30% concentration in Indian banking. We must calculate a daily correlation matrix of returns and cluster highly correlated assets.
* **Value at Risk (VaR)**: Calculate parametric and historical VaR (95% confidence) to show the maximum expected loss over a 1-day and 10-day horizon.
* **Stress Testing**: Provide historical scenario analysis. How would the current portfolio perform under the 2008 Financial Crisis, the 2020 COVID Crash, or a 10% market gap-down?

---

## 5. Agent Debate & Trade-offs

During our design workshops, several key debates occurred:

### Debate 1: Programming Language for the Backend
* *Principal Engineer* argued for rewriting the backend in **Rust (Tauri)** to minimize binary size and memory footprint.
* *Quant Trader* and *Portfolio Manager* objected, stating that the entire Python ecosystem (`pandas-ta`, `scikit-learn`, `xgboost`, and custom ML2 models) is required for quantitative calculations and ML training.
* **Consensus**: Retain Python 3.12, but package it cleanly with PyInstaller. Implement **DuckDB** and **Polars** to handle the heavy computations in C++ speed, keeping the Python layer as a thin API coordinator.

### Debate 2: Event-Driven vs. Vectorized Backtesting
* *Quant Trader* wanted a full event-driven backtesting engine (simulating tick-by-tick order book queues).
* *Principal Engineer* noted that event-driven engines are computationally expensive, require massive tick databases (GBs of storage), and are too complex for a local desktop application analyzing daily data.
* **Consensus**: Build a high-performance **vectorized backtester** in Polars for rapid strategy iteration, with a hybrid "pseudo-event-driven" pass that simulates daily high-low fills to accurately capture stop-loss and target triggers within a single bar.

### Debate 3: Advanced Portfolio Optimization Complexity
* *Portfolio Manager* wanted to include Black-Litterman and Mean-Variance Markowitz optimization models for automated capital allocation.
* *Swing Trader* argued that retail swing traders find covariance matrices confusing and prefer manual position sizing based on risk-per-trade (e.g. 1% rule).
* **Consensus**: Implement **risk-parity sizing** and **1% risk-per-trade rules** as default sizing tools. Offer the advanced portfolio optimization models under an "Advanced Quant Lab" tab.

---

## 6. Consensus Recommendations

We have aligned on a single product vision for **VajraStocks V2.0**:
> Build a high-performance, hybrid-database desktop workstation that unifies technical scanning, statistical backtesting, institutional risk modeling, and discretionary swing execution.

### Key Pillars
1. **Speed**: Sub-second screener sweeps and instantaneous backtests via DuckDB + Polars.
2. **Workflow Cohesion**: An integrated layout connecting Charts, Indicators, Trade Planner, and Journaling.
3. **Statistical Integrity**: No more guess-work. Backtests must show statistical significance, Sharpe, and drawdowns.
4. **Risk-First**: Alert-driven stops, correlation alerts, and Value at Risk (VaR) guardrails.

---

## 7. Feature Audit Matrix

| Feature | Current Status | V2.0 Verdict | Why & Benefits | Complexity | Value |
|---|---|---|---|---|---|
| **EOD Price Sync** | Single-threaded `yfinance` | **Replace** | Parallel, batch downloads; faster updates | Medium | High |
| **Screener Engine** | SQL joins on SQLite | **Rebuild** | DuckDB columnar scans; sub-second performance | High | High |
| **Backtester** | Hardcoded Golden Cross | **Rebuild** | Vectorized engine supporting custom strategy scripts | High | High |
| **Portfolio Risk** | Sum of stops | **Replace** | Correlation clustering, Portfolio Beta, VaR, Stress tests | High | High |
| **Trade Planner** | Text boxes, isolated | **Improve** | Drag-and-drop levels on chart, auto-calculates sizes | Medium | High |
| **Trade Journal** | Static list | **Rebuild** | Tagged logs, emotion tracking, performance reports | Medium | Medium |
| **AI Stock Research** | LangGraph, transient memory | **Improve** | Persistent SQLite checkpointer, deep context injection | Medium | Medium |
| **ML Model Training** | PyTorch / Local training | **Keep** | Retain local ML2 training, improve performance via Polars | Low | Medium |

---

## 8. Features to Keep

* **VajraML2 (Triple-Barrier Classifier)**: The machine learning pipeline is highly effective for identifying statistical edges. We will retain the local training pipeline but optimize the feature engineering step using Polars.
* **Lightweight TradingView Charts**: Highly performant and familiar to traders. Keep as the core rendering library.
* **NSE Announcement & News Scrapers**: Scraping official public sources provides critical context for swing traders. Keep and store announcements in SQLite.

---

## 9. Features to Improve

* **Trade Planner**: Extend the planner to calculate risk-adjusted position sizes based on current portfolio heat.
* **FastAPI Backend Lifespan**: Implement proper background tasks using a lightweight local worker queue (e.g., Python's `multiprocessing.Queue` or `Taskiq` with a SQLite backend) to prevent blocking main API threads during data sync.
* **Indicator Calculation**: Recompute indicators incrementally only for the newly synced days instead of deleting and recalculating the entire historical series.

---

## 10. Features to Remove

* **Hardcoded Backtester**: Remove the Golden Cross logic. Replace it with a scriptable engine.
* **In-Memory LangGraph Checkpointer**: Remove the transient memory solver that clears chat history.
* **MSSQL and PostgreSQL Support**: Remove support for enterprise database connections. Supporting three different databases creates high maintenance overhead. Commit fully to a local **SQLite + DuckDB** hybrid architecture, which is zero-configuration and outperforms client-server setups locally.

---

## 11. Features to Add

1. **Custom Strategy Builder**: A programmatic interface where users can write strategies in JSON or Python.
2. **Correlation Heatmap**: Visual matrix highlighting correlated holdings to prevent cluster risk.
3. **Monte Carlo Strategy Simulator**: Runs 1000 randomized shuffles of backtest trades to output confidence bands.
4. **Interactive Chart Tools**: Drag-and-drop stop loss, entry, and target lines directly on the chart.
5. **OS Notifications**: Trigger system-level notifications when screener alerts fire.

---

## 12. Complete Product Redesign (V2.0)

### UI Layout: Three-Pane Professional Workspace
The main interface is redesigned into a unified 3-pane workstation to maximize information density and usability:

```
+------------------------------------------------------------------------------------+
| [Logo] VAJRASTOCKS V2.0   | Workspace | Scanner | Quant Lab | Risk | Journal | Set |
+------------------------------------------------------------------------------------+
|  Left: Symbol Panel       | Center: Interactive Chart              | Right:        |
|  * Watchlists             |                                        | * Trade       |
|  * Alerts Feed            |                                        |   Planner     |
|                           +----------------------------------------+               |
|                           | Center-Bottom: Data Hub                | * AI          |
|                           | * Fundamentals                         |   Co-Pilot    |
|                           | * News & Announcements                 |               |
+------------------------------------------------------------------------------------+
```

### New Navigation Sections
1. **Workspace**: Interactive chart, indicator overlay, and drag-and-drop Trade Planner.
2. **Scanner**: Real-time filters and multi-variable screening.
3. **Quant Lab**: Strategy builder, backtester, walk-forward optimizer, and Monte Carlo analyzer.
4. **Risk Terminal**: Portfolio exposure, correlation matrix, VaR levels, and stress testing.
5. **Journal**: Performance metrics, mistake log, and equity curve.

---

## 13. UI/UX Recommendations

### Aesthetics & Typography
* **Font Family**: Use **Inter** or **Outfit** for clean numbers and labels.
* **Colors**: Curated dark mode. Primary: Deep Navy (`#0B0F19`), Surface: Slate (`#1E293B`), Accents: Neon Purple (`#A855F7`), Neon Green (`#22C55E`), Crimson (`#EF4444`).
* **Glassmorphism**: 80% opacity on sidebars and floating headers with a light backdrop blur.

### Micro-Animations
* **Screener Rows**: Smooth fade-in transitions when symbols match a live scanner.
* **Risk Heatmaps**: Hover states showing exact correlation coefficients with tooltips.
* **Chart Syncing**: A loading spinner that smoothly morphs into a checkmark upon sync completion.

---

## 14. Engineering Architecture

### Module Dependencies
V2.0 relies on a modular python package structure:

```
vajrastocks/
├── backend/
│   ├── api/                # FastAPI routes, schemas, rate limits
│   ├── db/                 # SQLite (Config, State) + DuckDB (Price History)
│   ├── engine/             # Indicators, Sync scheduler, parallel workers
│   ├── quant/              # Backtester, Portfolio Risk, Monte Carlo
│   └── agents/             # LangGraph, SQLite memory saver, tool definitions
├── frontend/
│   ├── src/
│   │   ├── components/     # High-performance charts, heatmaps
│   │   ├── store/          # Zustand State
│   │   └── services/       # SSE and REST Clients
```

### High-Performance Data Processing
* **Polars**: Replaces Pandas for feature engineering and backtest calculation. Polars is written in Rust, utilizes multithreading, and executes expressions lazily.
* **FastAPI Background Workers**: Runs heavy sync operations on a separate process using Python's `multiprocessing` package to keep the web server highly responsive.

---

## 15. Database Redesign

VajraStocks V2.0 utilizes a **hybrid database model** to optimize both read-write speed and transactional safety:

```
                             +------------------------+
                             |     App Controller     |
                             +------------------------+
                               /                     \
                             /                         \
                           v                             v
            +------------------------------+     +-------------------------------+
            |    SQLite (User Database)    |     |   DuckDB (Analytical DB)      |
            |  * User Watchlists           |     |  * Daily OHLCV Price Tables   |
            |  * Trade Journal Logs        |     |  * Pre-computed Indicators    |
            |  * App Settings & API Keys   |     |  * Backtesting Hist. Cache    |
            |  * LangGraph Chat Memory     |     |  * Screening snapshots        |
            +------------------------------+     +-------------------------------+
```

### SQLite Schema additions
* `conversation_messages` table remains in SQLite, but uses `langgraph.checkpoint.sqlite` to linkLangGraph directly to SQLite database.
* `trade_journal` table:
  * `id` INTEGER Primary Key
  * `symbol` VARCHAR(30)
  * `entry_date` DATE
  * `exit_date` DATE
  * `entry_price` NUMERIC
  * `exit_price` NUMERIC
  * `qty` NUMERIC
  * `setup_tags` TEXT (comma-separated tags)
  * `mistake_tags` TEXT
  * `screenshot_path` TEXT
  * `notes` TEXT

### DuckDB Schema
DuckDB will run in-process using `.duckdb` files stored in the local app data folder.
* `prices` table: Columnar table partitioned by symbol.
* `indicators` table: Stores historical technical indicators.

---

## 16. Plugin Architecture

To allow extensibility, V2.0 features a simple file-based plugin system:

1. **Plugin Directory**: A local folder: `%APPDATA%/VajraStocks/plugins/`.
2. **Indicator Plugins**: Users drop a Python script defining a calculation class. The engine scans this folder during initialization:
   ```python
   # Custom indicator example
   class CustomMomentum:
       def compute(self, df_polars):
           # df_polars is a Polars DataFrame containing OHLCV
           return df_polars.with_columns(
               ((polars.col("close") - polars.col("close").shift(10)) / polars.col("close").shift(10)).alias("mom_10")
           )
   ```
3. **Strategy Plugins**: Standardized strategies loaded into the Strategy Screener.

---

## 17. AI Agent Architecture

The AI Agent acts as a co-pilot using a unified **LangGraph** engine:

```
               +-------------------+
               |    User Input     |
               +-------------------+
                         |
                         v
               +-------------------+
               |  Router Node      |
               +-------------------+
              /          |          \
             /           |           \
            v            v            v
    +-----------+  +-----------+  +-----------+
    | Research  |  | Backtest  |  | Screen    |
    | Tool      |  | Tool      |  | Tool      |
    +-----------+  +-----------+  +-----------+
            \            |            /
             \           |           /
              v          v          v
               +-------------------+
               |   Response Node   |<---> [SQLite Checkpointer]
               +-------------------+
```

### Persistent SQLite Checkpointing
Instead of memory loss, conversations are stored in SQLite using `SqliteSaver`.
* Conversation threads persist across restarts.
* The agent has access to system tools: `fetch_stock_details()`, `execute_screener()`, `run_backtest()`.

---

## 18. Performance Optimizations

1. **Parquet Caching**: Store raw data downloaded from Yahoo Finance as local Parquet files. This allows instant schema reconstruction without hitting yfinance.
2. **Incremental Recalculations**: Indicator recalculations are performed on a rolling 50-day window for new bars instead of rebuilding the entire history.
3. **DuckDB Parquet Joins**: Join local parquets and DuckDB tables directly using vectorized execution plans.

---

## 19. Security Improvements

1. **Encrypted Keyring**: API keys (e.g. OpenAI keys, broker login details) are stored securely using the OS keychain via the Python `keyring` library.
2. **Input Sanitization**: Strictly validate screener SQL query parameters to prevent database exploit attempts.
3. **Strict CORS Policy**: Bind FastAPI to `127.0.0.1` explicitly, preventing external machines on the local network from calling the backend API.

---

## 20. Local Deployment Architecture

### Build and Packaging
* **PyInstaller**: Bundles the Python runtime, fastapi server, DuckDB binaries, and PyTorch dependencies into a single platform-native binary folder.
* **Vite Static Build**: The React frontend is pre-built to static assets (`index.html`, js, css) and served directly by FastAPI via `StaticFiles`.
* **Installer Compilation**:
  * **Windows**: WiX Toolset / Inno Setup compiling to a unified `.exe` installer.
  * **macOS**: DMG containing the app package, configured with Apple Developer ID signing certificates.
  * **Linux**: Distribute via AppImage for cross-distro compatibility.

---

## 21. Migration Plan (V1 to V2)

1. **Database Bootstrap**: Upon initial startup, the V2 installer runs a bootstrap script that parses the old SQLite database.
2. **Data Transfer**:
   * Configurations and user watchlists/portfolio items are migrated using a lightweight Alembic migration script.
   * Historical prices are exported from the old SQLite table into compressed parquets, then bulk imported into DuckDB.
3. **Old Schema Cleanup**: The old price-related tables are dropped from SQLite, reclaiming up to 90% of the SQLite database size.

---

## 22. Prioritized Roadmap

```
Phase 1: Core Infra (Weeks 1-3)
  * Hybrid DB: SQLite + DuckDB integration.
  * Multi-Threaded Sync Engine.
  * Polars-based Indicator calculations.

Phase 2: Quant & Strategy Lab (Weeks 4-6)
  * Vectorized & event-driven backtesting engine.
  * Custom Strategy builder (JSON/Python).
  * Monte Carlo simulator & statistical validation (p-values).

Phase 3: Portfolio & Risk (Weeks 7-9)
  * Correlation heatmap.
  * Value at Risk (VaR) & stress testing scenarios.
  * Interactive charting + drag-and-drop Trade Planner.

Phase 4: Journaling & Polish (Weeks 10-12)
  * Trade journal with tagging & screenshots.
  * LangGraph SQLite persistence.
  * Platform packaging (PyInstaller & WiX/DMG/AppImage).
```
