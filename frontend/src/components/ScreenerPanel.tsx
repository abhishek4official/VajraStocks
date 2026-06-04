import React, { useEffect, useState, useMemo } from 'react';
import { useStockStore } from '../store/useStockStore';
import { Play, Eye, Filter, RefreshCw, BarChart2, Download, Bookmark, Zap } from 'lucide-react';
import type { ScreenerRow } from '../services/api';

// ── Screener presets ─────────────────────────────────────────────────────────
const PRESETS = [
  {
    name: 'Breakout Scanner',
    emoji: '🚀',
    desc: 'Vol >2x + SMA 200 above + HA bullish',
    filters: { volume_breakout: '2.0X' as const, sma_200_cross: 'ABOVE' as const, ha_dir: 'UP' as const },
  },
  {
    name: 'Momentum',
    emoji: '⚡',
    desc: 'RSI 55-75 + MACD bullish + all SMAs above',
    filters: { min_rsi: 55, max_rsi: 75, macd_trend: 'BULLISH' as const, sma_20_cross: 'ABOVE' as const, sma_50_cross: 'ABOVE' as const, sma_200_cross: 'ABOVE' as const },
  },
  {
    name: 'Pullback to SMA20',
    emoji: '📉',
    desc: 'RSI 40-55 + MACD bullish + SMA 200 above',
    filters: { min_rsi: 40, max_rsi: 55, macd_trend: 'BULLISH' as const, sma_200_cross: 'ABOVE' as const },
  },
  {
    name: 'Oversold Bounce',
    emoji: '🔄',
    desc: 'RSI <35 + SMA 200 above',
    filters: { max_rsi: 35, sma_200_cross: 'ABOVE' as const },
  },
  {
    name: 'Volume Surge',
    emoji: '📊',
    desc: 'Vol >3x average — unusual activity',
    filters: { volume_breakout: '3.0X' as const },
  },
  {
    name: 'Swing Reversal',
    emoji: '↩️',
    desc: 'RSI <45 + Renko DOWN reversal candidates',
    filters: { max_rsi: 45, renko_dir: 'DOWN' as const },
  },
  {
    name: 'NR7 Squeeze',
    emoji: '🎯',
    desc: 'Narrowest range of last 7 days — pre-breakout compression',
    filters: { only_nr7: true },
  },
  {
    name: 'Inside Bar',
    emoji: '📦',
    desc: 'Low-risk entry with well-defined stop loss',
    filters: { only_inside_bar: true },
  },
  {
    name: 'Gap Up',
    emoji: '⬆️',
    desc: 'Opened >1% above yesterday\'s close on high volume',
    filters: { only_gap_up: true, volume_breakout: '1.5X' as const },
  },
  {
    name: 'RS Leaders',
    emoji: '🏆',
    desc: 'Outperforming NIFTY 50 by >20% over 1 month (RS > 1.2)',
    filters: { min_rs_1m: 1.2, sma_200_cross: 'ABOVE' as const },
  },
];

