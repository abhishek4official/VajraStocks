import React, { useEffect, useState } from 'react';
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { useSettings } from './hooks/useSettings';
import { API_BASE } from './lib/apiBase';
import { SettingsContext } from './contexts/SettingsContext';
import { useStockStore } from './store/useStockStore';
import { ThemeProvider } from './contexts/ThemeProvider';
import { ThemeToggle } from './components/ThemeToggle';
import { NavRail } from './components/NavRail';
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
import { Bell, LineChart, X, RefreshCw } from 'lucide-react';
import './App.css';

// ── Sub-tab definitions per destination ──────────────────────────────────────
const SUB_TABS: Record<string, { path: string; label: string }[]> = {
  '/research': [
    { path: '/research/explorer', label: 'Explorer' },
    { path: '/research/compare',  label: 'Compare'  },
    { path: '/research/ai',       label: 'AI Research' },
  ],
  '/discover': [
    { path: '/discover/screener', label: 'Screener' },
    { path: '/discover/ranking',  label: 'Ranking'  },
    { path: '/discover/setups',   label: 'Setups'   },
    { path: '/discover/picks',    label: 'Picks'    },
  ],
  '/validate': [
    { path: '/validate/backtest',  label: 'Backtest' },
    { path: '/validate/strategy',  label: 'Strategy' },
  ],
  '/portfolio': [
    { path: '/portfolio/holdings',  label: 'Holdings'  },
    { path: '/portfolio/watchlist', label: 'Watchlist' },
  ],
};

