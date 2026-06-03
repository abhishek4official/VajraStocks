# VajraStocks — .NET Core Implementation Guide (REST)

_Concrete project structure, REST controllers, DTOs (snake_case), EF Core, MAF agents (SSE), Yahoo Finance, Hangfire, and frontend wiring._

Companion to **MIGRATION_GUIDE.md**. Target: **.NET 9**, ASP.NET Core Web API, EF Core, Microsoft Agent Framework.

---

## 1. Solution structure

```
dotnet/
├── VajraStocks.sln
├── docs/
│   ├── MIGRATION_GUIDE.md
│   └── IMPLEMENTATION_GUIDE.md
└── src/
    ├── Vajra.Api/                  # ASP.NET Core Web API host (entry point)
    │   ├── Program.cs
    │   ├── Controllers/
    │   │   ├── SymbolsController.cs
    │   │   ├── ChartsController.cs
    │   │   ├── IndicatorsController.cs
    │   │   ├── ScreenersController.cs
    │   │   ├── SyncController.cs
    │   │   ├── SettingsController.cs
    │   │   ├── SetupController.cs
    │   │   └── AgentsController.cs      # SSE streaming
    │   ├── Dtos/                        # snake_case response/request models
    │   ├── appsettings.json
    │   └── wwwroot/                     # React build output (Phase E)
    ├── Vajra.Domain/                    # pure domain logic (no I/O)
    │   ├── Indicators/                  # RSI, MACD, ATR, SMA, EMA, BB
    │   ├── MarketStructure/             # Heikin-Ashi, Renko, Line Break
    │   ├── Screening/                   # filters, RS score, pattern flags
    │   └── TradePlanning/               # ATR-based entry/stop/target
    ├── Vajra.Data/                      # EF Core
    │   ├── VajraDbContext.cs
    │   ├── Entities/
    │   └── Migrations/
    ├── Vajra.MarketData/                # Yahoo Finance client
    │   ├── IMarketDataProvider.cs
    │   └── YahooFinanceProvider.cs
    ├── Vajra.Agents/                    # Microsoft Agent Framework orchestration
    │   ├── IAgentOrchestrator.cs
    │   ├── AgentOrchestrator.cs
    │   └── Tools/
    └── Vajra.Jobs/                      # Hangfire jobs
        ├── SyncJob.cs
        └── SectorEnrichmentJob.cs
```

---

## 2. Host bootstrap — `Program.cs`

```csharp
using System.Text.Json;
using Hangfire;
using Microsoft.EntityFrameworkCore;
using Vajra.Data;

var builder = WebApplication.CreateBuilder(args);

// 1. Connection string: env var -> appsettings -> SQLite default
var conn = Environment.GetEnvironmentVariable("VAJRA_DB_URL")
    ?? builder.Configuration.GetConnectionString("Default")
    ?? "Data Source=../../python/data/vajra.db";

// 2. EF Core — SQLite default, SQL Server optional
builder.Services.AddDbContext<VajraDbContext>(opt =>
{
    if (conn.Contains("Server=", StringComparison.OrdinalIgnoreCase))
        opt.UseSqlServer(conn);
    else
        opt.UseSqlite(conn.StartsWith("Data Source") ? conn : $"Data Source={conn}");
});

// 3. Controllers + snake_case JSON (matches the React types exactly)
builder.Services.AddControllers().AddJsonOptions(o =>
{
    o.JsonSerializerOptions.PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower;
    o.JsonSerializerOptions.DictionaryKeyPolicy = JsonNamingPolicy.SnakeCaseLower;
    o.JsonSerializerOptions.DefaultIgnoreCondition =
        System.Text.Json.Serialization.JsonIgnoreCondition.Never; // keep nulls like Pydantic
});

// 4. CORS (local dev; tighten later)
builder.Services.AddCors(o => o.AddPolicy("web", p =>
    p.AllowAnyOrigin().AllowAnyMethod().AllowAnyHeader()));

// 5. Domain & infrastructure
builder.Services.AddHttpClient<IMarketDataProvider, YahooFinanceProvider>();
builder.Services.AddScoped<IIndicatorService, IndicatorService>();
builder.Services.AddScoped<IScreeningService, ScreeningService>();
builder.Services.AddScoped<ISettingsService, SettingsService>();
builder.Services.AddScoped<ISyncService, SyncService>();
builder.Services.AddScoped<IAgentOrchestrator, AgentOrchestrator>();

// 6. Ollama chat client (local LLM, no paid API)
builder.Services.AddSingleton<Microsoft.Extensions.AI.IChatClient>(_ =>
    new OllamaChatClient(new Uri("http://localhost:11434"), "qwen2.5-coder:7b"));

// 7. Hangfire (jobs persisted to the same DB)
builder.Services.AddHangfire(c => c.UseSQLiteStorage(conn));
builder.Services.AddHangfireServer();

var app = builder.Build();

// Ensure schema + seed settings (mirrors the Python lifespan, idempotent)
using (var scope = app.Services.CreateScope())
{
    var db = scope.ServiceProvider.GetRequiredService<VajraDbContext>();
    db.Database.EnsureCreated();              // or db.Database.Migrate();
    SettingsSeeder.SeedDefaults(db);          // seed app_settings if empty
}

app.UseCors("web");
app.MapControllers();

// Hangfire dashboard + recurring jobs
app.UseHangfireDashboard("/hangfire");
RecurringJob.AddOrUpdate<Vajra.Jobs.SyncJob>(
    "nightly-sync", j => j.RunFullAsync(null), "0 18 * * 1-5");

// Serve React build (Phase E)
app.UseDefaultFiles();
app.UseStaticFiles();
app.MapFallbackToFile("index.html");

app.Run();
```

