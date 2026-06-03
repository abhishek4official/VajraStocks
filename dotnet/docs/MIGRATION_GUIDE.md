# VajraStocks — Migration Guide: Python/FastAPI → .NET Core (REST + Microsoft Agent Framework)

_Target stack: .NET 9, ASP.NET Core Web API (REST/JSON), Entity Framework Core, Microsoft Agent Framework (.NET), Hangfire._

---

## 1. Why REST (not gRPC)

The React frontend already speaks **REST/JSON via `fetch()`** and **SSE via `EventSource`**. By keeping the .NET backend on REST with the **same paths and the same JSON shape**, the frontend needs **essentially zero changes** — you just point `VITE_API_BASE_URL` at the .NET host.

This is the right call for a **local-first, single-user** app:
- No `.proto` toolchain, no generated stubs, no gRPC-Web transport quirks
- The agent console keeps its existing **SSE** streaming (ASP.NET supports SSE natively)
- You still get every server-side benefit of .NET: EF Core, Microsoft Agent Framework, Hangfire, strong typing, single-file publish

The **one contract rule**: .NET must serialize JSON in **snake_case** at the **same routes** so the React types (`close_price`, `rs_score_1m`, `is_gap_up`, …) match byte-for-byte.

---

## 2. What changes, what stays

**Stays identical:**
- The **React frontend** (UI, Zustand store, `services/api.ts`, `EventSource` SSE) — only `VITE_API_BASE_URL` is repointed
- The **data model** (symbols, prices, indicators, snapshots, settings)
- The **REST routes** (`/api/v1/...`) and **JSON shapes**
- The **local-first principle** — Yahoo Finance, no paid APIs
- The **domain logic** (RSI/MACD/ATR, Heikin-Ashi, Renko, Line Break, screening, RS score, trade plans)

**Changes (server side only):**
- Language: Python → C# (.NET 9)
- Web host: FastAPI/Uvicorn → ASP.NET Core/Kestrel
- ORM: SQLAlchemy + Alembic → EF Core + EF Migrations
- Agents: `agent-framework` (Python) → Microsoft Agent Framework (.NET) + Ollama
- Jobs: FastAPI `BackgroundTasks` → Hangfire (adds scheduling + dashboard)

---

## 3. Target architecture

```
┌─────────────────────────────────────────────────────────────┐
│  React 19 + Vite frontend  (UNCHANGED)                       │
│  fetch() REST/JSON  +  EventSource SSE                        │
│  only VITE_API_BASE_URL is repointed                         │
└───────────────────────────────┬─────────────────────────────┘
                                 │  HTTP/JSON (REST) + SSE
┌────────────────────────────────▼────────────────────────────┐
│  ASP.NET Core (.NET 9) — single self-hosted process          │
│                                                              │
│  ├─ Web API Controllers (snake_case JSON):                   │
│  │     SymbolsController, ChartsController,                   │
│  │     IndicatorsController, ScreenersController,             │
│  │     SyncController, SettingsController,                    │
│  │     SetupController, AgentsController (SSE)                │
│  ├─ Microsoft Agent Framework (.NET) — Ollama chat client    │
│  ├─ EF Core DbContext (SQLite default / SQL Server option)   │
│  ├─ Hangfire — scheduled & background jobs                   │
│  ├─ Yahoo Finance data client (HttpClient)                   │
│  └─ Domain services (Indicators, MarketStructure, Screening) │
│                                                              │
│  Serves the React build from wwwroot                         │
└──────────────────────────────────────────────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  SQLite (data/vajra.db)  │  default, local-first
                    │  or SQL Server (option)  │
                    └──────────────────────────┘
```

---

## 4. Component mapping (Python → .NET)

| Concern | Python (current) | .NET (target) |
|---|---|---|
| Web host | FastAPI + Uvicorn | ASP.NET Core Kestrel |
| API style | REST + Pydantic | **REST + Web API Controllers + DTOs** |
| JSON casing | snake_case (Pydantic) | **snake_case (`JsonNamingPolicy.SnakeCaseLower`)** |
| Streaming | SSE (`StreamingResponse`) | **SSE (`text/event-stream` from a controller)** |
| ORM | SQLAlchemy 2.0 | Entity Framework Core 9 |
| Migrations | Alembic | EF Core Migrations |
| DB providers | pyodbc / aiosqlite | `Microsoft.Data.SqlClient` / `Microsoft.Data.Sqlite` |
| Settings store | `app_settings` + SettingsService | `AppSetting` entity + `ISettingsService` |
| Agents | `agent_framework` (Python) | `Microsoft.Agents.AI` (.NET) |
| LLM client | `agent_framework_ollama` | `OllamaChatClient` / `OllamaSharp` |
| Background jobs | `BackgroundTasks` | Hangfire (`BackgroundJob`, `RecurringJob`) |
| Data source | yfinance | `YahooFinanceProvider` (HttpClient) |
| Indicators | pandas-ta | `Skender.Stock.Indicators` (NuGet) |
| Validation | Pydantic | FluentValidation / data annotations |
| Config | config.yaml + DB | `appsettings.json` + DB (DB wins) |
| Logging | loguru | Serilog |
| DI | manual constructors | built-in `IServiceCollection` |

