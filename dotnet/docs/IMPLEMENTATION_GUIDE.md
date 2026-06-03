# VajraStocks — .NET Core Implementation Guide

_Concrete project structure, `.proto` contracts, EF Core models, gRPC services, MAF agents, and frontend wiring._

Companion to **MIGRATION_GUIDE.md**. Target: **.NET 9**, ASP.NET Core, gRPC, EF Core, Microsoft Agent Framework.

---

## 1. Solution structure

```
dotnet/
├── VajraStocks.sln
├── docs/
│   ├── MIGRATION_GUIDE.md
│   └── IMPLEMENTATION_GUIDE.md
├── protos/                         # contract-first .proto files (shared)
│   ├── common.proto
│   ├── symbols.proto
│   ├── charts.proto
│   ├── indicators.proto
│   ├── screener.proto
│   ├── sync.proto
│   ├── settings.proto
│   ├── setup.proto
│   └── agents.proto
└── src/
    ├── Vajra.Api/                  # ASP.NET Core gRPC host (entry point)
    │   ├── Program.cs
    │   ├── Services/               # gRPC service implementations
    │   │   ├── SymbolGrpcService.cs
    │   │   ├── ChartGrpcService.cs
    │   │   ├── ScreenerGrpcService.cs
    │   │   ├── SyncGrpcService.cs
    │   │   ├── SettingsGrpcService.cs
    │   │   ├── SetupGrpcService.cs
    │   │   └── AgentGrpcService.cs
    │   ├── appsettings.json
    │   └── wwwroot/                # React build output (Phase E)
    ├── Vajra.Domain/               # pure domain logic (no I/O)
    │   ├── Indicators/             # RSI, MACD, ATR, SMA, EMA, BB
    │   ├── MarketStructure/        # Heikin-Ashi, Renko, Line Break
    │   ├── Screening/              # filters, RS score, pattern flags
    │   └── TradePlanning/          # ATR-based entry/stop/target
    ├── Vajra.Data/                 # EF Core
    │   ├── VajraDbContext.cs
    │   ├── Entities/
    │   └── Migrations/
    ├── Vajra.MarketData/           # Yahoo Finance client
    │   ├── IMarketDataProvider.cs
    │   └── YahooFinanceProvider.cs
    ├── Vajra.Agents/               # Microsoft Agent Framework orchestration
    │   ├── IAgentOrchestrator.cs
    │   ├── AgentOrchestrator.cs
    │   └── Tools/                  # AIFunction tools
    └── Vajra.Jobs/                 # Hangfire job definitions
        ├── SyncJob.cs
        └── SectorEnrichmentJob.cs
```

---

## 2. Proto contracts

### `protos/common.proto`
```protobuf
syntax = "proto3";
option csharp_namespace = "Vajra.Grpc";
package vajra;

message Empty {}

enum Direction { DIRECTION_UNSPECIFIED = 0; UP = 1; DOWN = 2; }
enum CrossPosition { CROSS_UNSPECIFIED = 0; ABOVE = 1; BELOW = 2; }
```

### `protos/symbols.proto`
```protobuf
syntax = "proto3";
option csharp_namespace = "Vajra.Grpc";
package vajra;

service SymbolService {
  rpc ListSymbols(ListSymbolsRequest) returns (ListSymbolsResponse);
  rpc GetSymbol(GetSymbolRequest) returns (SymbolDetail);
}

message ListSymbolsRequest { bool active_only = 1; }
message ListSymbolsResponse { repeated SymbolDetail symbols = 1; }
message GetSymbolRequest { string symbol = 1; }

message SymbolDetail {
  int32 id = 1;
  string symbol = 2;
  string company_name = 3;
  string isin = 4;
  string series = 5;
  bool is_active = 6;
  string last_successful_sync_date = 7;
  string last_attempt_status = 8;
}
```

