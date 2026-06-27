import React, { useEffect, useState } from 'react';
import { useSettings } from './hooks/useSettings';
import { API_BASE } from './lib/apiBase';
import { SettingsContext } from './contexts/SettingsContext';
import { useStockStore } from './store/useStockStore';
import { ThemeProvider } from './contexts/ThemeProvider';
import { ThemeToggle } from './components/ThemeToggle';
import { Sidebar } from './components/Sidebar';
import { StockChartWorkspace } from './components/StockChartWorkspace';
import { MetricsTable } from './components/MetricsTable';
import { CorporateActionsTimeline } from './components/CorporateActionsTimeline';
import { ScreenerPanel } from './components/ScreenerPanel';
import { StrategyPanel } from './components/StrategyPanel';
import { SyncPanel } from './components/SyncPanel';
import { AIResearch } from './components/AIResearch';
import { PortfolioPanel } from './components/PortfolioPanel';
import { WatchlistPanel } from './components/WatchlistPanel';
import { TradePlanCard } from './components/TradePlanCard';
import { ComparePanel } from './components/ComparePanel';
import { SettingsPanel } from './components/SettingsPanel';
import { SetupWizard } from './components/SetupWizard';
import { AboutPanel } from './components/AboutPanel';
import { SwingPicksPanel } from './components/SwingPicksPanel';
import { BacktestPanel } from './components/BacktestPanel';
import { JournalPanel } from './components/JournalPanel';
import { RankingPanel } from './components/RankingPanel';
import { SetupsPanel } from './components/SetupsPanel';
import { FundamentalsCard } from './components/FundamentalsCard';
import { AnnouncementsPanel } from './components/AnnouncementsPanel';
import { NewsPanel } from './components/NewsPanel';
import {
  LineChart,
  Search,
  Settings,
  Cpu,
  Layers,
  IndianRupee,
  Bookmark,
  TrendingUp,
  Target,
  Bell,
  X,
  BookOpen,
  Brain,
  Zap,
  Activity,
  BookMarked,
  ListOrdered,
} from 'lucide-react';
import './App.css';

// Thin wrapper: decides between loading / setup wizard / dashboard.
// Keeping this separate guarantees a stable hook order in Dashboard.
function App() {
  const [setupNeeded, setSetupNeeded] = React.useState<boolean | null>(null);
  // Single settings fetch shared by all child components via context
  const settingsState = useSettings();

  React.useEffect(() => {
    fetch(`${API_BASE}/setup/status`)
      .then(r => r.json())
      .then(d => setSetupNeeded(d.setup_needed === true))
      .catch(() => setSetupNeeded(false));
  }, []);

  if (setupNeeded === null) return (
    <div className="min-h-screen bg-bg-base flex items-center justify-center text-text-muted text-sm">
      Starting VajraStocks…
    </div>
  );

  if (setupNeeded) return <SetupWizard onComplete={() => setSetupNeeded(false)} />;

  return (
    <ThemeProvider>
      <SettingsContext.Provider value={settingsState}>
        <Dashboard />
      </SettingsContext.Provider>
    </ThemeProvider>
  );
}