---

## 5. Data layer migration (EF Core)

### 5.1 Tables ↔ entities (1:1, schema unchanged)

| SQLAlchemy table | EF Core entity |
|---|---|
| `symbols` | `Symbol` |
| `daily_prices` | `DailyPrice` |
| `corporate_actions` | `CorporateAction` |
| `daily_indicators` | `DailyIndicator` |
| `daily_heikin_ashi` | `DailyHeikinAshi` |
| `renko_bricks` | `RenkoBrick` |
| `line_break_lines` | `LineBreakLine` |
| `screening_snapshots` | `ScreeningSnapshot` |
| `sync_jobs` | `SyncJob` |
| `symbol_sync_state` | `SymbolSyncState` |
| `app_settings` | `AppSetting` |

### 5.2 Type mapping

| Python/SQLAlchemy | C#/EF Core | Notes |
|---|---|---|
| `String(n)` | `string` + `.HasMaxLength(n)` | |
| `Numeric(18,4)` | `decimal` + `.HasPrecision(18,4)` | exact for prices |
| `Float` | `double?` | indicators |
| `BIGINT` | `long` | volume |
| `Boolean` | `bool` | SQLite stores as INTEGER |
| `Date` | `DateOnly` | trading_date |
| `DateTime` | `DateTime` | timestamps |

### 5.3 Reuse the existing DB (zero data migration)

Schema is identical, so EF Core points at the **same SQLite file** (or SQL Server DB). Scaffold from the live DB to bootstrap entities:

```bash
dotnet ef dbcontext scaffold "Data Source=../../python/data/vajra.db" \
  Microsoft.EntityFrameworkCore.Sqlite -o Data/Entities --context VajraDbContext \
  --use-database-names
```

Then hand-tune precision/relationships and add `EFCore.NamingConventions` →
`.UseSnakeCaseNamingConvention()` so C# `PascalCase` properties map to the
existing `snake_case` columns automatically.

---

## 6. API migration (REST → REST, like-for-like)

Every FastAPI route maps to an ASP.NET controller action at the **same path**, returning the **same snake_case JSON**.

| FastAPI route | ASP.NET controller action |
|---|---|
| `GET /api/v1/symbols` | `SymbolsController.List` |
| `GET /api/v1/symbols/{symbol}` | `SymbolsController.Get` |
| `GET /api/v1/charts/{symbol}/candles` | `ChartsController.Candles` |
| `GET /api/v1/charts/{symbol}/heikin-ashi` | `ChartsController.HeikinAshi` |
| `GET /api/v1/charts/{symbol}/renko` | `ChartsController.Renko` |
| `GET /api/v1/charts/{symbol}/line-break` | `ChartsController.LineBreak` |
| `GET /api/v1/indicators/{symbol}` | `IndicatorsController.Get` |
| `POST /api/v1/screeners/run` | `ScreenersController.Run` |
| `GET /api/v1/screeners` | `ScreenersController.RunQuery` |
| `POST /api/v1/sync/full` | `SyncController.Full` |
| `POST /api/v1/sync/symbol/{symbol}` | `SyncController.Symbol` |
| `GET /api/v1/sync/jobs` | `SyncController.Jobs` |
| `GET /api/v1/sync/status` | `SyncController.Status` |
| `GET /api/v1/agents/chat-stream` (SSE) | `AgentsController.ChatStream` (**SSE**) |
| `GET /api/v1/settings` | `SettingsController.GetAll` |
| `PUT /api/v1/settings/{cat}/{key}` | `SettingsController.Update` |
| `GET /api/v1/setup/status` | `SetupController.Status` |
| `POST /api/v1/setup/initialize` | `SetupController.Initialize` |

**Frontend impact: none.** The React `services/api.ts` keeps the exact same URLs; the agent console keeps its `EventSource`.

---

## 7. Yahoo Finance in .NET (no paid APIs)

**Option A — Native .NET HTTP client (recommended).** Call Yahoo's chart endpoints with `HttpClient`:
```
https://query1.finance.yahoo.com/v8/finance/chart/RELIANCE.NS?range=3y&interval=1d&events=div,split
```
Parse JSON to OHLCV + actions. No account, no paid tier. Replaces yfinance `download()`.

**Option B — Python sidecar (fallback).** If a niche yfinance feature (e.g. `ticker.info` sector enrichment) is hard to replicate, keep a tiny Python REST microservice for just that, called from .NET.

> Honest note: the .NET client hits the same unofficial Yahoo endpoints as yfinance — same reliability, same risk of Yahoo changing things. Isolate behind `IMarketDataProvider` so it's swappable.

Indicators via `Skender.Stock.Indicators` (validate against pandas-ta — see §11).

---

## 8. Microsoft Agent Framework — Python → .NET

