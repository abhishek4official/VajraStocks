import { useEffect, useState } from 'react';
import { useStockStore } from './store/useStockStore';
import { Sidebar } from './components/Sidebar';
import { PriceChart } from './components/PriceChart';
import { MetricsTable } from './components/MetricsTable';
import { CorporateActionsTimeline } from './components/CorporateActionsTimeline';
import { ScreenerPanel } from './components/ScreenerPanel';
import { SyncPanel } from './components/SyncPanel';
import { AgentTerminal } from './components/AgentTerminal';
import { 
  LineChart, 
  Search, 
  Settings, 
  Cpu, 
  Layers 
} from 'lucide-react';
import './App.css';

function App() {
  const { 
    activeTab, 
    setActiveTab, 
    chartType, 
    setChartType, 
    activeSymbol, 
    activeSymbolDetail,
    fetchSymbols,
    isLoading
  } = useStockStore();

  const [indicatorToShow, setIndicatorToShow] = useState<'RSI' | 'MACD' | 'NONE'>('RSI');

  useEffect(() => {
    // Initial load of symbols
    fetchSymbols();

    // Browser back/forward button history navigation synchronization
    const handlePopState = () => {
      const path = window.location.pathname.replace(/^\/+/, '').split('/')[0];
      const tab = ['explorer', 'screener', 'sync', 'ai-research'].includes(path) ? path : 'explorer';
      useStockStore.setState({ activeTab: tab as any });
    };

    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
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
        <nav className="flex bg-[#121620]/80 p-1 rounded-lg border border-slate-800">
          <button
            onClick={() => setActiveTab('explorer')}
            className={`flex items-center gap-1.5 px-4 py-1.5 text-xs font-bold rounded-md transition duration-150 cursor-pointer ${
              activeTab === 'explorer'
                ? 'bg-purple-600 text-white shadow-md shadow-purple-900/20'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            Explorer Dashboard
          </button>
          
          <button
            onClick={() => setActiveTab('screener')}
            className={`flex items-center gap-1.5 px-4 py-1.5 text-xs font-bold rounded-md transition duration-150 cursor-pointer ${
              activeTab === 'screener'
                ? 'bg-purple-600 text-white shadow-md shadow-purple-900/20'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Search className="w-3.5 h-3.5" />
            Technical Screener
          </button>
          
          <button
            onClick={() => setActiveTab('sync')}
            className={`flex items-center gap-1.5 px-4 py-1.5 text-xs font-bold rounded-md transition duration-150 cursor-pointer ${
              activeTab === 'sync'
                ? 'bg-purple-600 text-white shadow-md shadow-purple-900/20'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Settings className="w-3.5 h-3.5" />
            Sync Center
          </button>

          <button
            onClick={() => setActiveTab('ai-research')}
            className={`flex items-center gap-1.5 px-4 py-1.5 text-xs font-bold rounded-md transition duration-150 cursor-pointer ${
              activeTab === 'ai-research'
                ? 'bg-purple-600 text-white shadow-md shadow-purple-900/20'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Cpu className="w-3.5 h-3.5" />
            AI Research Console
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
              
              {/* Active Symbol Stats Header */}
              {activeSymbolDetail ? (
                <div className="p-4 rounded-xl border border-slate-800/80 bg-[#121620]/35 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xl font-bold tracking-tight text-white">{activeSymbolDetail.symbol.replace('.NS', '')}</span>
                      <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-400">
                        {activeSymbolDetail.series}
                      </span>
                      {activeSymbolDetail.last_attempt_status === 'SUCCESS' ? (
                        <span className="text-[9px] uppercase font-bold px-2 py-0.5 rounded text-emerald-400 bg-emerald-950/20 border border-emerald-900/35">
                          Synced
                        </span>
                      ) : (
                        <span className="text-[9px] uppercase font-bold px-2 py-0.5 rounded text-rose-400 bg-rose-950/20 border border-rose-900/35">
                          Out of Date
                        </span>
                      )}
                    </div>
                    <h2 className="text-sm text-slate-400 mt-1">{activeSymbolDetail.company_name}</h2>
                  </div>

                  {/* Chart Style Toggles */}
                  <div className="flex flex-wrap gap-2">
                    {/* Chart Type selection */}
                    <div className="flex bg-slate-950/80 p-0.5 rounded-lg border border-slate-850">
                      {(['candles', 'heikin-ashi', 'renko', 'line-break'] as const).map((type) => (
                        <button
                          key={type}
                          onClick={() => setChartType(type)}
                          className={`px-3 py-1.5 rounded-md text-[10px] font-bold capitalize transition duration-150 cursor-pointer ${
                            chartType === type
                              ? 'bg-purple-600 text-white'
                              : 'text-slate-400 hover:text-slate-200'
                          }`}
                        >
                          {type.replace('-', ' ')}
                        </button>
                      ))}
                    </div>

                    {/* Sub-Pane Indicator Selection */}
                    <div className="flex bg-slate-950/80 p-0.5 rounded-lg border border-slate-850">
                      {(['RSI', 'MACD', 'NONE'] as const).map((ind) => (
                        <button
                          key={ind}
                          onClick={() => setIndicatorToShow(ind)}
                          className={`px-3 py-1.5 rounded-md text-[10px] font-bold transition duration-150 cursor-pointer ${
                            indicatorToShow === ind
                              ? 'bg-purple-600 text-white'
                              : 'text-slate-400 hover:text-slate-200'
                          }`}
                        >
                          {ind}
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
                  <PriceChart indicatorToShow={indicatorToShow} />
                  
                  {/* Multi-Pane Grid details */}
                  <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 min-h-[350px]">
                    <div className="xl:col-span-2">
                      <MetricsTable />
                    </div>
                    <div className="xl:col-span-1">
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