### `protos/screener.proto`
```protobuf
syntax = "proto3";
option csharp_namespace = "Vajra.Grpc";
package vajra;
import "common.proto";

service ScreenerService {
  rpc RunScreener(ScreenerRequest) returns (ScreenerResponse);
}

message ScreenerRequest {
  optional double min_rsi = 1;
  optional double max_rsi = 2;
  optional double min_price = 3;
  optional double max_price = 4;
  optional CrossPosition sma_200_cross = 5;
  optional Direction renko_dir = 6;
  optional string volume_breakout = 7;     // "1.5X" | "2.0X" | "3.0X"
  optional bool only_nr7 = 8;
  optional bool only_inside_bar = 9;
  optional bool only_gap_up = 10;
  optional bool only_gap_down = 11;
  optional double min_rs_1m = 12;
  int32 limit = 13;
}

message ScreenerResponse { repeated ScreenerRow rows = 1; }

message ScreenerRow {
  int32 symbol_id = 1;
  string symbol = 2;
  string company_name = 3;
  double close_price = 4;
  optional double price_pct_change = 5;
  int64 volume = 6;
  optional double rsi_14 = 7;
  optional string renko_direction = 8;
  optional bool is_gap_up = 9;
  optional bool is_gap_down = 10;
  optional double rs_score_1m = 11;
  // ... remaining snapshot fields
}
```

### `protos/agents.proto` (server-streaming — replaces SSE)
```protobuf
syntax = "proto3";
option csharp_namespace = "Vajra.Grpc";
package vajra;

service AgentService {
  rpc ChatStream(ChatRequest) returns (stream AgentEvent);
}

message ChatRequest { string prompt = 1; }

message AgentEvent {
  string event_type = 1;   // "started" | "agent_active" | "complete" | "error"
  string agent = 2;
  string status = 3;
  string report = 4;       // markdown, on "complete"
  string recommendation = 5;
  string confidence = 6;
}
```

---

## 3. Host bootstrap — `Program.cs`

```csharp
using Hangfire;
using Microsoft.EntityFrameworkCore;
using Vajra.Api.Services;
using Vajra.Data;

var builder = WebApplication.CreateBuilder(args);

// 1. Configuration: appsettings.json + DB-backed settings (DB wins at runtime)
var connString = builder.Configuration.GetConnectionString("Default")
    ?? "Data Source=../../data/vajra.db";

// 2. EF Core — SQLite default, SQL Server optional
builder.Services.AddDbContext<VajraDbContext>(opt =>
{
    if (connString.Contains("Server=", StringComparison.OrdinalIgnoreCase))
        opt.UseSqlServer(connString);
    else
        opt.UseSqlite(connString);
});

// 3. gRPC + gRPC-Web
builder.Services.AddGrpc();
builder.Services.AddCors(o => o.AddPolicy("web", p =>
    p.AllowAnyOrigin().AllowAnyMethod().AllowAnyHeader()
     .WithExposedHeaders("Grpc-Status", "Grpc-Message", "Grpc-Encoding", "Grpc-Accept-Encoding")));

// 4. Domain & infrastructure services
builder.Services.AddScoped<IMarketDataProvider, YahooFinanceProvider>();
builder.Services.AddScoped<IIndicatorService, IndicatorService>();
builder.Services.AddScoped<IScreeningService, ScreeningService>();
builder.Services.AddScoped<ISettingsService, SettingsService>();
builder.Services.AddScoped<IAgentOrchestrator, AgentOrchestrator>();

// 5. Hangfire (jobs persisted to the same DB)
builder.Services.AddHangfire(cfg => cfg.UseSqliteStorage(connString));
builder.Services.AddHangfireServer();

var app = builder.Build();

// Ensure schema exists (idempotent — mirrors the Python lifespan behavior)
using (var scope = app.Services.CreateScope())
{
    var db = scope.ServiceProvider.GetRequiredService<VajraDbContext>();
    db.Database.EnsureCreated();           // or db.Database.Migrate();
    SettingsSeeder.SeedDefaults(db);       // seed app_settings if empty
}

app.UseRouting();
app.UseCors("web");
app.UseGrpcWeb(new GrpcWebOptions { DefaultEnabled = true });

// Map gRPC services
app.MapGrpcService<SymbolGrpcService>().EnableGrpcWeb();
app.MapGrpcService<ChartGrpcService>().EnableGrpcWeb();
app.MapGrpcService<ScreenerGrpcService>().EnableGrpcWeb();
app.MapGrpcService<SyncGrpcService>().EnableGrpcWeb();
app.MapGrpcService<SettingsGrpcService>().EnableGrpcWeb();
app.MapGrpcService<SetupGrpcService>().EnableGrpcWeb();
app.MapGrpcService<AgentGrpcService>().EnableGrpcWeb();

// Hangfire dashboard
app.UseHangfireDashboard("/hangfire");

// Recurring jobs
RecurringJob.AddOrUpdate<SyncJob>("nightly-sync",
    j => j.RunFullAsync(null), "0 18 * * 1-5");

// Serve React build (Phase E)
app.UseDefaultFiles();
app.UseStaticFiles();
app.MapFallbackToFile("index.html");

app.Run();
```

