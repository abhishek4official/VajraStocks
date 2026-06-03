# VajraStocks — Migration Guide: Python/FastAPI → .NET Core (gRPC + Microsoft Agent Framework)

_Target stack: .NET 9, ASP.NET Core, gRPC, Entity Framework Core, Microsoft Agent Framework (.NET)_

---

## 1. Why migrate, and what stays the same

The current platform is a **local-first NSE stock analysis app** with:
- FastAPI REST backend (Python)
- React 19 + Vite frontend
- yfinance data pipeline → MSSQL/SQLite → indicators → screening snapshots
- Microsoft Agent Framework (Python) orchestrating Ollama-based multi-agent workflows

**What does NOT change:**
- The **React frontend** stays. Only its transport changes (REST → gRPC-Web).
- The **data model** (symbols, prices, indicators, snapshots, settings) is identical.
- The **local-first principle** — no paid APIs. Yahoo Finance remains the source.
- The **domain logic** (RSI/MACD/ATR, Heikin-Ashi, Renko, Line Break, screening, RS score, trade plans).

**What changes:**
- Backend language: Python → C# (.NET 9)
- API protocol: REST/JSON → **gRPC** (with gRPC-Web for the browser)
- ORM: SQLAlchemy + Alembic → **Entity Framework Core** + EF Migrations
- Agent runtime: `agent-framework` (Python) → **Microsoft Agent Framework for .NET**
- Background jobs: FastAPI BackgroundTasks → **Hangfire** or **IHostedService + Quartz.NET**

---

## 2. Guiding principles

