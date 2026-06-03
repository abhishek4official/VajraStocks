import React, { useState, useEffect, useMemo } from 'react';
import { useStockStore } from '../store/useStockStore';
import { Search, RefreshCw, Radio, CheckCircle, AlertTriangle, ArrowUpDown } from 'lucide-react';

type SortOption = 'alpha' | 'last_sync';

export const Sidebar: React.FC = () => {
  const { 
    symbols, 
    activeSymbol, 
    setSelectedSymbol, 
    fetchSymbols, 
    triggerSymbolSync,
    isLoading
  } = useStockStore();

  const [searchTerm, setSearchTerm] = useState('');
  const [activeOnly, setActiveOnly] = useState(true);
  const [sortBy, setSortBy] = useState<SortOption>('alpha');
  const [syncingTicker, setSyncingTicker] = useState<string | null>(null);

  useEffect(() => {
    fetchSymbols(activeOnly);
  }, [activeOnly]);

  const filteredSymbols = useMemo(() => {
    const filtered = symbols.filter(sym =>
      sym.symbol.toLowerCase().includes(searchTerm.toLowerCase()) ||
      sym.symbol.replace('.NS', '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      sym.company_name.toLowerCase().includes(searchTerm.toLowerCase())
    );
    if (sortBy === 'last_sync') {
      return [...filtered].sort((a, b) => {
        const aDate = a.last_successful_sync_date ?? '';
        const bDate = b.last_successful_sync_date ?? '';
        return bDate.localeCompare(aDate); // most recently synced first
      });
    }
    return filtered; // default is already alphabetical from backend
  }, [symbols, searchTerm, sortBy]);

  const handleSyncSymbol = async (e: React.MouseEvent, symbol: string) => {
    e.stopPropagation(); // prevent card selection
    setSyncingTicker(symbol);
    try {
      await triggerSymbolSync(symbol);
    } catch (err) {
      console.error(err);
    } finally {
      setTimeout(() => setSyncingTicker(null), 2000);
    }
  };

  return (
    <div className="flex flex-col h-full border-r border-slate-800/80 bg-[#0d0f14] w-80 shrink-0">
      {/* Sidebar Header */}
      <div className="p-4 border-b border-slate-800/80 flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Radio className="w-5 h-5 text-purple-500 animate-pulse" />
            <h2 className="text-lg font-bold text-white tracking-tight">NSE Tickers</h2>
          </div>
          <button 
            onClick={() => fetchSymbols(activeOnly)}
            className="p-1.5 rounded-lg border border-slate-800 bg-slate-900/50 hover:bg-slate-800 text-slate-400 hover:text-white transition"
            title="Refresh List"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {/* Search Input */}
        <div className="relative">
          <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-500" />
          <input
            type="text"
            placeholder="Search symbol or company..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-4 py-2 text-sm rounded-lg bg-slate-900/80 border border-slate-850 text-white placeholder-slate-500 focus:outline-none focus:border-purple-500 transition"
          />
        </div>

        {/* Sort selector */}
        <div className="flex items-center gap-2">
          <ArrowUpDown className="w-3.5 h-3.5 text-slate-500 shrink-0" />
          <select
            value={sortBy}
            onChange={e => setSortBy(e.target.value as SortOption)}
            className="flex-1 px-2 py-1 text-xs rounded bg-slate-900/80 border border-slate-850 text-slate-300 focus:outline-none focus:border-purple-500 transition"
          >
            <option value="alpha">Sort: A → Z</option>
            <option value="last_sync">Sort: Last Synced</option>
          </select>
        </div>

        {/* Filter Toggle */}
        <div className="flex items-center justify-between text-xs text-slate-400 px-1">
          <span>Show Active Only</span>
          <button
            onClick={() => setActiveOnly(!activeOnly)}
            className={`w-9 h-5 rounded-full p-0.5 transition duration-200 ease-in-out focus:outline-none ${
              activeOnly ? 'bg-purple-600' : 'bg-slate-700'
            }`}
          >
            <div
              className={`w-4 h-4 rounded-full bg-white transform duration-200 ease-in-out ${
                activeOnly ? 'translate-x-4' : 'translate-x-0'
              }`}
            />
          </button>
        </div>
      </div>

      {/* Symbol Cards List */}
      <div className="flex-1 overflow-y-auto p-2 flex flex-col gap-1.5">
        {filteredSymbols.length === 0 ? (
          <div className="p-4 text-center text-slate-500 text-sm">
            No symbols found.
          </div>
        ) : (
          filteredSymbols.map((sym) => {
            const isSelected = activeSymbol === sym.symbol;
            const isSyncingThis = syncingTicker === sym.symbol;

            // Resolve Sync Health Status Badge
            const isSuccess = sym.last_attempt_status === 'SUCCESS';
            const isFailed = sym.last_attempt_status === 'FAILURE';

            return (
              <div
                key={sym.id}
                onClick={() => setSelectedSymbol(sym.symbol)}
                className={`group p-3 rounded-lg cursor-pointer transition relative border ${
                  isSelected 
                    ? 'bg-purple-950/20 border-purple-500/80 text-white' 
                    : 'bg-[#121620]/45 border-transparent text-slate-300 hover:bg-[#161a27] hover:border-slate-800'
                }`}
              >
                <div className="flex justify-between items-start mb-1">
                  <div className="flex items-center gap-1.5">
                    <span className="font-bold text-sm tracking-wide">{sym.symbol.replace('.NS', '')}</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-400 font-mono">
                      {sym.series}
                    </span>
                  </div>
                  
                  {/* Status indicator / manual trigger */}
                  <div className="flex items-center gap-2">
                    {isSuccess && (
                      <span title="Synchronized successfully">
                        <CheckCircle className="w-3.5 h-3.5 text-emerald-500" />
                      </span>
                    )}
                    {isFailed && (
                      <span title={`Last Sync Failed: ${sym.last_error_message || ''}`}>
                        <AlertTriangle className="w-3.5 h-3.5 text-rose-500" />
                      </span>
                    )}
                    
                    <button
                      onClick={(e) => handleSyncSymbol(e, sym.symbol)}
                      disabled={isSyncingThis}
                      className={`opacity-0 group-hover:opacity-100 p-1 rounded bg-slate-900 hover:bg-purple-900/40 text-slate-400 hover:text-purple-400 border border-slate-800/80 transition duration-150 ${
                        isSyncingThis ? 'opacity-100 animate-spin text-purple-400' : ''
                      }`}
                      title="Sync this symbol now"
                    >
                      <RefreshCw className="w-3 h-3" />
                    </button>
                  </div>
                </div>

                <div className="text-xs text-slate-400 truncate max-w-[220px]" title={sym.company_name}>
                  {sym.company_name}
                </div>

                {/* Footer Sync Date Meta */}
                {sym.last_successful_sync_date && (
                  <div className="text-[10px] text-slate-500 font-mono mt-1">
                    Sync: {sym.last_successful_sync_date}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