---

## 3. DTOs — snake_case (must match React types)

```csharp
// Vajra.Api/Dtos/ScreenerRowDto.cs
// Property names are PascalCase in C#; the SnakeCaseLower policy emits
// "close_price", "rs_score_1m", "is_gap_up", ... matching frontend/src/services/api.ts
public record ScreenerRowDto
{
    public int SymbolId { get; init; }
    public string Symbol { get; init; } = "";
    public string CompanyName { get; init; } = "";
    public string LastTradingDate { get; init; } = "";   // "yyyy-MM-dd"
    public double ClosePrice { get; init; }
    public double? PricePctChange { get; init; }
    public long Volume { get; init; }
    public double HaClose { get; init; }
    public string HaDirection { get; init; } = "UP";
    public double? Rsi14 { get; init; }
    public string? Sma20CrossDirection { get; init; }
    public string? Sma50CrossDirection { get; init; }
    public string? Sma200CrossDirection { get; init; }
    public string? MacdTrend { get; init; }
    public string? RenkoDirection { get; init; }
    public string? LineBreakDirection { get; init; }
    public bool? IsNr7 { get; init; }
    public bool? IsInsideBar { get; init; }
    public bool? IsGapUp { get; init; }
    public bool? IsGapDown { get; init; }
    public double? RsScore1m { get; init; }
    public double? WeeklyAvgVolume { get; init; }
    public double? VolumeBreakoutRatio { get; init; }
}

// Request body for POST /api/v1/screeners/run (snake_case in -> bound here)
public record ScreenerRequestDto
{
    public double? MinRsi { get; init; }
    public double? MaxRsi { get; init; }
    public double? MinPrice { get; init; }
    public double? MaxPrice { get; init; }
    public string? Sma200Cross { get; init; }     // "ABOVE" | "BELOW"
    public string? RenkoDir { get; init; }         // "UP" | "DOWN"
    public string? VolumeBreakout { get; init; }   // "1.5X" | "2.0X" | "3.0X"
    public bool OnlyNr7 { get; init; }
    public bool OnlyInsideBar { get; init; }
    public bool OnlyGapUp { get; init; }
    public bool OnlyGapDown { get; init; }
    public double? MinRs1m { get; init; }
    public int Limit { get; init; } = 2500;
}
```

> Tip: a contract test deserializes a recorded Python response and asserts the
> .NET DTO serializes to the same JSON keys — catches casing drift immediately.

---

## 4. Controllers — REST, same paths

