import React, { useEffect, useMemo, useState } from 'react';
import { useSettings } from './hooks/useSettings';
import { SettingsContext } from './contexts/SettingsContext';
import { useStockStore } from './store/useStockStore';
import { Sidebar } from './components/Sidebar';
import { PriceChart } from './components/PriceChart';
import { MetricsTable } from './components/MetricsTable';
import { CorporateActionsTimeline } from './components/CorporateActionsTimeline';
import { ScreenerPanel } from './components/ScreenerPanel';
import { SyncPanel } from './components/SyncPanel';
import { AgentTerminal } from './components/AgentTerminal';
import { PortfolioPanel } from './components/PortfolioPanel';
import { WatchlistPanel } from './components/WatchlistPanel';
import { TradePlanCard } from './components/TradePlanCard';
import { ComparePanel } from './components/ComparePanel';
import { SettingsPanel } from './components/SettingsPanel';
import { SetupWizard } from './components/SetupWizard';
import {
  LineChart,
  Search,
  Settings,
  Cpu,
  Layers,
  IndianRupee,
  Bookmark,
  TrendingUp,
} from 'lucide-react';
import './App.css';

// Thin wrapper: decides between loading / setup wizard / dashboard.
// Keeping this separate guarantees a stable hook order in Dashboard.
function App() {
  const [setupNeeded, setSetupNeeded] = React.useState<boolean | null>(null);
  // Single settings fetch shared by all child components via context
  const settingsState = useSettings();

  React.useEffect(() => {
    fetch(`${import.meta.env.VITE_API_BASE_URL}/api/v1/setup/status`)
      .then(r => r.json())
      .then(d => setSetupNeeded(d.setup_needed === true))
      .catch(() => setSetupNeeded(false));
  }, []);

  if (setupNeeded === null) return (
    <div className="min-h-screen bg-[#07080a] flex items-center justify-center text-slate-400 text-sm">
      Starting VajraStocks…
    </div>
  );

  if (setupNeeded) return <SetupWizard onComplete={() => setSetupNeeded(false)} />;

  return (
    <SettingsContext.Provider value={settingsState}>
      <Dashboard />
    </SettingsContext.Provider>
  );
}