| Python (`agent_framework`) | .NET (`Microsoft.Agents.AI`) |
|---|---|
| `Agent(client=..., instructions=...)` | `ChatClientAgent` / `AIAgent` |
| `OllamaChatClient` | `OllamaChatClient` (or `IChatClient` via `OllamaSharp`) |
| `WorkflowBuilder` / `FunctionExecutor` | MAF `Workflow` + executors, or a sequential C# pipeline |
| `@tool` functions | `[Description]` methods registered as `AIFunction` |
| `agent.run(prompt)` | `await agent.RunAsync(prompt)` |
| `response_format=json` | `ChatOptions { ResponseFormat = ChatResponseFormat.Json }` |

The orchestrator DAG (intent → DB fetch → analysis → trade plan → report) becomes a sequential pipeline of agent calls with deterministic C# services (trade-planner math, backtester) in between — exactly as today. Results stream out over **SSE** from `AgentsController.ChatStream`.

---

## 9. Background jobs — Hangfire

Replaces FastAPI `BackgroundTasks` AND adds the scheduling the Python app lacked:

```csharp
// Fire-and-forget (replaces BackgroundTasks)
BackgroundJob.Enqueue<ISyncService>(s => s.RunFullSyncAsync(null));

// Recurring (new — nightly EOD sync, weekdays 18:00)
RecurringJob.AddOrUpdate<ISyncService>(
    "nightly-sync", s => s.RunFullSyncAsync(null), "0 18 * * 1-5");
```

Persists jobs to the same DB, survives restarts, retries automatically, and ships a **`/hangfire` dashboard**.

---

## 10. Phased migration roadmap

### Phase A — Scaffold (parallel, no cutover)
- Create `dotnet/` solution: `Vajra.Api` (Web API host), `Vajra.Domain`, `Vajra.Data`, `Vajra.Agents`, `Vajra.MarketData`, `Vajra.Jobs`.
- EF Core `VajraDbContext` scaffolded from the existing DB; verify it reads the same data Python writes.
- Stand up `SymbolsController.List` returning the same JSON as FastAPI.
- **Exit:** `GET /api/v1/symbols` on .NET returns identical JSON to Python, same DB.

### Phase B — Read-only controllers
- Port `ChartsController`, `IndicatorsController`, `ScreenersController`, `SettingsController` (reads).
- Repoint `VITE_API_BASE_URL` to the .NET host; React reads now hit .NET.
- Python still owns sync/writes.
- **Exit:** Explorer, Screener, Compare tabs run entirely on .NET reads, no frontend code change.

### Phase C — Writes & jobs
- Port `SyncController` + `YahooFinanceProvider` + indicator/market-structure calculators (`Skender.Stock.Indicators`).
- Wire Hangfire for sync + recurring jobs.
- Port `SettingsController` writes, `SetupController`.
- **Exit:** A full NSE sync on .NET produces identical indicators/snapshots.

### Phase D — Agents (SSE)
- Port the orchestrator to MAF .NET + Ollama.
- Implement `AgentsController.ChatStream` as SSE (same event shape the React store already parses).
- **Exit:** All four workflows stream equivalent reports; AI console unchanged.

### Phase E — Cutover & cleanup
- Move Portfolio/Watchlist/Alerts to DB-backed controllers (also completes Python Phase 2).
- Serve the React build from ASP.NET `wwwroot`.
- Retire the Python backend (keep under `python/` as reference).
- **Exit:** Single .NET process serves UI + REST + agents + jobs. Python not needed at runtime.

---

## 11. Risk assessment

| Risk | Impact | Mitigation |
|---|---|---|
| JSON casing/shape drift breaks React | **High** | Enforce `SnakeCaseLower`; contract tests comparing .NET vs Python JSON per endpoint |
| `Skender.Stock.Indicators` ≠ pandas-ta values | High | Golden-master test per symbol; tolerance < 0.01 |
| decimal vs double rounding | Medium | `decimal` for prices, `double` for indicators; assert vs Python outputs |
| Yahoo endpoint shape changes | High | Isolate behind `IMarketDataProvider`; integration tests with recorded fixtures |
| SSE buffering/proxy issues | Low | Set `X-Accel-Buffering: no`, flush per event (same headers Python uses) |
| MAF .NET API differs from Python | Medium | Thin `IAgentOrchestrator` abstraction; port logic, not framework internals |
| Dual-write drift (Python + .NET) | Medium | DB is the single source of truth; one writer per capability at a time |
| EF Core vs existing schema mismatch | Medium | Scaffold from live DB; never let EF drop/recreate during transition |

---

## 12. Definition of done

- [ ] React frontend runs against .NET with **only `VITE_API_BASE_URL` changed**
- [ ] All REST routes return identical snake_case JSON to the Python backend
- [ ] Full NSE sync on .NET; indicators/snapshots match Python within tolerance
- [ ] AI console streams via SSE from MAF .NET + Ollama
- [ ] Hangfire runs the nightly sync; `/hangfire` dashboard available
- [ ] Single self-contained .NET process serves UI + REST (SQLite default)
- [ ] No paid external APIs introduced
- [ ] Python backend archived under `python/` as reference

See **IMPLEMENTATION_GUIDE.md** for concrete project structure, controllers, DTOs, EF Core, MAF, and SSE code.