```csharp
// Vajra.Api/Controllers/SymbolsController.cs
[ApiController]
[Route("api/v1/symbols")]
public class SymbolsController : ControllerBase
{
    private readonly VajraDbContext _db;
    public SymbolsController(VajraDbContext db) => _db = db;

    [HttpGet]
    public async Task<IEnumerable<SymbolDetailDto>> List([FromQuery] bool active_only = true)
    {
        var q = _db.Symbols.AsQueryable();
        if (active_only) q = q.Where(s => s.IsActive);
        return await q.OrderBy(s => s.Symbol).Select(s => new SymbolDetailDto { /* map */ }).ToListAsync();
    }

    [HttpGet("{symbol}")]
    public async Task<ActionResult<SymbolDetailDto>> Get(string symbol)
    {
        var clean = symbol.ToUpper().EndsWith(".NS") || symbol.StartsWith("^")
            ? symbol.ToUpper() : $"{symbol.ToUpper()}.NS";
        var s = await _db.Symbols.FirstOrDefaultAsync(x => x.Symbol == clean);
        return s is null ? NotFound(new { detail = $"Symbol '{symbol}' not found." })
                         : new SymbolDetailDto { /* map */ };
    }
}
```

```csharp
// Vajra.Api/Controllers/ScreenersController.cs
[ApiController]
[Route("api/v1/screeners")]
public class ScreenersController : ControllerBase
{
    private readonly IScreeningService _screening;
    public ScreenersController(IScreeningService s) => _screening = s;

    [HttpPost("run")]
    public async Task<IEnumerable<ScreenerRowDto>> Run([FromBody] ScreenerRequestDto req)
        => await _screening.QueryAsync(req);

    [HttpGet]                                  // GET variant with query params
    public async Task<IEnumerable<ScreenerRowDto>> RunQuery(
        [FromQuery] double? min_rsi, [FromQuery] double? max_rsi,
        [FromQuery] bool only_gap_up = false, [FromQuery] double? min_rs_1m = null,
        [FromQuery] int limit = 2500)
        => await _screening.QueryAsync(new ScreenerRequestDto {
               MinRsi = min_rsi, MaxRsi = max_rsi, OnlyGapUp = only_gap_up,
               MinRs1m = min_rs_1m, Limit = limit });
}
```

---

## 5. EF Core — entity + DbContext

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

    public VajraDbContext(DbContextOptions<VajraDbContext> o) : base(o) { }

    protected override void OnModelCreating(ModelBuilder b)
    {
        b.Entity<DailyPrice>(e =>
        {
            e.ToTable("daily_prices");
            e.Property(x => x.Open).HasPrecision(18, 4);
            e.Property(x => x.High).HasPrecision(18, 4);
            e.Property(x => x.Low).HasPrecision(18, 4);
            e.Property(x => x.Close).HasPrecision(18, 4);
        });
        b.Entity<ScreeningSnapshot>(e =>
        {
            e.ToTable("screening_snapshots");
            e.HasKey(x => x.SymbolId);
            e.Property(x => x.ClosePrice).HasPrecision(12, 4);
        });
    }
}
```

Add `EFCore.NamingConventions` and call `.UseSnakeCaseNamingConvention()` in
`AddDbContext` so PascalCase properties map to the existing snake_case columns
without per-column `HasColumnName`.

---

## 6. Agents — MAF .NET over SSE (same event shape React already parses)

The React store parses events like `{ "event": "agent_active", "data": {...} }`.
Emit the **same** envelope from an SSE controller.

```csharp
// Vajra.Api/Controllers/AgentsController.cs
[ApiController]
[Route("api/v1/agents")]
public class AgentsController : ControllerBase
{
    private readonly IAgentOrchestrator _orchestrator;
    public AgentsController(IAgentOrchestrator o) => _orchestrator = o;