---

## 4. EF Core — entity + DbContext sample

```csharp
// Vajra.Data/Entities/ScreeningSnapshot.cs
public class ScreeningSnapshot
{
    public int SymbolId { get; set; }
    public string Symbol { get; set; } = "";
    public string CompanyName { get; set; } = "";
    public DateOnly LastTradingDate { get; set; }
    public decimal ClosePrice { get; set; }
    public double? PricePctChange { get; set; }
    public long Volume { get; set; }
    public double? Rsi14 { get; set; }
    public string? Sma200CrossDirection { get; set; }
    public string? RenkoDirection { get; set; }
    public bool? IsNr7 { get; set; }
    public bool? IsInsideBar { get; set; }
    public bool? IsGapUp { get; set; }
    public bool? IsGapDown { get; set; }
    public double? RsScore1m { get; set; }
}

// Vajra.Data/VajraDbContext.cs
public class VajraDbContext : DbContext
{
    public DbSet<Symbol> Symbols => Set<Symbol>();
    public DbSet<DailyPrice> DailyPrices => Set<DailyPrice>();
    public DbSet<DailyIndicator> DailyIndicators => Set<DailyIndicator>();
    public DbSet<ScreeningSnapshot> ScreeningSnapshots => Set<ScreeningSnapshot>();
    public DbSet<AppSetting> AppSettings => Set<AppSetting>();
    // ... other tables

    public VajraDbContext(DbContextOptions<VajraDbContext> o) : base(o) { }

    protected override void OnModelCreating(ModelBuilder b)
    {
        b.Entity<ScreeningSnapshot>(e =>
        {
            e.ToTable("screening_snapshots");
            e.HasKey(x => x.SymbolId);
            e.Property(x => x.ClosePrice).HasPrecision(12, 4);
            e.Property(x => x.Symbol).HasColumnName("symbol").HasMaxLength(50);
            // map snake_case columns explicitly to match existing schema
        });

        b.Entity<DailyPrice>(e =>
        {
            e.ToTable("daily_prices");
            e.Property(x => x.Open).HasPrecision(18, 4);
            e.Property(x => x.High).HasPrecision(18, 4);
            e.Property(x => x.Low).HasPrecision(18, 4);
            e.Property(x => x.Close).HasPrecision(18, 4);
        });
    }
}
```

> Use a snake_case naming convention helper (e.g. `EFCore.NamingConventions` → `.UseSnakeCaseNamingConvention()`) so you don't hand-map every column.

---

## 5. gRPC service — Screener example

```csharp
public class ScreenerGrpcService : ScreenerService.ScreenerServiceBase
{
    private readonly IScreeningService _screening;
    public ScreenerGrpcService(IScreeningService screening) => _screening = screening;

    public override async Task<ScreenerResponse> RunScreener(
        ScreenerRequest req, ServerCallContext context)
    {
        var results = await _screening.QueryAsync(new ScreenerFilters
        {
            MinRsi = req.HasMinRsi ? req.MinRsi : null,
            MaxRsi = req.HasMaxRsi ? req.MaxRsi : null,
            MinPrice = req.HasMinPrice ? req.MinPrice : null,
            OnlyGapUp = req.OnlyGapUp,
            MinRs1m = req.HasMinRs1M ? req.MinRs1M : null,
            Limit = req.Limit == 0 ? 2500 : req.Limit,
        });

        var resp = new ScreenerResponse();
        resp.Rows.AddRange(results.Select(r => new ScreenerRow
        {
            SymbolId = r.SymbolId,
            Symbol = r.Symbol,
            CompanyName = r.CompanyName,
            ClosePrice = (double)r.ClosePrice,
            Volume = r.Volume,
            Rsi14 = r.Rsi14 ?? 0,
            IsGapUp = r.IsGapUp ?? false,
            RsScore1m = r.RsScore1m ?? 0,
        }));
        return resp;
    }
}
```