function SubTabBar() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const dest = '/' + pathname.split('/')[1];
  const tabs = SUB_TABS[dest];
  if (!tabs) return null;

  return (
    <div className="flex gap-0 border-b border-border-subtle bg-bg-surface/50 px-3 shrink-0">
      {tabs.map(({ path, label }) => {
        const active = pathname === path || pathname.startsWith(path + '/');
        return (
          <button
            key={path}
            onClick={() => navigate(path)}
            className={`px-4 py-2 text-xs font-bold border-b-2 transition-colors cursor-pointer ${
              active
                ? 'border-accent-primary text-accent-primary'
                : 'border-transparent text-text-muted hover:text-text-main'
            }`}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}

// ── Explorer panel (Research/Explorer sub-route) ──────────────────────────────
function ExplorerPanel() {
  const { activeSymbol } = useStockStore();
  const [researchTab, setResearchTab] = useState<'fundamentals' | 'news' | 'announcements'>('fundamentals');

  return (
    <div className="flex-1 flex overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col p-4 overflow-y-auto gap-4">
        <StockChartWorkspace />
        {activeSymbol && (
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 min-h-[350px]">
            <div className="xl:col-span-2 flex flex-col gap-4">
              <MetricsTable />
              <div className="w-full rounded-xl border border-border-subtle bg-bg-surface/60 overflow-hidden shrink-0">
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
  );
}

// ── App shell ─────────────────────────────────────────────────────────────────
function App() {
  const [setupNeeded, setSetupNeeded] = React.useState<boolean | null>(null);
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

// ── Dashboard (router-driven) ─────────────────────────────────────────────────
function Dashboard() {
  const {
    fetchSymbols,
    fetchNiftyCandles,
    isLoading,
    stockAlerts,
    fetchStockAlerts,
    dismissStockAlert,
    dismissAllStockAlerts,
  } = useStockStore();

  const navigate = useNavigate();
  const [showAlerts, setShowAlerts] = useState(false);

  useEffect(() => {
    fetchSymbols();
    fetchNiftyCandles();
    fetchStockAlerts();

    // Keyboard shortcuts
    const handleKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA') return;
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      switch (e.key.toLowerCase()) {
        case 'e': navigate('/research/explorer'); break;
        case 's': navigate('/discover/screener'); break;
        case 't': navigate('/validate/strategy'); break;
        case 'p': navigate('/portfolio/holdings'); break;
        case 'w': navigate('/portfolio/watchlist'); break;
        case 'a': navigate('/research/ai');       break;
        case 'c': navigate('/research/compare');  break;
        case 'r': navigate('/discover/picks');    break;
        case 'j': navigate('/trade/journal');     break;
        case 'b': navigate('/validate/backtest'); break;
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [navigate]);

  return (
    <div className="flex flex-col h-screen w-screen bg-bg-base text-text-main overflow-hidden relative transition-colors duration-300">
      {/* Decorative glow spots */}
      <div className="glow-spot top-[-100px] left-[200px]" />
      <div className="glow-spot-blue bottom-[-150px] right-[100px]" />

      {/* Top header — slimmed to h-12, no nav tabs */}
      <header className="h-12 border-b border-border-subtle bg-bg-surface/80 backdrop-blur-md flex items-center justify-between px-4 shrink-0 z-50">
        <div className="flex items-center gap-2.5">
          <div className="p-1.5 bg-purple-600/10 border border-purple-500/30 rounded-lg text-purple-400">
            <LineChart className="w-4 h-4" />
          </div>
          <div>
            <h1 className="text-sm font-extrabold text-text-main tracking-tight flex items-center gap-1.5 leading-none">
              VAJRA <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-400 font-mono font-semibold">STOCKS</span>
            </h1>
            <p className="text-[9px] text-slate-400 mt-0.5 font-medium hidden sm:block">NSE Quantitative Analysis Platform</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <ThemeToggle />
          {isLoading && (
            <div className="flex items-center gap-1 bg-bg-surface px-2 py-1 rounded border border-border-subtle">
              <RefreshCw className="w-3 h-3 animate-spin text-accent-primary" />
              <span className="text-[10px] text-text-muted">Syncing</span>
            </div>
          )}
          <span className="text-[9px] text-text-muted/50 font-mono hidden md:block">
            v{import.meta.env.VITE_APP_VERSION}
          </span>

          {/* Alerts bell */}
          <div className="relative">
            <button
              onClick={() => setShowAlerts(v => !v)}
              title="Alerts"
              className="relative p-1.5 rounded-md transition cursor-pointer text-text-muted hover:text-text-main"
            >
              <Bell className="w-4 h-4" />
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
                      <button onClick={dismissAllStockAlerts} className="text-[10px] text-slate-400 hover:text-slate-200">
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
                        <button onClick={() => dismissStockAlert(alert.id)} className="text-slate-600 hover:text-slate-400 mt-0.5 shrink-0">
                          <X className="w-3 h-3" />
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Body: NavRail + content */}
      <div className="flex flex-1 overflow-hidden relative z-10">
        <NavRail />

        {/* Content area: sub-tab bar + panel */}
        <div className="flex-1 flex flex-col overflow-hidden">
          <SubTabBar />
          <main className="flex-1 overflow-hidden">
            <Routes>
              {/* Default */}
              <Route path="/" element={<Navigate to="/research/explorer" replace />} />

              {/* Research */}
              <Route path="/research" element={<Navigate to="/research/explorer" replace />} />
              <Route path="/research/explorer" element={<ExplorerPanel />} />
              <Route path="/research/compare"  element={<ComparePanel />} />
              <Route path="/research/ai"       element={<AIResearch />} />

              {/* Discover */}
              <Route path="/discover" element={<Navigate to="/discover/screener" replace />} />
              <Route path="/discover/screener" element={<ScreenerPanel />} />
              <Route path="/discover/ranking"  element={<RankingPanel />} />
              <Route path="/discover/setups"   element={<SetupsPanel />} />
              <Route path="/discover/picks"    element={<SwingPicksPanel />} />

              {/* Validate */}
              <Route path="/validate" element={<Navigate to="/validate/backtest" replace />} />
              <Route path="/validate/backtest"  element={<BacktestPanel />} />
              <Route path="/validate/strategy"  element={<StrategyPanel />} />

              {/* Trade */}
              <Route path="/trade" element={<Navigate to="/trade/journal" replace />} />
              <Route path="/trade/journal" element={<JournalPanel />} />

              {/* Portfolio */}
              <Route path="/portfolio" element={<Navigate to="/portfolio/holdings" replace />} />
              <Route path="/portfolio/holdings"  element={<PortfolioPanel />} />
              <Route path="/portfolio/watchlist" element={<WatchlistPanel />} />

              {/* Utility */}
              <Route path="/sync"     element={<SyncPanel />} />
              <Route path="/settings" element={<SettingsPanel />} />
              <Route path="/about"    element={<AboutPanel />} />

              {/* Fallback */}
              <Route path="*" element={<Navigate to="/research/explorer" replace />} />
            </Routes>
          </main>
        </div>
      </div>

      <footer className="h-7 shrink-0 border-t border-border-subtle bg-bg-surface/85 backdrop-blur-md flex items-center justify-between px-5 z-40">
        <span className="text-[10px] font-bold text-slate-300">VajraStocks v{import.meta.env.VITE_APP_VERSION} — Data © Yahoo Finance, for personal use only</span>
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

export default App;