    [HttpGet("chat-stream")]
    public async Task ChatStream([FromQuery] string prompt, CancellationToken ct)
    {
        Response.Headers.CacheControl = "no-cache, no-transform";
        Response.Headers["X-Accel-Buffering"] = "no";
        Response.ContentType = "text/event-stream";

        await foreach (var ev in _orchestrator.ExecuteWorkflowAsync(prompt, ct))
        {
            var payload = JsonSerializer.Serialize(new { @event = ev.Type, data = ev.Data },
                new JsonSerializerOptions { PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower });
            await Response.WriteAsync($"data: {payload}\n\n", ct);
            await Response.Body.FlushAsync(ct);
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
    private readonly IChatClient _chat;
    public AgentOrchestrator(IChatClient chat) => _chat = chat;

    public async IAsyncEnumerable<WorkflowEvent> ExecuteWorkflowAsync(
        string prompt, [EnumeratorCancellation] CancellationToken ct)
    {
        yield return new("started", new { status = "Parsing query..." });

        var orchestrator = new ChatClientAgent(_chat, new()
        {
            Instructions = "Classify the stock query into intent + symbol. Reply JSON.",
        });
        var intentResult = await orchestrator.RunAsync(prompt, cancellationToken: ct);
        // route: analyze_stock / breakout_scan / market_regime / swing_trade_scan
        // call deterministic C# services (trade planner, backtester) between steps
        // yield "agent_active" events per step

        yield return new("complete", new {
            report = "# RELIANCE.NS Report\n...", recommendation = "BULLISH", confidence = "HIGH" });
    }
}
```

The React `EventSource` + the store's event handling stay **exactly as they are**.

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
var rsi  = quotes.GetRsi(14).Last().Rsi;
var macd = quotes.GetMacd(12, 26, 9).Last();
var atr  = quotes.GetAtr(14).Last().Atr;
var bb   = quotes.GetBollingerBands(20, 2).Last();
```
Validate against Python pandas-ta outputs (golden-master test, tolerance < 0.01).

---

## 8. Hangfire job

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
            // validate -> upsert daily_prices
            // compute indicators + market structures -> upsert
        }
        await _screening.RefreshAllSnapshotsAsync();
    }
}
```

---

## 9. Frontend wiring — essentially zero change

The React app keeps `fetch()` and `EventSource`. The only change is the base URL:

```
# frontend/.env
VITE_API_BASE_URL=http://localhost:8000     # now the .NET host
```

`services/api.ts`, the Zustand store, the AI console, and all components are
**unchanged**. The contract (paths + snake_case JSON + SSE event envelope) is
preserved by:
- `JsonNamingPolicy.SnakeCaseLower` (responses)
- controllers mapped to the same `/api/v1/...` routes
- the SSE controller emitting `data: {"event": "...", "data": {...}}\n\n`

---

## 10. Local run & packaging

```bash
# Dev
dotnet run --project src/Vajra.Api          # REST on :8000, serves wwwroot

# Publish self-contained single-file (Windows, no .NET install needed)
dotnet publish src/Vajra.Api -c Release -r win-x64 \
  --self-contained -p:PublishSingleFile=true -o ../dist/win
```

`install.ps1` / `start.ps1` adapt to launch `Vajra.Api.exe` instead of uvicorn.
SQLite stays at `data/vajra.db` (shared with, or migrated from, the Python build).

---

## 11. NuGet dependencies

| Package | Purpose |
|---|---|
| `Microsoft.AspNetCore.OpenApi` | REST API + Swagger |
| `Microsoft.EntityFrameworkCore.Sqlite` | SQLite provider |
| `Microsoft.EntityFrameworkCore.SqlServer` | SQL Server option |
| `EFCore.NamingConventions` | snake_case column mapping |
| `Hangfire.AspNetCore` + `Hangfire.Storage.SQLite` | jobs + dashboard |
| `Microsoft.Agents.AI` | Microsoft Agent Framework (.NET) |
| `Microsoft.Extensions.AI` | `IChatClient` abstraction |
| `OllamaSharp` | Ollama client (local LLM) |
| `Skender.Stock.Indicators` | RSI/MACD/ATR/BB/SMA/EMA |
| `Serilog.AspNetCore` | logging |
| `FluentValidation.AspNetCore` | request validation |

---

## 12. Parity checklist (per controller)

- [ ] `SymbolsController` — list/detail JSON byte-identical to Python
- [ ] `ChartsController` — candles/HA/renko/line-break same ordering & values
- [ ] `IndicatorsController` — RSI/MACD/ATR/SMA/EMA/BB within tolerance vs pandas-ta
- [ ] `ScreenersController` — all filters incl. NR7/InsideBar/Gap/RS produce same rows
- [ ] `SyncController` + `YahooFinanceProvider` — full sync yields identical snapshots
- [ ] `AgentsController` — four workflows stream equivalent SSE reports via MAF .NET
- [ ] `SettingsController` / `SetupController` — DB-backed settings parity
- [ ] Hangfire nightly sync runs; `/hangfire` dashboard reachable
- [ ] React app runs against .NET with only `VITE_API_BASE_URL` changed
```