---

## 6. Agent service — MAF .NET + server streaming

```csharp
public class AgentGrpcService : AgentService.AgentServiceBase
{
    private readonly IAgentOrchestrator _orchestrator;
    public AgentGrpcService(IAgentOrchestrator o) => _orchestrator = o;

    public override async Task ChatStream(
        ChatRequest request,
        IServerStreamWriter<AgentEvent> responseStream,
        ServerCallContext context)
    {
        await foreach (var ev in _orchestrator.ExecuteWorkflowAsync(
                           request.Prompt, context.CancellationToken))
        {
            await responseStream.WriteAsync(new AgentEvent
            {
                EventType = ev.Type,
                Agent = ev.Agent ?? "",
                Status = ev.Status ?? "",
                Report = ev.Report ?? "",
                Recommendation = ev.Recommendation ?? "",
                Confidence = ev.Confidence ?? "",
            });
        }
    }
}
```

```csharp
// Vajra.Agents/AgentOrchestrator.cs — MAF .NET + Ollama
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;

public class AgentOrchestrator : IAgentOrchestrator
{
    private readonly IChatClient _chat;   // OllamaChatClient registered in DI

    public AgentOrchestrator(IChatClient chat) => _chat = chat;

    public async IAsyncEnumerable<WorkflowEvent> ExecuteWorkflowAsync(
        string prompt, [EnumeratorCancellation] CancellationToken ct)
    {
        yield return new WorkflowEvent { Type = "started", Status = "Parsing query..." };

        var orchestrator = new ChatClientAgent(_chat, new()
        {
            Instructions = "Classify the user's stock query into an intent and symbol.",
            // structured JSON output
        });

        var intent = await orchestrator.RunAsync(prompt, cancellationToken: ct);
        // ... route to analyze_stock / breakout_scan / market_regime / swing
        // call deterministic C# services (trade planner, backtester) between agent steps
        // yield agent_active events per step

        yield return new WorkflowEvent
        {
            Type = "complete",
            Report = "# RELIANCE.NS Report\n...",
            Recommendation = "BULLISH",
            Confidence = "HIGH",
        };
    }
}
```

Register the Ollama client (local, no paid API):
```csharp
builder.Services.AddSingleton<IChatClient>(_ =>
    new OllamaChatClient(new Uri("http://localhost:11434"), "qwen2.5-coder:7b"));
```

---

## 7. Yahoo Finance provider

```csharp
public interface IMarketDataProvider
{
    Task<IReadOnlyList<Candle>> GetDailyAsync(string yfSymbol, int years, CancellationToken ct);
}

public class YahooFinanceProvider : IMarketDataProvider
{
    private readonly HttpClient _http;
    public YahooFinanceProvider(HttpClient http) => _http = http;

    public async Task<IReadOnlyList<Candle>> GetDailyAsync(
        string yfSymbol, int years, CancellationToken ct)
    {
        var url = $"https://query1.finance.yahoo.com/v8/finance/chart/{yfSymbol}" +
                  $"?range={years}y&interval=1d&events=div,split";
        using var resp = await _http.GetAsync(url, ct);
        resp.EnsureSuccessStatusCode();
        var json = await resp.Content.ReadAsStringAsync(ct);
        return YahooChartParser.Parse(json);   // -> OHLCV + actions
    }
}
```

Indicators via `Skender.Stock.Indicators`:
```csharp
using Skender.Stock.Indicators;
var rsi = quotes.GetRsi(14).Last().Rsi;
var macd = quotes.GetMacd(12, 26, 9).Last();
var atr = quotes.GetAtr(14).Last().Atr;
var bb  = quotes.GetBollingerBands(20, 2).Last();
```
(Validate against the Python pandas-ta outputs — see migration §11 golden-master test.)