export const ScreenerPanel: React.FC = () => {
  const {
    screenerFilters,
    screenerResults,
    setScreenerFilters,
    runScreener,
    isLoading,
    setActiveTab,
    setSelectedSymbol,
    watchlists,
    addToWatchlist,
  } = useStockStore();

  // Client-side sorting + pagination states
  const [sortField, setSortField] = useState<keyof ScreenerRow | null>(null);
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');
  const [visibleCount, setVisibleCount] = useState(50);
  const PAGE_SIZE = 50;
  const [searchQuery, setSearchQuery] = useState('');
  const [showFilters, setShowFilters] = useState(false);

  useEffect(() => { runScreener(); }, []);
  // Reset to first page whenever results or search query updates
  useEffect(() => { setVisibleCount(PAGE_SIZE); }, [screenerResults, searchQuery]);

  const handleRunScreener = () => {
    runScreener();
    setShowFilters(false);
  };

  // Navigate in-place to the Explorer Dashboard for the selected symbol
  const handleSelectScreenerMatch = async (symbol: string) => {
    await setSelectedSymbol(symbol);
    setActiveTab('explorer');
  };

  // Add ticker to the first watchlist (or the only one if one exists)
  const handleAddToWatchlist = (symbol: string) => {
    const target = watchlists[0];
    if (target) addToWatchlist(target.id, symbol);
  };

  const formatNumber = (val: number | null | undefined, decimals = 2) => {
    if (val === null || val === undefined) return '-';
    return Number(val).toFixed(decimals);
  };

  const formatVolume = (vol: number | null | undefined) => {
    if (vol === null || vol === undefined) return '-';
    if (vol >= 1000000) return `${(vol / 1000000).toFixed(2)}M`;
    if (vol >= 1000) return `${(vol / 1000).toFixed(1)}K`;
    return vol.toString();
  };

  // Sorting Handler
  const handleSort = (field: keyof ScreenerRow) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  // Sorting Icon Renderer
  const renderSortIcon = (field: keyof ScreenerRow) => {
    if (sortField !== field) return <span className="text-slate-650 ml-1 text-[10px]">↕</span>;
    return sortDirection === 'asc' 
      ? <span className="text-purple-400 ml-1 text-[9px]">▲</span> 
      : <span className="text-purple-400 ml-1 text-[9px]">▼</span>;
  };

  // Sorted Results Memo
  const sortedResults = useMemo(() => {
    if (!sortField) return screenerResults;

    return [...screenerResults].sort((a, b) => {
      const aVal = a[sortField];
      const bVal = b[sortField];

      if (aVal === undefined || aVal === null) return sortDirection === 'asc' ? 1 : -1;
      if (bVal === undefined || bVal === null) return sortDirection === 'asc' ? -1 : 1;

      if (typeof aVal === 'string' && typeof bVal === 'string') {
        return sortDirection === 'asc' 
          ? aVal.localeCompare(bVal) 
          : bVal.localeCompare(aVal);
      }

      return sortDirection === 'asc'
        ? (aVal as number) - (bVal as number)
        : (bVal as number) - (aVal as number);
    });
  }, [screenerResults, sortField, sortDirection]);

  // Filtered Results Memo (applies client-side search query)
  const filteredResults = useMemo(() => {
    if (!searchQuery.trim()) return sortedResults;
    const query = searchQuery.toLowerCase().trim();
    return sortedResults.filter(
      row => row.symbol.toLowerCase().includes(query) || 
             row.company_name.toLowerCase().includes(query)
    );
  }, [sortedResults, searchQuery]);

  // CSV Exporter
  const exportToCSV = () => {
    if (screenerResults.length === 0) return;

    const headers = [
      'Ticker', 'Company Name', 'Last EOD Price', 'Change %',
      'Weekly Avg Vol', 'Vol Breakout', 'RSI (14)', 'SMA 20',
      'SMA 50', 'SMA 200', 'MACD Trend', 'Heikin Ashi', 'Renko', 'Three Line Break', 'RS 1M',
      'Stop', 'T1', 'T2', 'T3', 'Upside %', 'R:R', 'TQS', 'Shares'
    ];

    const rows = filteredResults.map(row => [
      row.symbol.replace('.NS', ''),
      `"${row.company_name.replace(/"/g, '""')}"`,
      row.close_price,
      row.price_pct_change ?? '',
      row.weekly_avg_volume ?? '',
      row.volume_breakout_ratio ?? '',
      row.rsi_14 ?? '',
      row.sma_20_cross_direction ?? '',
      row.sma_50_cross_direction ?? '',
      row.sma_200_cross_direction ?? '',
      row.macd_trend ?? '',
      row.ha_direction ?? '',
      row.renko_direction ?? '',
      row.line_break_direction ?? '',
      (row as any).rs_score_1m ?? '',
      row.stop_loss ?? '',
      row.target_1 ?? '',
      row.target_2 ?? '',
      row.target_3 ?? '',
      row.potential_gain_pct ?? '',
      row.rr_ratio ?? '',
      row.trade_quality_score ?? '',
      row.position_size_shares ?? ''
    ]);

    const csvContent = [
      headers.join(','),
      ...rows.map(e => e.join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `Stock_Screener_Export_${new Date().toISOString().split('T')[0]}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="flex-1 flex flex-col gap-4 p-5 overflow-y-auto max-h-full">
      {/* Header Banner */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            <Filter className="w-5 h-5 text-purple-500" />
            Stock Screening Suite
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Execute sub-5ms screening sweeps directly against our high-speed EOD snapshot layers.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-bold transition cursor-pointer border ${
              showFilters 
                ? 'bg-purple-950/40 border-purple-500 text-purple-200' 
                : 'bg-slate-800 border-slate-700 text-slate-300 hover:text-white hover:bg-slate-700'
            }`}
          >
            <Filter className="w-4 h-4" />
            {showFilters ? 'Hide Filters' : 'Show Filters'}
          </button>
          <button
            onClick={exportToCSV}
            disabled={screenerResults.length === 0}
            className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed text-slate-300 hover:text-white border border-slate-700 rounded-lg text-sm font-bold transition cursor-pointer"
            title="Export filtered results to CSV file"
          >
            <Download className="w-4 h-4" />
            Export CSV
          </button>
          <button
            onClick={handleRunScreener}
            disabled={isLoading}
            className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-500 disabled:bg-purple-800 text-white rounded-lg text-sm font-bold shadow-lg shadow-purple-900/25 hover:shadow-purple-500/25 transition cursor-pointer"
          >
            <Play className="w-4 h-4 fill-white" />
            Run Filter Sweep
          </button>
        </div>
      </div>

      {/* ── Preset Cards ──────────────────────────────────────────────────── */}
      <div className="flex flex-wrap gap-2">
        {PRESETS.map(p => (
          <button
            key={p.name}
            onClick={() => {
              // Reset all filters then apply preset
              setScreenerFilters({
                min_rsi: undefined, max_rsi: undefined,
                min_price: undefined, max_price: undefined,
                sma_20_cross: undefined, sma_50_cross: undefined, sma_200_cross: undefined,
                macd_trend: undefined, ha_dir: undefined, renko_dir: undefined, lb_dir: undefined,
                volume_breakout: undefined, min_weekly_avg_volume: undefined,
                only_nr7: undefined,
                only_inside_bar: undefined,
                only_gap_up: undefined,
                only_gap_down: undefined,
                min_rs_1m: undefined,
                ...p.filters,
              });
              runScreener();
              setShowFilters(false);
            }}
            disabled={isLoading}
            className="flex items-center gap-2 px-3 py-2 rounded-xl border border-slate-800/80 bg-[#121620]/30 hover:bg-[#121620]/70 hover:border-purple-500/40 disabled:opacity-40 transition cursor-pointer text-left"
          >
            <span className="text-base leading-none">{p.emoji}</span>
            <div>
              <div className="text-xs font-bold text-white flex items-center gap-1">
                <Zap className="w-2.5 h-2.5 text-purple-400" />
                {p.name}
              </div>
              <div className="text-[10px] text-slate-500">{p.desc}</div>
            </div>
          </button>
        ))}
      </div>

      {/* Organized Filter Grid (Toggleable) */}
      {showFilters && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 p-5 rounded-xl border border-slate-800/80 bg-[#121620]/30 shadow-inner">
          
          {/* Column 1: Price & Volume */}
          <div className="flex flex-col gap-4 lg:border-r border-slate-850 lg:pr-4">
            <h4 className="text-xs font-bold uppercase tracking-wider text-purple-400 flex items-center gap-1.5 mb-1 select-none">
              <BarChart2 className="w-3.5 h-3.5 text-purple-500" /> Price & Volume
            </h4>
            
            <div className="flex flex-col gap-1.5">
              <label className="text-[11px] font-semibold text-slate-400">Min Weekly Avg Vol</label>
              <input
                type="number"
                placeholder="No Limit"
                value={screenerFilters.min_weekly_avg_volume !== undefined ? screenerFilters.min_weekly_avg_volume : ''}
                onChange={(e) => setScreenerFilters({ 
                  min_weekly_avg_volume: e.target.value === '' ? undefined : Number(e.target.value) 
                })}
                className="w-full px-3 py-1.5 text-xs rounded bg-slate-900 border border-slate-800 text-white focus:outline-none focus:border-purple-500 transition"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-[11px] font-semibold text-slate-400">Volume Breakout</label>
              <select
                value={screenerFilters.volume_breakout || 'ANY'}
                onChange={(e) => setScreenerFilters({ 
                  volume_breakout: e.target.value === 'ANY' ? undefined : e.target.value as any 
                })}
                className="w-full px-3 py-1.5 text-xs rounded bg-slate-900 border border-slate-800 text-white focus:outline-none focus:border-purple-500 transition"
              >
                <option value="ANY">Any Volume</option>
                <option value="1.5X">1.5x Breakout</option>
                <option value="2.0X">2.0x Breakout</option>
                <option value="3.0X">3.0x Breakout</option>
              </select>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div className="flex flex-col gap-1.5">
                <label className="text-[11px] font-semibold text-slate-400">Min Price (₹)</label>
                <input
                  type="number"
                  placeholder="No Limit"
                  value={screenerFilters.min_price !== undefined ? screenerFilters.min_price : ''}
                  onChange={(e) => setScreenerFilters({ min_price: e.target.value === '' ? undefined : Number(e.target.value) })}
                  className="w-full px-3 py-1.5 text-xs rounded bg-slate-900 border border-slate-800 text-white focus:outline-none focus:border-purple-500 transition"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-[11px] font-semibold text-slate-400">Max Price (₹)</label>
                <input
                  type="number"
                  placeholder="No Limit"
                  value={screenerFilters.max_price !== undefined ? screenerFilters.max_price : ''}
                  onChange={(e) => setScreenerFilters({ max_price: e.target.value === '' ? undefined : Number(e.target.value) })}
                  className="w-full px-3 py-1.5 text-xs rounded bg-slate-900 border border-slate-800 text-white focus:outline-none focus:border-purple-500 transition"
                />
              </div>
            </div>
          </div>

          {/* Column 2: Moving Averages & RSI */}
          <div className="flex flex-col gap-4 lg:border-r border-slate-850 lg:pr-4">
            <h4 className="text-xs font-bold uppercase tracking-wider text-purple-400 flex items-center gap-1.5 mb-1 select-none">
              <Zap className="w-3.5 h-3.5 text-purple-500" /> Averages & RSI
            </h4>

            <div className="grid grid-cols-2 gap-2">
              <div className="flex flex-col gap-1.5">
                <label className="text-[11px] font-semibold text-slate-400">Min RSI (14)</label>
                <input
                  type="number"
                  placeholder="No Limit"
                  value={screenerFilters.min_rsi !== undefined ? screenerFilters.min_rsi : ''}
                  onChange={(e) => setScreenerFilters({ 
                    min_rsi: e.target.value === '' ? undefined : Number(e.target.value) 
                  })}
                  className="w-full px-3 py-1.5 text-xs rounded bg-slate-900 border border-slate-800 text-white focus:outline-none focus:border-purple-500 transition"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-[11px] font-semibold text-slate-400">Max RSI (14)</label>
                <input
                  type="number"
                  placeholder="No Limit"
                  value={screenerFilters.max_rsi !== undefined ? screenerFilters.max_rsi : ''}
                  onChange={(e) => setScreenerFilters({ 
                    max_rsi: e.target.value === '' ? undefined : Number(e.target.value) 
                  })}
                  className="w-full px-3 py-1.5 text-xs rounded bg-slate-900 border border-slate-800 text-white focus:outline-none focus:border-purple-500 transition"
                />
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-[11px] font-semibold text-slate-400">SMA 20 Cross</label>
              <select
                value={screenerFilters.sma_20_cross || 'ANY'}
                onChange={(e) => setScreenerFilters({ 
                  sma_20_cross: e.target.value === 'ANY' ? undefined : e.target.value as any 
                })}
                className="w-full px-3 py-1.5 text-xs rounded bg-slate-900 border border-slate-800 text-white focus:outline-none focus:border-purple-500 transition"
              >
                <option value="ANY">Any Position</option>
                <option value="ABOVE">Above SMA 20</option>
                <option value="BELOW">Below SMA 20</option>
              </select>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-[11px] font-semibold text-slate-400">SMA 50 Cross</label>
              <select
                value={screenerFilters.sma_50_cross || 'ANY'}
                onChange={(e) => setScreenerFilters({ 
                  sma_50_cross: e.target.value === 'ANY' ? undefined : e.target.value as any 
                })}
                className="w-full px-3 py-1.5 text-xs rounded bg-slate-900 border border-slate-800 text-white focus:outline-none focus:border-purple-500 transition"
              >
                <option value="ANY">Any Position</option>
                <option value="ABOVE">Above SMA 50</option>
                <option value="BELOW">Below SMA 50</option>
              </select>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-[11px] font-semibold text-slate-400">SMA 200 Cross</label>
              <select
                value={screenerFilters.sma_200_cross || 'ANY'}
                onChange={(e) => setScreenerFilters({ 
                  sma_200_cross: e.target.value === 'ANY' ? undefined : e.target.value as any 
                })}
                className="w-full px-3 py-1.5 text-xs rounded bg-slate-900 border border-slate-800 text-white focus:outline-none focus:border-purple-500 transition"
              >
                <option value="ANY">Any Position</option>
                <option value="ABOVE">Above SMA 200</option>
                <option value="BELOW">Below SMA 200</option>
              </select>
            </div>
          </div>

          {/* Column 3: Trend Signals */}
          <div className="flex flex-col gap-4 lg:border-r border-slate-850 lg:pr-4">
            <h4 className="text-xs font-bold uppercase tracking-wider text-purple-400 flex items-center gap-1.5 mb-1 select-none">
              <Eye className="w-3.5 h-3.5 text-purple-500" /> Trend Signals
            </h4>

            <div className="flex flex-col gap-1.5">
              <label className="text-[11px] font-semibold text-slate-400">MACD Trend</label>
              <select
                value={screenerFilters.macd_trend || 'ANY'}
                onChange={(e) => setScreenerFilters({ 
                  macd_trend: e.target.value === 'ANY' ? undefined : e.target.value as any 
                })}
                className="w-full px-3 py-1.5 text-xs rounded bg-slate-900 border border-slate-800 text-white focus:outline-none focus:border-purple-500 transition"
              >
                <option value="ANY">Any Trend</option>
                <option value="BULLISH">Bullish (MACD &gt; Sig)</option>
                <option value="BEARISH">Bearish (MACD &lt; Sig)</option>
              </select>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-[11px] font-semibold text-slate-400">Heikin Ashi Trend</label>
              <select
                value={screenerFilters.ha_dir || 'ANY'}
                onChange={(e) => setScreenerFilters({ 
                  ha_dir: e.target.value === 'ANY' ? undefined : e.target.value as any 
                })}
                className="w-full px-3 py-1.5 text-xs rounded bg-slate-900 border border-slate-800 text-white focus:outline-none focus:border-purple-500 transition"
              >
                <option value="ANY">Any Trend</option>
                <option value="UP">Bullish (UP)</option>
                <option value="DOWN">Bearish (DOWN)</option>
              </select>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-[11px] font-semibold text-slate-400">Renko Brick</label>
              <select
                value={screenerFilters.renko_dir || 'ANY'}
                onChange={(e) => setScreenerFilters({ 
                  renko_dir: e.target.value === 'ANY' ? undefined : e.target.value as any 
                })}
                className="w-full px-3 py-1.5 text-xs rounded bg-slate-900 border border-slate-800 text-white focus:outline-none focus:border-purple-500 transition"
              >
                <option value="ANY">Any Direction</option>
                <option value="UP">Bullish (UP)</option>
                <option value="DOWN">Bearish (DOWN)</option>
              </select>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-[11px] font-semibold text-slate-400">Three Line Break</label>
              <select
                value={screenerFilters.lb_dir || 'ANY'}
                onChange={(e) => setScreenerFilters({
                  lb_dir: e.target.value === 'ANY' ? undefined : e.target.value as any
                })}
                className="w-full px-3 py-1.5 text-xs rounded bg-slate-900 border border-slate-800 text-white focus:outline-none focus:border-purple-500 transition"
              >
                <option value="ANY">Any Direction</option>
                <option value="UP">Bullish (UP)</option>
                <option value="DOWN">Bearish (DOWN)</option>
              </select>
            </div>
          </div>

          {/* Column 4: Strength & Patterns */}
          <div className="flex flex-col gap-4">
            <h4 className="text-xs font-bold uppercase tracking-wider text-purple-400 flex items-center gap-1.5 mb-1 select-none">
              <Filter className="w-3.5 h-3.5 text-purple-500" /> Patterns & RS
            </h4>

            <div className="flex flex-col gap-1.5">
              <label className="text-[11px] font-semibold text-slate-400">Min RS vs NIFTY</label>
              <input
                type="number"
                step="0.1"
                placeholder="e.g. 1.2"
                value={screenerFilters.min_rs_1m !== undefined ? screenerFilters.min_rs_1m : ''}
                onChange={(e) => setScreenerFilters({ min_rs_1m: e.target.value === '' ? undefined : Number(e.target.value) })}
                className="w-full px-3 py-1.5 text-xs rounded bg-slate-900 border border-slate-800 text-white focus:outline-none focus:border-purple-500 transition"
              />
              <span className="text-[10px] text-slate-500">1.0 = matches NIFTY · &gt;1.2 = outperforming</span>
            </div>

            <div className="flex flex-col gap-1.5 mt-1.5">
              <label className="text-[11px] font-semibold text-slate-400">Patterns</label>
              <div className="grid grid-cols-2 gap-x-2 gap-y-3 mt-1">
                {([
                  { key: 'only_nr7' as const,       label: 'NR7 only'       },
                  { key: 'only_inside_bar' as const, label: 'Inside Bar'     },
                  { key: 'only_gap_up' as const,     label: 'Gap Up (>1%)'   },
                  { key: 'only_gap_down' as const,   label: 'Gap Down (>1%)' },
                ]).map(({ key, label }) => (
                  <label key={key} className="flex items-center gap-2 cursor-pointer select-none group">
                    <input
                      type="checkbox"
                      checked={!!screenerFilters[key]}
                      onChange={(e) => setScreenerFilters({ [key]: e.target.checked || undefined })}
                      className="accent-purple-500 w-3.5 h-3.5 cursor-pointer rounded"
                    />
                    <span className="text-xs text-slate-300 group-hover:text-white transition">{label}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Results Grid Table */}
      <div className="flex-1 bg-[#121620]/60 rounded-xl border border-slate-800/80 p-4 overflow-hidden flex flex-col min-h-[300px]">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-800 mb-3 shrink-0">
          <h3 className="text-sm font-bold text-white tracking-wide flex items-center gap-1.5">
            <BarChart2 className="w-4 h-4 text-purple-400" />
            Matching Stocks
            <span className="font-mono text-xs text-slate-400 font-normal">
              ({filteredResults.length.toLocaleString()} result{filteredResults.length !== 1 ? 's' : ''})
            </span>
          </h3>
          <div className="flex items-center gap-3">
            <div className="relative">
              <input
                type="text"
                placeholder="Search ticker or company..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-48 sm:w-64 pl-8 pr-3 py-1 text-xs rounded bg-slate-900 border border-slate-800 text-white placeholder-slate-500 focus:outline-none focus:border-purple-500 transition"
              />
              <svg className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-1/2 -translate-y-1/2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
            {isLoading && <RefreshCw className="w-3.5 h-3.5 text-purple-400 animate-spin" />}
          </div>
        </div>

        <div className="flex-1 overflow-auto flex flex-col">
          <table className="min-w-max w-full border-collapse text-left text-xs text-slate-300">
            <thead>
              <tr className="border-b border-slate-800 text-xs text-slate-400 uppercase tracking-wider font-mono select-none whitespace-nowrap">
                <th className="py-2 px-1.5 cursor-pointer hover:text-white transition" onClick={() => handleSort('symbol')}>
                  Ticker {renderSortIcon('symbol')}
                </th>
                <th className="py-2 px-1.5 cursor-pointer hover:text-white transition" title="Company Name" onClick={() => handleSort('company_name')}>
                  Company {renderSortIcon('company_name')}
                </th>
                <th className="py-2 px-1.5 cursor-pointer hover:text-white transition" title="Last End of Day Price" onClick={() => handleSort('close_price')}>
                  Price {renderSortIcon('close_price')}
                </th>
                <th className="py-2 px-1.5 cursor-pointer hover:text-white transition" title="Price Percentage Change" onClick={() => handleSort('price_pct_change')}>
                  Chg% {renderSortIcon('price_pct_change')}
                </th>
                <th className="py-2 px-1.5 cursor-pointer hover:text-white transition" title="Composite Bias (5-tier: VERY_BULLISH / BULLISH / NEUTRAL / BEARISH / VERY_BEARISH) — sort by composite score" onClick={() => handleSort('composite_score' as any)}>
                  Bias {renderSortIcon('composite_score' as any)}
                </th>
                <th className="py-2 px-1 text-right cursor-pointer hover:text-white transition" title="1-week rolling return" onClick={() => handleSort('ret_1w')}>
                  1W {renderSortIcon('ret_1w')}
                </th>
                <th className="py-2 px-1 text-right cursor-pointer hover:text-white transition" title="2-week rolling return" onClick={() => handleSort('ret_2w')}>
                  2W {renderSortIcon('ret_2w')}
                </th>
                <th className="py-2 px-1 text-right cursor-pointer hover:text-white transition" title="3-week rolling return" onClick={() => handleSort('ret_3w')}>
                  3W {renderSortIcon('ret_3w')}
                </th>
                <th className="py-2 px-1 text-right cursor-pointer hover:text-white transition" title="4-week rolling return" onClick={() => handleSort('ret_4w')}>
                  4W {renderSortIcon('ret_4w')}
                </th>
                <th className="py-2 px-1 text-right cursor-pointer hover:text-white transition" title="Stop Loss (Close - 1.5 * ATR)" onClick={() => handleSort('stop_loss')}>
                  Stop {renderSortIcon('stop_loss')}
                </th>
                <th className="py-2 px-1 text-right cursor-pointer hover:text-white transition" title="Target 1 — strongest structural resistance above price" onClick={() => handleSort('target_1')}>
                  T1 {renderSortIcon('target_1')}
                </th>
                <th className="py-2 px-1 text-right cursor-pointer hover:text-white transition" title="Target 2 — next structural resistance above T1" onClick={() => handleSort('target_2' as any)}>
                  T2 {renderSortIcon('target_2' as any)}
                </th>
                <th className="py-2 px-1 text-right cursor-pointer hover:text-white transition" title="Target 3 — third structural resistance" onClick={() => handleSort('target_3' as any)}>
                  T3 {renderSortIcon('target_3' as any)}
                </th>
                <th className="py-2 px-1 text-right cursor-pointer hover:text-white transition" title="Potential Gain % to Target 1" onClick={() => handleSort('potential_gain_pct')}>
                  Upside {renderSortIcon('potential_gain_pct')}
                </th>
                <th className="py-2 px-1 text-right cursor-pointer hover:text-white transition" title="Risk-to-Reward Ratio" onClick={() => handleSort('rr_ratio')}>
                  R:R {renderSortIcon('rr_ratio')}
                </th>
                <th className="py-2 px-1 text-right cursor-pointer hover:text-white transition" title="Trade Quality Score (0–100): Trend + Momentum + RS + Volume + R:R" onClick={() => handleSort('trade_quality_score' as any)}>
                  TQS {renderSortIcon('trade_quality_score' as any)}
                </th>
                <th className="py-2 px-1 text-right cursor-pointer hover:text-white transition" title="Suggested position size (shares) based on risk budget ÷ stop distance" onClick={() => handleSort('position_size_shares' as any)}>
                  Shares {renderSortIcon('position_size_shares' as any)}
                </th>
                <th className="py-2 px-1.5 text-right cursor-pointer hover:text-white transition" title="Weekly Average Volume" onClick={() => handleSort('weekly_avg_volume')}>
                  Avg Vol {renderSortIcon('weekly_avg_volume')}
                </th>
                <th className="py-2 px-1.5 text-center cursor-pointer hover:text-white transition" title="Volume Breakout Ratio" onClick={() => handleSort('volume_breakout_ratio')}>
                  Vol Brk {renderSortIcon('volume_breakout_ratio')}
                </th>
                <th className="py-2 px-1.5 text-center cursor-pointer hover:text-white transition" title="Relative Strength Index (14)" onClick={() => handleSort('rsi_14')}>
                  RSI {renderSortIcon('rsi_14')}
                </th>
                <th className="py-2 px-1.5 text-center cursor-pointer hover:text-white transition" title="SMA 20 position" onClick={() => handleSort('sma_20_cross_direction')}>
                  S20 {renderSortIcon('sma_20_cross_direction')}
                </th>
                <th className="py-2 px-1.5 text-center cursor-pointer hover:text-white transition" title="SMA 50 position" onClick={() => handleSort('sma_50_cross_direction')}>
                  S50 {renderSortIcon('sma_50_cross_direction')}
                </th>
                <th className="py-2 px-1.5 text-center cursor-pointer hover:text-white transition" title="SMA 200 position" onClick={() => handleSort('sma_200_cross_direction')}>
                  S200 {renderSortIcon('sma_200_cross_direction')}
                </th>
                <th className="py-2 px-1.5 text-center cursor-pointer hover:text-white transition" title="MACD Trend (BULLISH / BEARISH)" onClick={() => handleSort('macd_trend')}>
                  MACD {renderSortIcon('macd_trend')}
                </th>
                <th className="py-2 px-1.5 text-center cursor-pointer hover:text-white transition" title="Heikin Ashi Direction (UP / DOWN)" onClick={() => handleSort('ha_direction')}>
                  HA {renderSortIcon('ha_direction')}
                </th>
                <th className="py-2 px-1.5 text-center cursor-pointer hover:text-white transition" title="Renko Brick Direction (UP / DOWN)" onClick={() => handleSort('renko_direction')}>
                  Renko {renderSortIcon('renko_direction')}
                </th>
                <th className="py-2 px-1.5 text-center cursor-pointer hover:text-white transition" title="Three Line Break Direction (UP / DOWN)" onClick={() => handleSort('line_break_direction')}>
                  TLB {renderSortIcon('line_break_direction')}
                </th>
                <th className="py-2 px-1.5 text-center cursor-pointer hover:text-white transition" title="1-Month Relative Strength vs NIFTY 50" onClick={() => handleSort('rs_score_1m' as any)}>
                  RS 1M {renderSortIcon('rs_score_1m' as any)}
                </th>
                <th className="py-2 px-1.5 text-center" title="Pattern triggers">Patterns</th>
                <th className="py-2 px-1.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-850">
              {filteredResults.length === 0 ? (
                <tr>
                  <td colSpan={30} className="py-10 text-center text-slate-500 text-xs">
                    {isLoading 
                      ? 'Executing database snapshot sweep...' 
                      : 'No stock matches found for the current criteria.'}
                  </td>
                </tr>
              ) : (
                filteredResults.slice(0, visibleCount).map((row) => {
                  const isChangeBullish = (row.price_pct_change || 0) >= 0;
                  const isHaBullish = row.ha_direction === 'UP';
                  const isRenkoBullish = row.renko_direction === 'UP';
                  const isLbBullish = row.line_break_direction === 'UP';
                  
                  return (
                    <tr key={row.symbol_id} className="hover:bg-slate-900/40 transition whitespace-nowrap text-xs">
                      {/* Ticker */}
                      <td className="py-2 px-1.5 font-bold text-white font-mono">
                        {row.symbol.replace('.NS', '')}
                      </td>
                      
                      {/* Company Name */}
                      <td className="py-2 px-1.5 text-slate-400 truncate max-w-[100px]" title={row.company_name}>
                        {row.company_name}
                      </td>
                      
                      {/* Price */}
                      <td className="py-2 px-1.5 font-mono font-semibold">
                        ₹{formatNumber(row.close_price)}
                      </td>
                      
                      {/* Change */}
                      <td className={`py-2 px-1.5 font-mono ${isChangeBullish ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {isChangeBullish ? '+' : ''}{formatNumber(row.price_pct_change)}%
                      </td>

                      {/* Bias chip */}
                      <td className="py-2 px-1.5">
                        {(() => {
                          const bias = (row as any).regime_bias as string | null | undefined;
                          const score = (row as any).composite_score as number | null | undefined;
                          const trend = (row as any).trend_score_val as number | null | undefined;
                          const vol   = (row as any).volume_score_val as number | null | undefined;
                          const rs    = (row as any).rs_score_val as number | null | undefined;
                          const mom   = (row as any).momentum_score_val as number | null | undefined;
                          const tooltip = score != null
                            ? `Score: ${score.toFixed(1)}\nTrend: ${trend?.toFixed(0) ?? '—'}  Volume: ${vol?.toFixed(0) ?? '—'}  RS: ${rs?.toFixed(0) ?? '—'}  Momentum: ${mom?.toFixed(0) ?? '—'}`
                            : bias ?? '—';
                          const cfg: Record<string, { bg: string; text: string; label: string }> = {
                            VERY_BULLISH: { bg: 'bg-emerald-500/20 border-emerald-400/50', text: 'text-emerald-200', label: 'VB+' },
                            BULLISH:      { bg: 'bg-emerald-500/10 border-emerald-500/30', text: 'text-emerald-400', label: 'Bull' },
                            NEUTRAL:      { bg: 'bg-slate-700/40 border-slate-600/40',     text: 'text-slate-400',  label: 'Neut' },
                            BEARISH:      { bg: 'bg-rose-500/10 border-rose-500/30',        text: 'text-rose-400',   label: 'Bear' },
                            VERY_BEARISH: { bg: 'bg-rose-500/20 border-rose-400/50',        text: 'text-rose-200',   label: 'VB-' },
                          };
                          const c = bias ? (cfg[bias] ?? cfg['NEUTRAL']) : null;
                          if (!c) return <span className="text-slate-600">—</span>;
                          return (
                            <span
                              title={tooltip}
                              className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[10px] font-bold whitespace-nowrap ${c.bg} ${c.text}`}
                            >
                              {c.label}
                              {score != null && (
                                <span className="opacity-70 font-mono">{score.toFixed(0)}</span>
                              )}
                            </span>
                          );
                        })()}
                      </td>

                      {/* Rolling weekly returns 1W/2W/3W/4W */}
                      {[row.ret_1w, row.ret_2w, row.ret_3w, row.ret_4w].map((r, i) => (
                        <td key={i} className={`py-2 px-1 text-right font-mono text-xs ${
                          r === null || r === undefined ? 'text-slate-650' : r >= 0 ? 'text-emerald-400' : 'text-rose-400'
                        }`}>
                          {r === null || r === undefined ? '—' : `${r >= 0 ? '+' : ''}${r.toFixed(1)}%`}
                        </td>
                      ))}

                      {/* ATR-based trade setup: Stop / Target 1 / Upside% */}
                      <td className="py-2 px-1 text-right font-mono text-xs text-rose-400/80">
                        {row.stop_loss == null ? '—' : `₹${formatNumber(row.stop_loss, 1)}`}
                      </td>
                      <td className="py-2 px-1 text-right font-mono text-xs text-emerald-400/90">
                        {row.target_1 == null ? '—' : `₹${formatNumber(row.target_1, 1)}`}
                      </td>
                      <td className="py-2 px-1 text-right font-mono text-xs text-emerald-400/60">
                        {row.target_2 == null ? '—' : `₹${formatNumber(row.target_2, 1)}`}
                      </td>
                      <td className="py-2 px-1 text-right font-mono text-xs text-emerald-400/40">
                        {row.target_3 == null ? '—' : `₹${formatNumber(row.target_3, 1)}`}
                      </td>
                      <td className="py-2 px-1 text-right font-mono text-xs text-emerald-400">
                        {row.potential_gain_pct == null ? '—' : `+${row.potential_gain_pct.toFixed(1)}%`}
                      </td>

                      {/* R:R Ratio */}
                      <td className="py-2 px-1 text-right font-mono text-xs">
                        {row.rr_ratio !== undefined && row.rr_ratio !== null ? (
                          <span className={`px-1 py-0.2 rounded font-bold ${
                            row.rr_ratio >= 2.0
                              ? 'text-emerald-400 bg-emerald-950/20'
                              : row.rr_ratio >= 1.0
                              ? 'text-indigo-400 bg-[#121620]'
                              : 'text-rose-400 bg-rose-950/20'
                          }`}>
                            {row.rr_ratio.toFixed(2)}x
                          </span>
                        ) : <span className="text-slate-600">—</span>}
                      </td>

                      {/* Trade Quality Score */}
                      <td className="py-2 px-1 text-right font-mono text-xs">
                        {row.trade_quality_score != null ? (
                          <span className={`px-1 rounded font-bold ${
                            row.trade_quality_score >= 70
                              ? 'text-emerald-400 bg-emerald-950/20'
                              : row.trade_quality_score >= 50
                              ? 'text-amber-400 bg-amber-950/20'
                              : 'text-rose-400 bg-rose-950/20'
                          }`}>
                            {row.trade_quality_score.toFixed(0)}
                          </span>
                        ) : <span className="text-slate-600">—</span>}
                      </td>

                      {/* Position Size */}
                      <td className="py-2 px-1 text-right font-mono text-xs text-purple-400">
                        {row.position_size_shares != null ? row.position_size_shares.toLocaleString('en-IN') : '—'}
                      </td>

                      {/* Weekly Avg Vol */}
                      <td className="py-2 px-1.5 text-right font-mono text-slate-350">
                        {formatVolume(row.weekly_avg_volume)}
                      </td>
                      
                      {/* Volume Breakout Badge */}
                      <td className="py-2 px-1.5 text-center">
                        <span className={`font-mono text-xs px-1 py-0.2 rounded border inline-block ${
                          (row.volume_breakout_ratio || 0) >= 3.0
                            ? 'text-rose-400 bg-rose-950/30 border-rose-500/50 font-bold'
                            : (row.volume_breakout_ratio || 0) >= 2.0
                            ? 'text-purple-400 bg-purple-950/30 border-purple-500/30 font-semibold'
                            : (row.volume_breakout_ratio || 0) >= 1.5
                            ? 'text-indigo-400 bg-indigo-950/30 border-indigo-500/30 font-medium'
                            : 'text-slate-400 bg-slate-900/50 border-slate-800'
                        }`}>
                          {row.volume_breakout_ratio ? `${row.volume_breakout_ratio.toFixed(2)}x` : '1.00x'}
                        </span>
                      </td>
                      
                      {/* RSI */}
                      <td className="py-2 px-1.5 text-center">
                        <span className={`font-mono inline-block px-1 py-0.2 rounded text-xs border ${
                          (row.rsi_14 || 0) >= 70 
                            ? 'text-rose-400 bg-rose-950/20 border-rose-900/30 font-bold' 
                            : (row.rsi_14 || 0) <= 30 && row.rsi_14 !== null
                            ? 'text-emerald-400 bg-emerald-950/20 border-emerald-900/30 font-bold'
                            : 'text-slate-300 bg-slate-900/50 border-slate-800'
                        }`}>
                          {formatNumber(row.rsi_14, 1)}
                        </span>
                      </td>
                      
                      {/* SMA 20 */}
                      <td className="py-2 px-1.5 text-center font-mono">
                        {row.sma_20_cross_direction === 'ABOVE' ? (
                          <span className="text-indigo-400 font-bold" title="Above SMA 20">▲</span>
                        ) : row.sma_20_cross_direction === 'BELOW' ? (
                          <span className="text-amber-500 font-bold" title="Below SMA 20">▼</span>
                        ) : (
                          <span className="text-slate-600">—</span>
                        )}
                      </td>

                      {/* SMA 50 */}
                      <td className="py-2 px-1.5 text-center font-mono">
                        {row.sma_50_cross_direction === 'ABOVE' ? (
                          <span className="text-indigo-400 font-bold" title="Above SMA 50">▲</span>
                        ) : row.sma_50_cross_direction === 'BELOW' ? (
                          <span className="text-amber-500 font-bold" title="Below SMA 50">▼</span>
                        ) : (
                          <span className="text-slate-600">—</span>
                        )}
                      </td>

                      {/* SMA 200 */}
                      <td className="py-2 px-1.5 text-center font-mono">
                        {row.sma_200_cross_direction === 'ABOVE' ? (
                          <span className="text-indigo-400 font-bold" title="Above SMA 200">▲</span>
                        ) : row.sma_200_cross_direction === 'BELOW' ? (
                          <span className="text-amber-500 font-bold" title="Below SMA 200">▼</span>
                        ) : (
                          <span className="text-slate-600">—</span>
                        )}
                      </td>

                      {/* MACD Trend */}
                      <td className="py-2 px-1.5 text-center font-mono">
                        {row.macd_trend === 'BULLISH' ? (
                          <span className="text-emerald-400 font-bold animate-pulse" title="MACD Bullish">▲</span>
                        ) : row.macd_trend === 'BEARISH' ? (
                          <span className="text-rose-400 font-bold" title="MACD Bearish">▼</span>
                        ) : (
                          <span className="text-slate-600">—</span>
                        )}
                      </td>
                      
                      {/* HA */}
                      <td className="py-2 px-1.5 text-center font-mono">
                        {isHaBullish ? (
                          <span className="text-emerald-400 font-bold" title="HA Bullish (UP)">▲</span>
                        ) : row.ha_direction === 'DOWN' ? (
                          <span className="text-rose-400 font-bold" title="HA Bearish (DOWN)">▼</span>
                        ) : (
                          <span className="text-slate-600">—</span>
                        )}
                      </td>

                      {/* Renko */}
                      <td className="py-2 px-1.5 text-center font-mono">
                        {isRenkoBullish ? (
                          <span className="text-emerald-400 font-bold" title="Renko Bullish (UP)">▲</span>
                        ) : row.renko_direction === 'DOWN' ? (
                          <span className="text-rose-400 font-bold" title="Renko Bearish (DOWN)">▼</span>
                        ) : (
                          <span className="text-slate-600">—</span>
                        )}
                      </td>

                      {/* Three Line Break */}
                      <td className="py-2 px-1.5 text-center font-mono">
                        {isLbBullish ? (
                          <span className="text-emerald-400 font-bold" title="Three Line Break Bullish (UP)">▲</span>
                        ) : row.line_break_direction === 'DOWN' ? (
                          <span className="text-rose-400 font-bold" title="Three Line Break Bearish (DOWN)">▼</span>
                        ) : (
                          <span className="text-slate-600">—</span>
                        )}
                      </td>
                      
                      {/* RS Score */}
                      <td className="py-2 px-1.5 text-center">
                        {(row as any).rs_score_1m != null ? (
                          <span className={`font-mono text-xs px-1 py-0.2 rounded border ${
                            (row as any).rs_score_1m >= 1.2 ? 'text-emerald-400 bg-emerald-950/20 border-emerald-900/30'
                            : (row as any).rs_score_1m >= 0.8 ? 'text-slate-350 bg-slate-900/40 border-slate-800'
                            : 'text-rose-400 bg-rose-950/20 border-rose-900/30'
                          }`}>
                            {((row as any).rs_score_1m as number).toFixed(2)}x
                          </span>
                        ) : <span className="text-slate-600">—</span>}
                      </td>
                      {/* Patterns / Signals */}
                      <td className="py-2 px-1.5 text-center">
                        <div className="flex flex-wrap gap-1 justify-center items-center">
                          {row.is_nr7 && (
                            <span className="text-[10px] font-bold text-amber-400 bg-amber-950/25 border border-amber-900/30 px-1 py-0.5 rounded">
                              NR7
                            </span>
                          )}
                          {row.is_inside_bar && (
                            <span className="text-[10px] font-bold text-indigo-400 bg-indigo-950/25 border border-indigo-900/30 px-1 py-0.5 rounded">
                              Inside
                            </span>
                          )}
                          {row.is_gap_up && (
                            <span className="text-[10px] font-bold text-emerald-400 bg-emerald-950/25 border border-emerald-900/30 px-1 py-0.5 rounded">
                              Gap+
                            </span>
                          )}
                          {row.is_gap_down && (
                            <span className="text-[10px] font-bold text-rose-400 bg-rose-950/25 border border-rose-900/30 px-1 py-0.5 rounded">
                              Gap-
                            </span>
                          )}
                          {!row.is_nr7 && !row.is_inside_bar && !row.is_gap_up && !row.is_gap_down && (
                            <span className="text-slate-650">—</span>
                          )}
                        </div>
                      </td>
                      {/* Actions */}
                      <td className="py-2 px-1.5 text-right">
                        <div className="flex items-center gap-1 justify-end">
                          <button
                            onClick={() => handleAddToWatchlist(row.symbol)}
                            title="Add to Watchlist"
                            className="p-0.5 px-1 rounded bg-slate-900 border border-slate-800 hover:border-indigo-500/80 text-slate-500 hover:text-indigo-400 text-xs flex items-center transition cursor-pointer"
                          >
                            <Bookmark className="w-2.5 h-2.5" />
                          </button>
                          <button
                            onClick={() => handleSelectScreenerMatch(row.symbol)}
                            className="p-0.5 px-1.5 rounded bg-slate-900 border border-slate-800 hover:border-purple-500/80 text-slate-400 hover:text-white text-xs flex items-center gap-1 transition cursor-pointer"
                          >
                            <Eye className="w-3 h-3" />
                            Inspect
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
          {/* Pagination footer */}
          {filteredResults.length > PAGE_SIZE && (
            <div className="shrink-0 flex items-center justify-between px-4 py-2 border-t border-slate-800 bg-[#0c0f17] mt-2">
              <span className="text-xs text-slate-500">
                Showing <span className="text-slate-300 font-semibold">{Math.min(visibleCount, filteredResults.length).toLocaleString()}</span> of <span className="text-slate-300 font-semibold">{filteredResults.length.toLocaleString()}</span> results
              </span>
              <div className="flex gap-2">
                {visibleCount < filteredResults.length && (
                  <button
                    onClick={() => setVisibleCount(v => Math.min(v + PAGE_SIZE, filteredResults.length))}
                    className="px-2.5 py-1 text-xs font-bold bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 hover:text-white rounded transition cursor-pointer"
                  >
                    Load {Math.min(PAGE_SIZE, filteredResults.length - visibleCount)} More
                  </button>
                )}
                {visibleCount < filteredResults.length && (
                  <button
                    onClick={() => setVisibleCount(filteredResults.length)}
                    className="px-2.5 py-1 text-xs font-bold bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-400 hover:text-white rounded transition cursor-pointer"
                  >
                    Load All ({filteredResults.length.toLocaleString()})
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