function Dashboard() {
  const {
    activeTab,
    setActiveTab,
    activeSymbol,
    fetchSymbols,
    fetchNiftyCandles,
    isLoading,
    stockAlerts,
    fetchStockAlerts,
    dismissStockAlert,
    dismissAllStockAlerts,
  } = useStockStore();

  const [showAlerts, setShowAlerts] = useState(false);
  const [researchTab, setResearchTab] = useState<'fundamentals' | 'news' | 'announcements'>('fundamentals');

  useEffect(() => {
    fetchSymbols();
    fetchNiftyCandles(); // attempt to load NIFTY data for overlay — silently fails if not synced
    fetchStockAlerts();  // load triggered alerts on startup

    const handlePopState = () => {
      const path = window.location.pathname.replace(/^\/+/, '').split('/')[0];
      const valid = ['explorer', 'screener', 'ranking', 'setups', 'strategy', 'backtest', 'journal', 'sync', 'ai-research', 'portfolio', 'watchlist', 'about', 'ml2-training'];
      const tab = valid.includes(path) ? path : 'explorer';
      useStockStore.setState({ activeTab: tab as any });
    };
    window.addEventListener('popstate', handlePopState);

    // Keyboard shortcuts
    const handleKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA') return; // don't fire inside inputs
      if (e.ctrlKey || e.metaKey || e.altKey) return; // bypass if modifier keys are active (e.g. Ctrl+C)
      const { setActiveTab } = useStockStore.getState();
      switch (e.key.toLowerCase()) {
        case 'e': setActiveTab('explorer');    break;
        case 's': setActiveTab('screener');    break;
        case 't': setActiveTab('strategy');    break;
        case 'p': setActiveTab('portfolio');   break;
        case 'w': setActiveTab('watchlist');   break;
        case 'a': setActiveTab('ai-research'); break;
        case 'c': setActiveTab('compare');    break;
        case 'r': setActiveTab('swing-picks'); break;
      }
    };
    window.addEventListener('keydown', handleKey);

    return () => {
      window.removeEventListener('popstate', handlePopState);
      window.removeEventListener('keydown', handleKey);
    };
  }, []);

  return (
    <div className="flex flex-col h-screen w-screen bg-bg-base text-text-main overflow-hidden relative pt-16 transition-colors duration-300">
      {/* Decorative Glow Spots */}
      <div className="glow-spot top-[-100px] left-[200px]" />
      <div className="glow-spot-blue bottom-[-150px] right-[100px]" />

      {/* Top Navbar */}
      <header className="h-16 border-b border-border-subtle bg-bg-surface/80 backdrop-blur-md flex items-center justify-between px-6 shrink-0 fixed top-0 left-0 right-0 z-50 w-full transition-colors duration-300">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-purple-600/10 border border-purple-500/30 rounded-xl text-purple-400">
            <LineChart className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-md font-extrabold text-text-main tracking-tight flex items-center gap-1.5 leading-none">
              VAJRA <span className="text-xs px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-400 font-mono font-semibold">STOCKS</span>
            </h1>
            <p className="text-[10px] text-slate-400 mt-1 font-medium">NSE Quantitative Analysis & Screening Platform</p>
          </div>
        </div>

        {/* Dynamic Global Navigation Tabs */}
        <nav className="flex bg-bg-surface/90 p-1 rounded-lg border border-border-subtle flex-wrap gap-0.5 transition-colors duration-300">
          {([
            { id: 'explorer',    label: 'Explorer',    Icon: Layers      },
            { id: 'screener',    label: 'Screener',    Icon: Search      },
            { id: 'ranking',     label: 'Ranking',     Icon: ListOrdered },
            { id: 'setups',      label: 'Setups',      Icon: Zap         },
            { id: 'strategy',    label: 'Strategy',    Icon: Target      },
            { id: 'backtest',    label: 'Backtest',    Icon: Activity    },
            { id: 'journal',     label: 'Journal',     Icon: BookMarked  },
            { id: 'portfolio',   label: 'Portfolio',   Icon: IndianRupee },
            { id: 'watchlist',   label: 'Watchlist',   Icon: Bookmark    },
            { id: 'compare',     label: 'Compare',     Icon: TrendingUp  },
            { id: 'swing-picks', label: 'Picks',       Icon: Zap         },
            { id: 'ai-research', label: 'AI Research', Icon: Cpu         },
            { id: 'ml2-training', label: 'ML Model',    Icon: Brain       },
            { id: 'about',       label: 'About',       Icon: BookOpen    },
            { id: 'settings',    label: 'Settings',    Icon: Settings    },
          ] as const).map(({ id, label, Icon }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-md transition duration-150 cursor-pointer ${
                activeTab === id
                  ? 'bg-accent-primary text-accent-text shadow-md'
                  : 'text-text-muted hover:text-text-main'
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
                ? 'bg-border-subtle text-text-main'
                : 'text-text-muted/65 hover:text-text-muted'
            }`}
          >
            <Settings className="w-3.5 h-3.5" />
          </button>

          {/* Alerts bell */}
          <div className="relative">
            <button
              onClick={() => setShowAlerts(v => !v)}
              title="Alerts"
              className="relative flex items-center gap-1.5 px-2 py-1.5 rounded-md transition duration-150 cursor-pointer text-text-muted/65 hover:text-text-muted"
            >
              <Bell className="w-3.5 h-3.5" />
              {stockAlerts.length > 0 && (
                <span className="absolute -top-0.5 -right-0.5 min-w-[14px] h-[14px] flex items-center justify-center bg-rose-500 text-white text-[9px] font-bold rounded-full px-0.5">
                  {stockAlerts.length > 99 ? '99+' : stockAlerts.length}
                </span>
              )}
            </button>

            {showAlerts && (
              <div className="absolute right-0 top-full mt-1 w-96 max-h-96 overflow-y-auto bg-bg-surface border border-border-subtle rounded-xl shadow-2xl z-50">
                <div className="flex items-center justify-between px-3 py-2 border-b border-border-subtle">
                  <span className="text-xs font-bold text-text-main">Alerts ({stockAlerts.length})</span>
                  <div className="flex gap-2">
                    {stockAlerts.length > 0 && (
                      <button
                        onClick={() => { dismissAllStockAlerts(); }}
                        className="text-[10px] text-slate-400 hover:text-slate-200"
                      >
                        Dismiss all
                      </button>
                    )}
                    <button onClick={() => setShowAlerts(false)} className="text-slate-400 hover:text-slate-200">
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
                {stockAlerts.length === 0 ? (
                  <p className="text-xs text-slate-500 px-3 py-4 text-center">No active alerts.</p>
                ) : (
                  <ul className="divide-y divide-slate-800">
                    {stockAlerts.map(alert => (
                      <li key={alert.id} className="flex items-start gap-2 px-3 py-2.5 hover:bg-slate-800/40">
                        <div className="flex-1 min-w-0">
                          <p className="text-[11px] font-semibold text-slate-200 truncate">{alert.symbol.replace('.NS', '')}</p>
                          <p className="text-[10px] text-slate-400 mt-0.5 leading-tight">{alert.message}</p>
                          <p className="text-[9px] text-slate-600 mt-0.5">{new Date(alert.triggered_at).toLocaleString('en-IN')}</p>
                        </div>
                        <button
                          onClick={() => dismissStockAlert(alert.id)}
                          className="text-slate-600 hover:text-slate-400 mt-0.5 flex-shrink-0"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
        </nav>

        {/* Global Loading Spinner */}
        <div className="flex items-center gap-4 text-xs text-text-muted">
          <ThemeToggle />
          {isLoading && (
            <div className="flex items-center gap-1.5 bg-bg-surface px-2 py-1 rounded-md border border-border-subtle">
              <RefreshCw className="w-3.5 h-3.5 animate-spin text-accent-primary" />
              <span className="text-[10px]">Processing</span>
            </div>
          )}
          <span className="text-[10px] text-text-muted/60 font-mono">Ver {import.meta.env.VITE_APP_VERSION}</span>
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
              <StockChartWorkspace />
              
              {/* Multi-Pane Grid details */}
              {activeSymbol && (
                <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 min-h-[350px]">
                  <div className="xl:col-span-2 flex flex-col gap-4">
                    <MetricsTable />
                    
                    {/* Research panel — Fundamentals / News / NSE Announcements */}
                    <div className="w-full rounded-xl border border-border-subtle bg-bg-surface/60 overflow-hidden shrink-0">
                      {/* Tab bar */}
                        <div className="flex items-center border-b border-border-subtle px-2 pt-1">
                          {([
                            { id: 'fundamentals'  as const, label: 'Fundamentals' },
                            { id: 'news'          as const, label: 'News'         },
                            { id: 'announcements' as const, label: 'NSE Filings'  },
                          ]).map(({ id, label }) => (
                            <button
                              key={id}
                              onClick={() => setResearchTab(id)}
                              className={`px-4 py-2 text-xs font-bold border-b-2 transition-colors cursor-pointer ${
                                researchTab === id
                                  ? 'border-accent-primary text-accent-primary'
                                  : 'border-transparent text-text-muted hover:text-text-main'
                              }`}
                            >
                              {label}
                            </button>
                          ))}
                        </div>
                        {/* Tab content — no extra card wrapper inside since each component is self-contained */}
                        <div className="p-4">
                          {researchTab === 'fundamentals'  && <FundamentalsCard  symbol={activeSymbol} />}
                          {researchTab === 'news'          && <NewsPanel         symbol={activeSymbol} />}
                          {researchTab === 'announcements' && <AnnouncementsPanel symbol={activeSymbol} />}
                        </div>
                      </div>
                    </div>

                    <div className="xl:col-span-1 flex flex-col gap-4">
                      <TradePlanCard />
                      <CorporateActionsTimeline />
                    </div>
                  </div>
              )}

            </div>
          </div>
        )}

        {/* TAB 2: Screener Workspace */}
        {activeTab === 'screener' && <ScreenerPanel />}

        {/* TAB 2b: Strategy Screener Workspace */}
        {activeTab === 'strategy' && <StrategyPanel />}

        {/* TAB 2c: Backtest Lab */}
        {activeTab === 'backtest' && <BacktestPanel />}

        {/* TAB 2d: Trade Journal */}
        {activeTab === 'journal' && <JournalPanel />}

        {/* TAB 2e: Cross-sectional Ranking */}
        {activeTab === 'ranking' && <RankingPanel />}

        {/* TAB 2f: Setups (presets) */}
        {activeTab === 'setups' && <SetupsPanel />}

        {/* TAB 3: Synchronization Workspace */}
        {activeTab === 'sync' && <SyncPanel />}

        {/* TAB 4: AI Research Workspace */}
        {activeTab === 'ai-research' && <AIResearch />}

        {/* TAB 5: Portfolio */}
        {activeTab === 'portfolio' && <PortfolioPanel />}

        {/* Compare */}
        {activeTab === 'compare' && <ComparePanel />}

        {/* Swing Picks */}
        {activeTab === 'swing-picks' && <SwingPicksPanel />}

        {/* Settings */}
        {activeTab === 'settings' && <SettingsPanel />}

        {/* About */}
        {activeTab === 'about' && <AboutPanel />}

        {/* TAB 6: Watchlist */}
        {activeTab === 'watchlist' && <WatchlistPanel />}

      </main>

      {/* Sticky footer */}
      <footer className="h-7 shrink-0 border-t border-border-subtle bg-bg-surface/85 backdrop-blur-md flex items-center justify-between px-5 z-40">
        <span className="text-[10px] font-bold text-slate-300">VajraStocks v1.5.0 — Data © Yahoo Finance, for personal use only</span>
        <a
          href="https://abhishek4official.github.io/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-[10px] font-bold text-slate-300 hover:text-purple-400 transition flex items-center gap-1"
        >
          Developed by <span className="text-text-main hover:text-accent-primary transition ml-0.5">Abhishek Kumar</span>
        </a>
      </footer>
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