---

## 8. Hangfire jobs

```csharp
public class SyncJob
{
    private readonly IMarketDataProvider _market;
    private readonly VajraDbContext _db;
    private readonly IIndicatorService _indicators;
    private readonly IScreeningService _screening;

    public async Task RunFullAsync(string[]? symbols)
    {
        var active = await _db.Symbols.Where(s => s.IsActive).ToListAsync();
        foreach (var sym in active)
        {
            var candles = await _market.GetDailyAsync(sym.Symbol, 3, default);
            // validate → upsert daily_prices
            // compute indicators + market structures → upsert
        }
        await _screening.RefreshAllSnapshotsAsync();
    }
}
```

---

## 9. Frontend wiring (gRPC-Web)

Generate TS stubs with **`buf` + `protoc-gen-es`** (Connect) or `ts-proto`:

```bash
# buf.gen.yaml drives generation into frontend/src/gen
buf generate ../dotnet/protos
```

Replace the `apiService` fetch calls with typed gRPC clients:
```typescript
import { createConnectTransport } from "@connectrpc/connect-web";
import { createClient } from "@connectrpc/connect";
import { ScreenerService } from "./gen/screener_connect";

const transport = createConnectTransport({ baseUrl: import.meta.env.VITE_API_BASE_URL });
const screener = createClient(ScreenerService, transport);

const res = await screener.runScreener({ minRsi: 55, onlyGapUp: true, limit: 2500 });
```

The agent console consumes the server stream:
```typescript
for await (const ev of agentClient.chatStream({ prompt })) {
  if (ev.eventType === "complete") setReport(ev.report);
  else appendEvent(ev);
}
```

The Zustand store and React components stay the same — only the transport layer (`services/api.ts`) is swapped for generated gRPC clients.

---

## 10. Local run & packaging

```bash
# Dev
dotnet run --project src/Vajra.Api          # serves gRPC-Web on :8000

# Publish self-contained single-file (Windows, no .NET install needed)
dotnet publish src/Vajra.Api -c Release -r win-x64 \
  --self-contained -p:PublishSingleFile=true -o ../dist/win
```

`install.ps1` / `start.ps1` adapt to launch the published `Vajra.Api.exe` instead of uvicorn. SQLite file stays at `data/vajra.db`, shared with (or migrated from) the Python build.

---

## 11. NuGet dependencies

| Package | Purpose |
|---|---|
| `Grpc.AspNetCore` | gRPC server |
| `Grpc.AspNetCore.Web` | gRPC-Web for browsers |
| `Microsoft.EntityFrameworkCore.Sqlite` | SQLite provider |
| `Microsoft.EntityFrameworkCore.SqlServer` | SQL Server option |
| `EFCore.NamingConventions` | snake_case mapping |
| `Hangfire.AspNetCore` + `Hangfire.Storage.SQLite` | jobs + dashboard |
| `Microsoft.Agents.AI` | Microsoft Agent Framework (.NET) |
| `Microsoft.Extensions.AI` | `IChatClient` abstraction |
| `OllamaSharp` | Ollama client (local LLM) |
| `Skender.Stock.Indicators` | RSI/MACD/ATR/BB/SMA/EMA |
| `Serilog.AspNetCore` | logging |
| `FluentValidation` | request validation |

---

## 12. Parity checklist (per service)

- [ ] `SymbolService` — list/detail match Python JSON
- [ ] `ChartService` — candles/HA/renko/line-break identical ordering & values
- [ ] `IndicatorService` — RSI/MACD/ATR/SMA/EMA/BB within tolerance vs pandas-ta
- [ ] `ScreenerService` — all filters incl. NR7/InsideBar/Gap/RS produce same rows
- [ ] `SyncService` + `YahooFinanceProvider` — full sync yields identical snapshots
- [ ] `AgentService` — four workflows stream equivalent reports via MAF .NET
- [ ] `SettingsService` / `SetupService` — DB-backed settings parity
- [ ] Hangfire nightly sync runs; `/hangfire` dashboard reachable
- [ ] React app fully on gRPC-Web; single .NET process serves everything