1. **Strangler-fig migration.** Run .NET alongside Python. Move one capability at a time. The React app can talk to both during transition.
2. **Contract-first gRPC.** Define `.proto` files as the single source of truth for every API. Generate both server (C#) and client (TypeScript) stubs from them.
3. **Domain logic ported verbatim first, optimized later.** Get correct numbers before refactoring.
4. **Keep the database as the integration boundary.** During transition, both Python and .NET read/write the same DB schema. This de-risks cutover.
5. **No paid services.** Yahoo Finance via a .NET HTTP client (or call yfinance through a thin Python sidecar only if needed — see §7).

---

## 3. Target architecture

```
┌─────────────────────────────────────────────────────────────┐
│  React 19 + Vite frontend                                    │
│  (unchanged UI; transport via gRPC-Web + Connect/grpc-web)   │
└───────────────────────────────┬─────────────────────────────┘
                                 │  gRPC-Web (HTTP/2 or HTTP/1.1 framing)
┌────────────────────────────────▼────────────────────────────┐
│  ASP.NET Core (.NET 9) — single self-hosted process          │
│                                                              │
│  ├─ gRPC Services (Symbols, Charts, Screener, Sync,          │
│  │                 Portfolio, Watchlist, Settings, Agents)   │
│  ├─ Microsoft Agent Framework (.NET) — Ollama chat client    │
│  ├─ EF Core DbContext (SQLite default / SQL Server option)   │
│  ├─ Hangfire — scheduled & background jobs (sync, enrich)    │
│  ├─ Yahoo Finance data client (HttpClient)                   │
│  └─ Indicator/MarketStructure/Screening domain services      │
│                                                              │
│  Serves the React build as static files (wwwroot)            │
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
| API protocol | REST + Pydantic | gRPC + Protobuf messages |
| ORM | SQLAlchemy 2.0 | Entity Framework Core 9 |
| Migrations | Alembic | EF Core Migrations |
| DB providers | pyodbc / aiosqlite | `Microsoft.Data.SqlClient` / `Microsoft.Data.Sqlite` |
| Settings store | `app_settings` table + SettingsService | `AppSettings` entity + `ISettingsService` |
| Agents | `agent_framework` (Python) | `Microsoft.Agents.AI` (.NET) |
| LLM client | `agent_framework_ollama` | `OllamaChatClient` (MAF .NET) or `OllamaSharp` |
| Background jobs | `BackgroundTasks` | Hangfire (`BackgroundJob`, `RecurringJob`) |
| Data source | yfinance | `YahooFinanceClient` (HttpClient) |
| Indicators | pandas-ta | `Skender.Stock.Indicators` (NuGet) |
| Validation | Pydantic | FluentValidation / data annotations |
| Config | config.yaml + DB | `appsettings.json` + DB (DB wins) |
| Logging | loguru | Serilog |
| DI | manual constructors | built-in `IServiceCollection` |

---

## 5. Data layer migration (EF Core)

### 5.1 Entities ↔ models

Each SQLAlchemy model maps 1:1 to an EF Core entity. The schema is unchanged, so EF Core can be pointed at the **existing database**.

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

Because the schema is identical, point EF Core at the **same SQLite file** (or SQL Server DB) the Python app uses. Use **`dotnet ef migrations add InitialCreate`** with the model, then **`--idempotent`** scripts, OR scaffold from the existing DB:

```bash
dotnet ef dbcontext scaffold "Data Source=../data/vajra.db" \
  Microsoft.EntityFrameworkCore.Sqlite -o Data/Entities --context VajraDbContext
```

This generates entities matching the live schema — then hand-tune relationships and precision.

---

## 6. API migration (REST → gRPC)

### 6.1 Endpoint → RPC mapping

| REST (current) | gRPC service.method |
|---|---|
| `GET /api/v1/symbols` | `SymbolService.ListSymbols` |
| `GET /api/v1/symbols/{symbol}` | `SymbolService.GetSymbol` |
| `GET /api/v1/charts/{symbol}/candles` | `ChartService.GetCandles` |
| `GET /api/v1/charts/{symbol}/heikin-ashi` | `ChartService.GetHeikinAshi` |
| `GET /api/v1/charts/{symbol}/renko` | `ChartService.GetRenko` |
| `GET /api/v1/charts/{symbol}/line-break` | `ChartService.GetLineBreak` |
| `GET /api/v1/indicators/{symbol}` | `IndicatorService.GetIndicators` |
| `POST /api/v1/screeners/run` | `ScreenerService.RunScreener` |
| `POST /api/v1/sync/full` | `SyncService.RunFullSync` |
| `GET /api/v1/sync/jobs` | `SyncService.ListJobs` |
| `GET /api/v1/sync/status` | `SyncService.GetSymbolStatus` |
| `GET /api/v1/agents/chat-stream` (SSE) | `AgentService.ChatStream` (**server-streaming RPC**) |
| `GET /api/v1/settings` | `SettingsService.GetAll` |
| `PUT /api/v1/settings/{cat}/{key}` | `SettingsService.UpdateSetting` |
| `GET /api/v1/setup/status` | `SetupService.GetStatus` |
| `POST /api/v1/setup/initialize` | `SetupService.Initialize` |

### 6.2 The SSE → server-streaming win

The current AI console uses **Server-Sent Events** (`/agents/chat-stream`). gRPC has **first-class server streaming**, which is a cleaner fit:

```protobuf
service AgentService {
  rpc ChatStream(ChatRequest) returns (stream AgentEvent);
}
```

The browser consumes it via gRPC-Web streaming. No manual SSE parsing, typed events end-to-end.

### 6.3 Browser transport — gRPC-Web

Browsers can't speak raw gRPC (no HTTP/2 frame access). Use **gRPC-Web**:
- Server: `Grpc.AspNetCore.Web` middleware (`UseGrpcWeb()`)
- Client: `@connectrpc/connect-web` or `grpc-web` + `ts-proto` generated stubs

Server streaming (for the agent console) works over gRPC-Web with the Connect protocol.

---

## 7. Yahoo Finance in .NET (no paid APIs)

Two options, in order of preference:

**Option A — Native .NET HTTP client (recommended).**
Call Yahoo's chart endpoints directly with `HttpClient`:
```
https://query1.finance.yahoo.com/v8/finance/chart/RELIANCE.NS?range=3y&interval=1d&events=div,split
```
Parse JSON to OHLCV + actions. No third-party account. This replaces yfinance's `download()`.
NuGet helpers exist (e.g. `YahooFinanceApi`, `OoplesFinance.YahooFinanceAPI`) but a hand-rolled client avoids dependency drift.

**Option B — Python sidecar (fallback).**
If a specific yfinance capability is hard to replicate (e.g. `ticker.info` sector enrichment), keep a tiny Python microservice exposing just that over gRPC, called from .NET. Use only where Option A is impractical.

> Honest note: yfinance is an unofficial scrape. The .NET HTTP approach hits the same endpoints, so reliability is equivalent — and equally subject to Yahoo changing things. Pin behavior behind an `IMarketDataProvider` interface so it can be swapped.

---

## 8. Microsoft Agent Framework — Python → .NET

The MAF .NET SDK mirrors the Python concepts:

| Python (`agent_framework`) | .NET (`Microsoft.Agents.AI`) |
|---|---|
| `Agent(client=..., instructions=...)` | `ChatClientAgent` / `AIAgent` |
| `OllamaChatClient` | `OllamaChatClient` (or `IChatClient` via `OllamaSharp`) |
| `WorkflowBuilder` / `FunctionExecutor` | `Workflow` + executors (MAF .NET workflows) |
| `@tool` functions | `[Description]`-annotated methods registered as `AIFunction` |
| `agent.run(prompt)` | `await agent.RunAsync(prompt)` |
| structured `response_format=json` | `ChatOptions { ResponseFormat = ChatResponseFormat.Json }` |

The orchestrator's DAG (intent → DB fetch → analysis → trade plan → report) maps to a MAF .NET **Workflow** with typed executors, or a sequential pipeline of agent calls. The deterministic Python services (trade planner math, backtester) become plain C# services invoked between agent steps — same as today.

---

## 9. Background jobs — Hangfire

Replaces FastAPI `BackgroundTasks` AND adds scheduling the Python app lacked:

```csharp
// Fire-and-forget (replaces BackgroundTasks)
BackgroundJob.Enqueue<ISyncService>(s => s.RunFullSyncAsync(null));

// Recurring (new capability — nightly EOD sync)
RecurringJob.AddOrUpdate<ISyncService>(
    "nightly-sync", s => s.RunFullSyncAsync(null), "0 18 * * 1-5"); // weekdays 18:00
```

Hangfire persists jobs to the same DB (SQLite/SQL Server), survives restarts, retries automatically, and ships a **`/hangfire` dashboard** — the Hangfire equivalent the user asked about, native to .NET.

---

## 10. Phased migration roadmap

### Phase A — Scaffold (parallel, no cutover)
- Create `dotnet/` solution: `Vajra.Api` (gRPC host), `Vajra.Domain`, `Vajra.Data`, `Vajra.Agents`, `Vajra.MarketData`.
- EF Core `VajraDbContext` scaffolded from the existing DB. Verify it reads the same data Python writes.
- Stand up an empty gRPC host serving `SymbolService.ListSymbols` from the shared DB.
- **Exit criteria:** .NET returns the same symbol list as Python, reading the same DB.

### Phase B — Read-only services
- Port `ChartService`, `IndicatorService`, `ScreenerService`, `SettingsService` (read paths).
- Generate TS gRPC-Web stubs; switch the React **read** calls (charts, screener, symbols) to gRPC.
- Python still owns sync/writes.
- **Exit criteria:** Explorer, Screener, Compare tabs run entirely on .NET reads.

### Phase C — Write & jobs
- Port `SyncService` + Yahoo Finance client + indicator/market-structure calculators (`Skender.Stock.Indicators`).
- Wire Hangfire for sync + recurring jobs.
- Port `SettingsService` writes, `SetupService`.
- **Exit criteria:** A full NSE sync runs on .NET and produces identical indicators/snapshots.

### Phase D — Agents
- Port the orchestrator to MAF .NET with the Ollama chat client.
- Implement `AgentService.ChatStream` server-streaming RPC.
- Switch the AI Research console to gRPC-Web streaming.
- **Exit criteria:** All four workflows (analyze, breakout, regime, swing) produce equivalent reports.

### Phase E — Cutover & cleanup
- Move Portfolio/Watchlist/Alerts to DB-backed gRPC services (also completes the Python Phase 2).
- Serve the React build from ASP.NET `wwwroot`.
- Retire the Python backend (keep as reference under `python/`).
- **Exit criteria:** Single .NET process serves UI + APIs + agents + jobs. Python no longer required at runtime.

---

## 11. Risk assessment

| Risk | Impact | Mitigation |
|---|---|---|
| gRPC-Web server streaming quirks in browser | Medium | Use Connect protocol (`@connectrpc/connect-web`) — robust streaming + REST fallback |
| `Skender.Stock.Indicators` ≠ pandas-ta values | High | Golden-master test: compare .NET vs Python indicators per symbol; tolerance < 0.01 |
| Decimal vs double rounding differences | Medium | Use `decimal` for prices, `double` only for indicators; assert against Python outputs |
| Yahoo endpoint shape changes | High | Isolate behind `IMarketDataProvider`; integration tests with recorded fixtures |
| MAF .NET API surface differs from Python | Medium | Thin `IAgentOrchestrator` abstraction; port workflow logic, not framework internals |
| Dual-write period drift (Python + .NET) | Medium | Keep DB as single source of truth; only one writer per capability at a time |
| EF Core migration vs existing schema mismatch | Medium | Scaffold from live DB first; never let EF drop/recreate during transition |

---

## 12. Definition of done

- [ ] React frontend talks to .NET over gRPC-Web for all reads and writes
- [ ] Full NSE sync runs on .NET; indicators/snapshots match Python within tolerance
- [ ] AI console streams via gRPC server-streaming using MAF .NET + Ollama
- [ ] Hangfire runs the nightly sync and a `/hangfire` dashboard is available
- [ ] Single self-contained .NET process serves UI + APIs (SQLite default)
- [ ] No paid external APIs introduced
- [ ] Python backend archived under `python/` as reference

See **IMPLEMENTATION_GUIDE.md** for concrete project structure, `.proto` definitions, and code patterns.