function Dashboard() {
  const {
    activeTab,
    setActiveTab,
    chartType,
    setChartType,
    chartTimeframe,
    setChartTimeframe,
    chartOverlays,
    toggleChartOverlay,
    activeSymbol,
    activeSymbolDetail,
    candles,
    niftyCandles,
    fetchSymbols,
    fetchNiftyCandles,
    isLoading,
    addToWatchlist,
    watchlists,
    customLines,
    addCustomLine,
    removeCustomLines,
  } = useStockStore();

  const [indicatorToShow, setIndicatorToShow] = useState<'RSI' | 'MACD' | 'NONE'>('RSI');
  const [drawMode, setDrawMode] = useState(false);

  // Compute 52W High/Low from candles in the store (last 252 trading days ≈ 1 year)
  const stats52w = useMemo(() => {
    if (!candles.length) return null;
    const slice = candles.slice(-252);
    return {
      high: Math.max(...slice.map(c => c.high)),
      low: Math.min(...slice.map(c => c.low)),
      close: candles[candles.length - 1]?.close ?? 0,
      prevClose: candles[candles.length - 2]?.close ?? 0,
      volume: candles[candles.length - 1]?.volume ?? 0,
      dayHigh: candles[candles.length - 1]?.high ?? 0,
      dayLow: candles[candles.length - 1]?.low ?? 0,
    };
  }, [candles]);

  const changeAmt = stats52w ? stats52w.close - stats52w.prevClose : 0;
  const changePct = stats52w && stats52w.prevClose > 0 ? (changeAmt / stats52w.prevClose) * 100 : 0;
  const isBullishDay = changeAmt >= 0;

  // RS Score vs NIFTY 50 — 21-trading-day return ratio
  const rsScore = useMemo(() => {
    if (!candles.length || !niftyCandles.length) return null;
    const cutoff = new Date(); cutoff.setDate(cutoff.getDate() - 35);
    const cutStr = cutoff.toISOString().split('T')[0];
    const stockOld = candles.find(c => c.time >= cutStr);
    const niftyOld = niftyCandles.find(c => c.time >= cutStr);
    if (!stockOld || !niftyOld || niftyOld.close === 0) return null;
    const stockRet = (candles[candles.length - 1].close - stockOld.close) / stockOld.close;
    const niftyRet = (niftyCandles[niftyCandles.length - 1].close - niftyOld.close) / niftyOld.close;
    if (niftyRet === 0) return null;
    return stockRet / niftyRet;
  }, [candles, niftyCandles]);

  const fmtINR = (n: number) =>
    new Intl.NumberFormat('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n);
  const fmtVol = (v: number) =>
    v >= 1_000_000 ? `${(v / 1_000_000).toFixed(2)}M` : v >= 1000 ? `${(v / 1000).toFixed(1)}K` : String(v);

  useEffect(() => {
    fetchSymbols();
    fetchNiftyCandles(); // attempt to load NIFTY data for overlay — silently fails if not synced

    const handlePopState = () => {
      const path = window.location.pathname.replace(/^\/+/, '').split('/')[0];
      const valid = ['explorer', 'screener', 'sync', 'ai-research', 'portfolio', 'watchlist'];
      const tab = valid.includes(path) ? path : 'explorer';
      useStockStore.setState({ activeTab: tab as any });
    };
    window.addEventListener('popstate', handlePopState);

    // Keyboard shortcuts
    const handleKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA') return; // don't fire inside inputs
      const { setActiveTab } = useStockStore.getState();
      switch (e.key.toLowerCase()) {
        case 'e': setActiveTab('explorer');    break;
        case 's': setActiveTab('screener');    break;
        case 'p': setActiveTab('portfolio');   break;
        case 'w': setActiveTab('watchlist');   break;
        case 'a': setActiveTab('ai-research'); break;
        case 'c': setActiveTab('compare');    break;
      }
    };
    window.addEventListener('keydown', handleKey);

    return () => {
      window.removeEventListener('popstate', handlePopState);
      window.removeEventListener('keydown', handleKey);
    };
  }, []);

  return (
    <div className="flex flex-col h-screen w-screen bg-[#07080a] text-slate-100 overflow-hidden relative pt-16">
      {/* Decorative Glow Spots */}
      <div className="glow-spot top-[-100px] left-[200px]" />
      <div className="glow-spot-blue bottom-[-150px] right-[100px]" />

      {/* Top Navbar */}
      <header className="h-16 border-b border-slate-800 bg-[#0d0f14]/80 backdrop-blur-md flex items-center justify-between px-6 shrink-0 fixed top-0 left-0 right-0 z-50 w-full">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-purple-600/10 border border-purple-500/30 rounded-xl text-purple-400">
            <LineChart className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-md font-extrabold text-white tracking-tight flex items-center gap-1.5 leading-none">
              VAJRA <span className="text-xs px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-400 font-mono font-semibold">STOCKS</span>
            </h1>
            <p className="text-[10px] text-slate-400 mt-1 font-medium">NSE Quantitative Analysis & Screening Platform</p>
          </div>
        </div>

        {/* Dynamic Global Navigation Tabs */}
        <nav className="flex bg-[#121620]/80 p-1 rounded-lg border border-slate-800 flex-wrap gap-0.5">
          {([
            { id: 'explorer',    label: 'Explorer',    Icon: Layers      },
            { id: 'screener',    label: 'Screener',    Icon: Search      },
            { id: 'portfolio',   label: 'Portfolio',   Icon: IndianRupee },
            { id: 'watchlist',   label: 'Watchlist',   Icon: Bookmark    },
            { id: 'compare',     label: 'Compare',     Icon: TrendingUp  },
            { id: 'ai-research', label: 'AI Research', Icon: Cpu         },
            { id: 'settings',    label: 'Settings',    Icon: Settings    },
          ] as const).map(({ id, label, Icon }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-md transition duration-150 cursor-pointer ${
                activeTab === id
                  ? 'bg-purple-600 text-white shadow-md shadow-purple-900/20'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              {label}
            </button>
          ))}
          {/* Sync Centre — gear icon, not a primary tab */}
          <button
            onClick={() => setActiveTab('sync')}
            title="Sync Centre"
            className={`flex items-center gap-1.5 px-2 py-1.5 rounded-md transition duration-150 cursor-pointer ${
              activeTab === 'sync'
                ? 'bg-slate-700 text-white'
                : 'text-slate-500 hover:text-slate-300'
            }`}
          >
            <Settings className="w-3.5 h-3.5" />
          </button>
        </nav>

        {/* Global Loading Spinner */}
        <div className="flex items-center gap-2 text-xs text-slate-400">
          {isLoading && (
            <div className="flex items-center gap-1.5 bg-slate-900 px-2 py-1 rounded-md border border-slate-850">
              <RefreshCw className="w-3.5 h-3.5 animate-spin text-purple-400" />
              <span className="text-[10px]">Processing</span>
            </div>
          )}
          <span className="text-[10px] text-slate-500 font-mono">Ver 1.0.0</span>
        </div>
      </header>

      {/* Main Content Workspace */}
      <main className="flex-1 flex overflow-hidden relative z-10">
        
        {/* TAB 1: Explorer workspace (Grid with Sidebar) */}
        {activeTab === 'explorer' && (
          <div className="flex-1 flex overflow-hidden">
            {/* Stock Search/Browse Sidebar */}
            <Sidebar />
            
            {/* Stock Charting Workspace */}
            <div className="flex-1 flex flex-col p-4 overflow-y-auto gap-4">
              
              {/* ── Active Symbol Header ─────────────────────────────────────── */}
              {activeSymbolDetail ? (
                <div className="flex flex-col gap-2 p-4 rounded-xl border border-slate-800/80 bg-[#121620]/35">
                  {/* Row 1: Name + badges + watchlist */}
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xl font-bold tracking-tight text-white">
                        {activeSymbolDetail.symbol.replace('.NS', '')}
                      </span>
                      <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-400">
                        {activeSymbolDetail.series}
                      </span>
                      {activeSymbolDetail.last_attempt_status === 'SUCCESS' ? (
                        <span className="text-[9px] uppercase font-bold px-2 py-0.5 rounded text-emerald-400 bg-emerald-950/20 border border-emerald-900/35">Synced</span>
                      ) : (
                        <span className="text-[9px] uppercase font-bold px-2 py-0.5 rounded text-rose-400 bg-rose-950/20 border border-rose-900/35">Out of Date</span>
                      )}
                      <h2 className="text-sm text-slate-400">{activeSymbolDetail.company_name}</h2>
                    </div>
                    <button
                      onClick={() => { const wl = watchlists[0]; if (wl && activeSymbolDetail) addToWatchlist(wl.id, activeSymbolDetail.symbol); }}
                      title="Add to Watchlist"
                      className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-900 border border-slate-800 hover:border-indigo-500/60 text-slate-400 hover:text-indigo-400 text-xs font-semibold transition cursor-pointer"
                    >
                      <Bookmark className="w-3.5 h-3.5" />
                      Watchlist
                    </button>
                  </div>

                  {/* Row 2: OHLC / Volume / 52W strip */}
                  {stats52w && (
                    <div className="flex flex-wrap gap-x-5 gap-y-1 pt-1 border-t border-slate-800/60">
                      {/* CMP + Day Change */}
                      <div className="flex items-center gap-1.5">
                        <span className={`text-base font-extrabold font-mono ${isBullishDay ? 'text-emerald-400' : 'text-rose-400'}`}>
                          ₹{fmtINR(stats52w.close)}
                        </span>
                        <span className={`flex items-center gap-0.5 text-xs font-bold ${isBullishDay ? 'text-emerald-400' : 'text-rose-400'}`}>
                          <TrendingUp className="w-3 h-3" />
                          {isBullishDay ? '+' : ''}{fmtINR(changeAmt)} ({isBullishDay ? '+' : ''}{changePct.toFixed(2)}%)
                        </span>
                      </div>
                      {/* Static stats */}
                      {([
                        { label: 'Day H',   value: `₹${fmtINR(stats52w.dayHigh)}` },
                        { label: 'Day L',   value: `₹${fmtINR(stats52w.dayLow)}`  },
                        { label: 'Volume',  value: fmtVol(stats52w.volume)          },
                        { label: '52W H',   value: `₹${fmtINR(stats52w.high)}`     },
                        { label: '52W L',   value: `₹${fmtINR(stats52w.low)}`      },
                      ] as { label: string; value: string }[]).map(({ label, value }) => (
                        <div key={label} className="flex items-center gap-1 text-xs">
                          <span className="text-slate-500">{label}</span>
                          <span className="text-slate-200 font-mono font-semibold">{value}</span>
                        </div>
                      ))}
                      {/* RS Score badge */}
                      {rsScore != null && (
                        <div className="flex items-center gap-1 text-xs">
                          <span className="text-slate-500">RS 1M</span>
                          <span className={`font-mono font-bold px-1.5 py-0.5 rounded border text-[10px] ${
                            rsScore >= 1.2 ? 'text-emerald-400 bg-emerald-950/20 border-emerald-900/30'
                            : rsScore >= 0.8 ? 'text-slate-300 bg-slate-900/40 border-slate-800'
                            : 'text-rose-400 bg-rose-950/20 border-rose-900/30'
                          }`}>
                            {rsScore.toFixed(2)}x
                          </span>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Row 3: Chart controls */}
                  <div className="flex flex-wrap gap-2 pt-1">
                    {/* Timeframe */}
                    <div className="flex bg-slate-950/80 p-0.5 rounded-lg border border-slate-850">
                      {(['1W', '1M', '3M', '6M', '1Y', 'MAX'] as const).map(tf => (
                        <button
                          key={tf}
                          onClick={() => setChartTimeframe(tf)}
                          className={`px-2.5 py-1.5 rounded-md text-[10px] font-bold transition duration-150 cursor-pointer ${
                            chartTimeframe === tf ? 'bg-purple-600 text-white' : 'text-slate-400 hover:text-slate-200'
                          }`}
                        >
                          {tf}
                        </button>
                      ))}
                    </div>

                    {/* Chart Type */}
                    <div className="flex bg-slate-950/80 p-0.5 rounded-lg border border-slate-850">
                      {(['candles', 'heikin-ashi', 'renko', 'line-break'] as const).map(type => (
                        <button
                          key={type}
                          onClick={() => setChartType(type)}
                          className={`px-3 py-1.5 rounded-md text-[10px] font-bold capitalize transition duration-150 cursor-pointer ${
                            chartType === type ? 'bg-purple-600 text-white' : 'text-slate-400 hover:text-slate-200'
                          }`}
                        >
                          {type.replace('-', ' ')}
                        </button>
                      ))}
                    </div>

                    {/* Indicator sub-pane */}
                    <div className="flex bg-slate-950/80 p-0.5 rounded-lg border border-slate-850">
                      {(['RSI', 'MACD', 'NONE'] as const).map(ind => (
                        <button
                          key={ind}
                          onClick={() => setIndicatorToShow(ind)}
                          className={`px-3 py-1.5 rounded-md text-[10px] font-bold transition duration-150 cursor-pointer ${
                            indicatorToShow === ind ? 'bg-purple-600 text-white' : 'text-slate-400 hover:text-slate-200'
                          }`}
                        >
                          {ind}
                        </button>
                      ))}
                    </div>

                    {/* Drawing tools */}
                    <div className="flex bg-slate-950/80 p-0.5 rounded-lg border border-slate-850">
                      <button
                        onClick={() => setDrawMode(d => !d)}
                        title={drawMode ? 'Click chart to place H-Line · Click again to exit' : 'Draw horizontal level'}
                        className={`px-2.5 py-1.5 rounded-md text-[10px] font-bold transition cursor-pointer ${
                          drawMode ? 'bg-purple-600 text-white' : 'text-slate-500 hover:text-slate-300'
                        }`}
                      >
                        {drawMode ? '✏️ Drawing…' : '✏️ H-Line'}
                      </button>
                      {activeSymbol && (customLines[activeSymbol]?.length ?? 0) > 0 && (
                        <button
                          onClick={() => activeSymbol && removeCustomLines(activeSymbol)}
                          title="Clear all drawn lines"
                          className="px-2.5 py-1.5 rounded-md text-[10px] font-bold text-rose-400 hover:text-rose-300 transition cursor-pointer"
                        >
                          Clear
                        </button>
                      )}
                    </div>

                    {/* Overlay toggles — SMAs + EMAs + BB in one block */}
                    <div className="flex bg-slate-950/80 p-0.5 rounded-lg border border-slate-850 flex-wrap">
                      {([
                        { key: 'sma20'  as const, label: 'SMA 20',  color: 'text-blue-400'   },
                        { key: 'sma50'  as const, label: 'SMA 50',  color: 'text-amber-400'  },
                        { key: 'sma200' as const, label: 'SMA 200', color: 'text-pink-400'   },
                        { key: 'ema9'   as const, label: 'EMA 9',   color: 'text-cyan-400'   },
                        { key: 'ema21'  as const, label: 'EMA 21',  color: 'text-orange-400' },
                        { key: 'bb'     as const, label: 'BB',      color: 'text-slate-300'  },
                        { key: 'sr'     as const, label: 'S/R',     color: 'text-yellow-400' },
                        { key: 'nifty'  as const, label: 'NIFTY',   color: 'text-yellow-300', disabled: niftyCandles.length === 0 },
                      ]).map(({ key, label, color, disabled = false }) => (
                        <button
                          key={key}
                          onClick={() => !disabled && toggleChartOverlay(key)}
                          title={disabled ? `Sync ^NSEI first to enable` : chartOverlays.has(key) ? `Hide ${label}` : `Show ${label}`}
                          className={`px-2.5 py-1.5 rounded-md text-[10px] font-bold transition duration-150 ${
                            disabled ? 'opacity-30 cursor-not-allowed text-slate-600'
                            : chartOverlays.has(key) ? `bg-slate-700 ${color} cursor-pointer`
                            : 'text-slate-600 hover:text-slate-400 cursor-pointer'
                          }`}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="p-4 rounded-xl border border-slate-800 bg-[#121620]/30 text-center text-slate-500 text-sm">
                  Please select an active ticker from the sidebar to inspect market trends.
                </div>
              )}

              {/* Central Charting Area */}
              {activeSymbol ? (
                <>
                  <PriceChart
                    indicatorToShow={indicatorToShow}
                    timeframe={chartTimeframe}
                    overlays={chartOverlays}
                    niftyCandles={niftyCandles}
                    customLines={activeSymbol ? (customLines[activeSymbol] ?? []) : []}
                    drawMode={drawMode}
                    onChartClick={(price) => {
                      if (activeSymbol) { addCustomLine(activeSymbol, price); setDrawMode(false); }
                    }}
                  />
                  
                  {/* Multi-Pane Grid details */}
                  <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 min-h-[350px]">
                    <div className="xl:col-span-2">
                      <MetricsTable />
                    </div>
                    <div className="xl:col-span-1 flex flex-col gap-4">
                      <TradePlanCard />
                      <CorporateActionsTimeline />
                    </div>
                  </div>
                </>
              ) : (
                <div className="flex-1 flex flex-col items-center justify-center text-slate-500 py-12">
                  <Cpu className="w-12 h-12 mb-3 text-slate-700 animate-pulse" />
                  <p className="text-sm">Select an active stock to launch TradingView charts.</p>
                </div>
              )}

            </div>
          </div>
        )}

        {/* TAB 2: Screener Workspace */}
        {activeTab === 'screener' && <ScreenerPanel />}

        {/* TAB 3: Synchronization Workspace */}
        {activeTab === 'sync' && <SyncPanel />}

        {/* TAB 4: AI Research Workspace */}
        {activeTab === 'ai-research' && <AgentTerminal />}

        {/* TAB 5: Portfolio */}
        {activeTab === 'portfolio' && <PortfolioPanel />}

        {/* Compare */}
        {activeTab === 'compare' && <ComparePanel />}

        {/* Settings */}
        {activeTab === 'settings' && <SettingsPanel />}

        {/* TAB 6: Watchlist */}
        {activeTab === 'watchlist' && <WatchlistPanel />}

      </main>
    </div>
  );
}

// Inline reload icon for sidebar compatibility
const RefreshCw = ({ className, ...props }: React.ComponentProps<'svg'>) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    {...props}
  >
    <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
    <path d="M3 3v5h5" />
    <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" />
    <path d="M16 16h5v5" />
  </svg>
);

export default App;
