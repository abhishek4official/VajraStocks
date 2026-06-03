import React, { useEffect, useState, useMemo } from 'react';
import { useStockStore } from '../store/useStockStore';
import { Play, Eye, Filter, RefreshCw, BarChart2, Download, Bookmark } from 'lucide-react';
import type { ScreenerRow } from '../services/api';

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

  // Client-side sorting states
  const [sortField, setSortField] = useState<keyof ScreenerRow | null>(null);
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');

  useEffect(() => {
    // Run an initial sweep when the panel is first mounted
    runScreener();
  }, []);

  const handleRunScreener = () => {
    runScreener();
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

  // CSV Exporter
  const exportToCSV = () => {
    if (screenerResults.length === 0) return;

    const headers = [
      'Ticker', 'Company Name', 'Last EOD Price', 'Change %', 
      'Weekly Avg Vol', 'Vol Breakout', 'RSI (14)', 'SMA 20', 
      'SMA 50', 'SMA 200', 'MACD Trend', 'Heikin Ashi', 'Renko', 'Three Line Break'
    ];

    const rows = sortedResults.map(row => [
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
      row.line_break_direction ?? ''
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

      {/* Advanced Filter Inputs Card */}
      <div className="grid grid-cols-1 md:grid-cols-3 xl:grid-cols-11 gap-4 p-4 rounded-xl border border-slate-800/80 bg-[#121620]/30">
        
        {/* Weekly Avg Volume */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-semibold text-slate-400">Min Weekly Avg Vol</label>
          <input
            type="number"
            placeholder="No Limit"
            value={screenerFilters.min_weekly_avg_volume !== undefined ? screenerFilters.min_weekly_avg_volume : ''}
            onChange={(e) => setScreenerFilters({ 
              min_weekly_avg_volume: e.target.value === '' ? undefined : Number(e.target.value) 
            })}
            className="w-full px-3 py-1.5 text-sm rounded bg-slate-900 border border-slate-800 text-white focus:outline-none focus:border-purple-500 transition"
          />
        </div>

        {/* Volume Breakout Dropdown */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-semibold text-slate-400">Volume Breakout</label>
          <select
            value={screenerFilters.volume_breakout || 'ANY'}
            onChange={(e) => setScreenerFilters({ 
              volume_breakout: e.target.value === 'ANY' ? undefined : e.target.value as any 
            })}
            className="w-full px-3 py-1.5 text-sm rounded bg-slate-900 border border-slate-800 text-white focus:outline-none focus:border-purple-500 transition"
          >
            <option value="ANY">Any Volume</option>
            <option value="1.5X">1.5x Breakout</option>
            <option value="2.0X">2.0x Breakout</option>
            <option value="3.0X">3.0x Breakout</option>
          </select>
        </div>

        {/* RSI Range */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-semibold text-slate-400">Min RSI (14)</label>
          <input
            type="number"
            placeholder="No Limit"
            value={screenerFilters.min_rsi !== undefined ? screenerFilters.min_rsi : ''}
            onChange={(e) => setScreenerFilters({ 
              min_rsi: e.target.value === '' ? undefined : Number(e.target.value) 
            })}
            className="w-full px-3 py-1.5 text-sm rounded bg-slate-900 border border-slate-800 text-white focus:outline-none focus:border-purple-500 transition"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-semibold text-slate-400">Max RSI (14)</label>
          <input
            type="number"
            placeholder="No Limit"
            value={screenerFilters.max_rsi !== undefined ? screenerFilters.max_rsi : ''}
            onChange={(e) => setScreenerFilters({ 
              max_rsi: e.target.value === '' ? undefined : Number(e.target.value) 
            })}
            className="w-full px-3 py-1.5 text-sm rounded bg-slate-900 border border-slate-800 text-white focus:outline-none focus:border-purple-500 transition"
          />
        </div>

        {/* SMA 20 Cross */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-semibold text-slate-400">SMA 20 Cross</label>
          <select
            value={screenerFilters.sma_20_cross || 'ANY'}
            onChange={(e) => setScreenerFilters({ 
              sma_20_cross: e.target.value === 'ANY' ? undefined : e.target.value as any 
            })}
            className="w-full px-3 py-1.5 text-sm rounded bg-slate-900 border border-slate-800 text-white focus:outline-none focus:border-purple-500 transition"
          >
            <option value="ANY">Any Position</option>
            <option value="ABOVE">Above SMA 20</option>
            <option value="BELOW">Below SMA 20</option>
          </select>
        </div>

        {/* SMA 50 Cross */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-semibold text-slate-400">SMA 50 Cross</label>
          <select
            value={screenerFilters.sma_50_cross || 'ANY'}
            onChange={(e) => setScreenerFilters({ 
              sma_50_cross: e.target.value === 'ANY' ? undefined : e.target.value as any 
            })}
            className="w-full px-3 py-1.5 text-sm rounded bg-slate-900 border border-slate-800 text-white focus:outline-none focus:border-purple-500 transition"
          >
            <option value="ANY">Any Position</option>
            <option value="ABOVE">Above SMA 50</option>
            <option value="BELOW">Below SMA 50</option>
          </select>
        </div>

        {/* SMA 200 Cross */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-semibold text-slate-400">SMA 200 Cross</label>
          <select
            value={screenerFilters.sma_200_cross || 'ANY'}
            onChange={(e) => setScreenerFilters({ 
              sma_200_cross: e.target.value === 'ANY' ? undefined : e.target.value as any 
            })}
            className="w-full px-3 py-1.5 text-sm rounded bg-slate-900 border border-slate-800 text-white focus:outline-none focus:border-purple-500 transition"
          >
            <option value="ANY">Any Position</option>
            <option value="ABOVE">Above SMA 200</option>
            <option value="BELOW">Below SMA 200</option>
          </select>
        </div>

        {/* MACD Trend */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-semibold text-slate-400">MACD Trend</label>
          <select
            value={screenerFilters.macd_trend || 'ANY'}
            onChange={(e) => setScreenerFilters({ 
              macd_trend: e.target.value === 'ANY' ? undefined : e.target.value as any 
            })}
            className="w-full px-3 py-1.5 text-sm rounded bg-slate-900 border border-slate-800 text-white focus:outline-none focus:border-purple-500 transition"
          >
            <option value="ANY">Any Trend</option>
            <option value="BULLISH">Bullish (MACD &gt; Sig)</option>
            <option value="BEARISH">Bearish (MACD &lt; Sig)</option>
          </select>
        </div>

        {/* Heikin-Ashi Direction */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-semibold text-slate-400">Heikin Ashi Trend</label>
          <select
            value={screenerFilters.ha_dir || 'ANY'}
            onChange={(e) => setScreenerFilters({ 
              ha_dir: e.target.value === 'ANY' ? undefined : e.target.value as any 
            })}
            className="w-full px-3 py-1.5 text-sm rounded bg-slate-900 border border-slate-800 text-white focus:outline-none focus:border-purple-500 transition"
          >
            <option value="ANY">Any Trend</option>
            <option value="UP">Bullish (UP)</option>
            <option value="DOWN">Bearish (DOWN)</option>
          </select>
        </div>

        {/* Renko Direction */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-semibold text-slate-400">Renko Brick</label>
          <select
            value={screenerFilters.renko_dir || 'ANY'}
            onChange={(e) => setScreenerFilters({ 
              renko_dir: e.target.value === 'ANY' ? undefined : e.target.value as any 
            })}
            className="w-full px-3 py-1.5 text-sm rounded bg-slate-900 border border-slate-800 text-white focus:outline-none focus:border-purple-500 transition"
          >
            <option value="ANY">Any Direction</option>
            <option value="UP">Bullish (UP)</option>
            <option value="DOWN">Bearish (DOWN)</option>
          </select>
        </div>

        {/* Line Break Direction */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-semibold text-slate-400">Three Line Break</label>
          <select
            value={screenerFilters.lb_dir || 'ANY'}
            onChange={(e) => setScreenerFilters({ 
              lb_dir: e.target.value === 'ANY' ? undefined : e.target.value as any 
            })}
            className="w-full px-3 py-1.5 text-sm rounded bg-slate-900 border border-slate-800 text-white focus:outline-none focus:border-purple-500 transition"
          >
            <option value="ANY">Any Direction</option>
            <option value="UP">Bullish (UP)</option>
            <option value="DOWN">Bearish (DOWN)</option>
          </select>
        </div>
      </div>

      {/* Results Grid Table */}
      <div className="flex-1 bg-[#121620]/60 rounded-xl border border-slate-800/80 p-4 overflow-hidden flex flex-col min-h-[300px]">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-3 shrink-0">
          <h3 className="text-sm font-bold text-white tracking-wide flex items-center gap-1.5">
            <BarChart2 className="w-4 h-4 text-purple-400" />
            Matching Stocks
            <span className="font-mono text-xs text-slate-400 font-normal">
              ({sortedResults.length.toLocaleString()} result{sortedResults.length !== 1 ? 's' : ''})
            </span>
          </h3>
          {isLoading && <RefreshCw className="w-4 h-4 text-purple-400 animate-spin" />}
        </div>

        <div className="flex-1 overflow-auto">
          <table className="w-full border-collapse text-left text-sm text-slate-300">
            <thead>
              <tr className="border-b border-slate-800 text-xs text-slate-400 uppercase tracking-wider font-mono select-none">
                <th className="py-2.5 px-3 cursor-pointer hover:text-white transition" onClick={() => handleSort('symbol')}>
                  Ticker {renderSortIcon('symbol')}
                </th>
                <th className="py-2.5 px-3 cursor-pointer hover:text-white transition" onClick={() => handleSort('company_name')}>
                  Company Name {renderSortIcon('company_name')}
                </th>
                <th className="py-2.5 px-3 cursor-pointer hover:text-white transition" onClick={() => handleSort('close_price')}>
                  Last EOD Price {renderSortIcon('close_price')}
                </th>
                <th className="py-2.5 px-3 cursor-pointer hover:text-white transition" onClick={() => handleSort('price_pct_change')}>
                  Change % {renderSortIcon('price_pct_change')}
                </th>
                <th className="py-2.5 px-3 cursor-pointer hover:text-white transition" onClick={() => handleSort('weekly_avg_volume')}>
                  Weekly Avg Vol {renderSortIcon('weekly_avg_volume')}
                </th>
                <th className="py-2.5 px-3 text-center cursor-pointer hover:text-white transition" onClick={() => handleSort('volume_breakout_ratio')}>
                  Vol Breakout {renderSortIcon('volume_breakout_ratio')}
                </th>
                <th className="py-2.5 px-3 text-center cursor-pointer hover:text-white transition" onClick={() => handleSort('rsi_14')}>
                  RSI (14) {renderSortIcon('rsi_14')}
                </th>
                <th className="py-2.5 px-3 text-center cursor-pointer hover:text-white transition" onClick={() => handleSort('sma_20_cross_direction')}>
                  SMA 20 {renderSortIcon('sma_20_cross_direction')}
                </th>
                <th className="py-2.5 px-3 text-center cursor-pointer hover:text-white transition" onClick={() => handleSort('sma_50_cross_direction')}>
                  SMA 50 {renderSortIcon('sma_50_cross_direction')}
                </th>
                <th className="py-2.5 px-3 text-center cursor-pointer hover:text-white transition" onClick={() => handleSort('sma_200_cross_direction')}>
                  SMA 200 {renderSortIcon('sma_200_cross_direction')}
                </th>
                <th className="py-2.5 px-3 text-center cursor-pointer hover:text-white transition" onClick={() => handleSort('macd_trend')}>
                  MACD Trend {renderSortIcon('macd_trend')}
                </th>
                <th className="py-2.5 px-3 text-center cursor-pointer hover:text-white transition" onClick={() => handleSort('ha_direction')}>
                  Heikin Ashi {renderSortIcon('ha_direction')}
                </th>
                <th className="py-2.5 px-3 text-center cursor-pointer hover:text-white transition" onClick={() => handleSort('renko_direction')}>
                  Renko {renderSortIcon('renko_direction')}
                </th>
                <th className="py-2.5 px-3 text-center cursor-pointer hover:text-white transition" onClick={() => handleSort('line_break_direction')}>
                  Three Line Break {renderSortIcon('line_break_direction')}
                </th>
                <th className="py-2.5 px-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-850">
              {sortedResults.length === 0 ? (
                <tr>
                  <td colSpan={15} className="py-12 text-center text-slate-500 text-sm">
                    {isLoading 
                      ? 'Executing database snapshot sweep...' 
                      : 'No stock matches found for the current filter criteria.'}
                  </td>
                </tr>
              ) : (
                sortedResults.map((row) => {
                  const isChangeBullish = (row.price_pct_change || 0) >= 0;
                  const isHaBullish = row.ha_direction === 'UP';
                  const isRenkoBullish = row.renko_direction === 'UP';
                  const isLbBullish = row.line_break_direction === 'UP';
                  
                  return (
                    <tr key={row.symbol_id} className="hover:bg-slate-900/40 transition">
                      {/* Ticker */}
                      <td className="py-3 px-3 font-bold text-white tracking-wide font-mono">
                        {row.symbol.replace('.NS', '')}
                      </td>
                      
                      {/* Company Name */}
                      <td className="py-3 px-3 text-slate-400 truncate max-w-[150px]" title={row.company_name}>
                        {row.company_name}
                      </td>
                      
                      {/* Price */}
                      <td className="py-3 px-3 font-mono font-semibold">
                        ₹{formatNumber(row.close_price)}
                      </td>
                      
                      {/* Change */}
                      <td className={`py-3 px-3 font-mono ${isChangeBullish ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {isChangeBullish ? '+' : ''}{formatNumber(row.price_pct_change)}%
                      </td>

                      {/* Weekly Avg Vol */}
                      <td className="py-3 px-3 font-mono text-slate-300">
                        {formatVolume(row.weekly_avg_volume)}
                      </td>
                      
                      {/* Volume Breakout Badge */}
                      <td className="py-3 px-3 text-center">
                        <span className={`font-mono text-xs px-2 py-0.5 rounded border inline-block ${
                          (row.volume_breakout_ratio || 0) >= 3.0
                            ? 'text-rose-400 bg-rose-950/30 border-rose-500/50 shadow-[0_0_8px_rgba(244,63,94,0.15)] font-bold animate-pulse'
                            : (row.volume_breakout_ratio || 0) >= 2.0
                            ? 'text-purple-400 bg-purple-950/30 border-purple-500/30 shadow-[0_0_8px_rgba(168,85,247,0.15)] font-semibold'
                            : (row.volume_breakout_ratio || 0) >= 1.5
                            ? 'text-indigo-400 bg-indigo-950/30 border-indigo-500/30 font-medium'
                            : 'text-slate-400 bg-slate-900/50 border-slate-800'
                        }`}>
                          {row.volume_breakout_ratio ? `${row.volume_breakout_ratio.toFixed(2)}x` : '1.00x'}
                        </span>
                      </td>
                      
                      {/* RSI */}
                      <td className="py-3 px-3 text-center">
                        <span className={`font-mono inline-block px-2 py-0.5 rounded text-xs border ${
                          (row.rsi_14 || 0) >= 70 
                            ? 'text-rose-400 bg-rose-950/20 border-rose-900/30 font-bold' 
                            : (row.rsi_14 || 0) <= 30 && row.rsi_14 !== null
                            ? 'text-emerald-400 bg-emerald-950/20 border-emerald-900/30 font-bold'
                            : 'text-slate-300 bg-slate-900/50 border-slate-800'
                        }`}>
                          {formatNumber(row.rsi_14)}
                        </span>
                      </td>
                      
                      {/* SMA 20 */}
                      <td className="py-3 px-3 text-center">
                        <span className={`text-xs px-2 py-0.5 rounded border ${
                          row.sma_20_cross_direction === 'ABOVE'
                            ? 'text-indigo-400 bg-indigo-950/20 border-indigo-900/30'
                            : 'text-amber-400 bg-amber-950/20 border-amber-900/30'
                        }`}>
                          {row.sma_20_cross_direction || 'UNKNOWN'}
                        </span>
                      </td>

                      {/* SMA 50 */}
                      <td className="py-3 px-3 text-center">
                        <span className={`text-xs px-2 py-0.5 rounded border ${
                          row.sma_50_cross_direction === 'ABOVE'
                            ? 'text-indigo-400 bg-indigo-950/20 border-indigo-900/30'
                            : 'text-amber-400 bg-amber-950/20 border-amber-900/30'
                        }`}>
                          {row.sma_50_cross_direction || 'UNKNOWN'}
                        </span>
                      </td>

                      {/* SMA 200 */}
                      <td className="py-3 px-3 text-center">
                        <span className={`text-xs px-2 py-0.5 rounded border ${
                          row.sma_200_cross_direction === 'ABOVE'
                            ? 'text-indigo-400 bg-indigo-950/20 border-indigo-900/30'
                            : 'text-amber-400 bg-amber-950/20 border-amber-900/30'
                        }`}>
                          {row.sma_200_cross_direction || 'UNKNOWN'}
                        </span>
                      </td>

                      {/* MACD Trend */}
                      <td className="py-3 px-3 text-center">
                        <span className={`text-xs px-2 py-0.5 rounded border ${
                          row.macd_trend === 'BULLISH'
                            ? 'text-emerald-400 bg-emerald-950/20 border-emerald-900/30'
                            : 'text-rose-400 bg-rose-950/20 border-rose-900/30'
                        }`}>
                          {row.macd_trend || 'UNKNOWN'}
                        </span>
                      </td>
                      
                      {/* HA */}
                      <td className="py-3 px-3 text-center">
                        <span className={`text-xs px-2 py-0.5 rounded ${
                          isHaBullish ? 'text-emerald-400 bg-emerald-950/25' : 'text-rose-400 bg-rose-950/25'
                        }`}>
                          {row.ha_direction || 'NONE'}
                        </span>
                      </td>

                      {/* Renko */}
                      <td className="py-3 px-3 text-center">
                        <span className={`text-xs px-2 py-0.5 rounded ${
                          isRenkoBullish ? 'text-emerald-400 bg-emerald-950/25' : 'text-rose-400 bg-rose-950/25'
                        }`}>
                          {row.renko_direction || 'NONE'}
                        </span>
                      </td>

                      {/* Three Line Break */}
                      <td className="py-3 px-3 text-center">
                        <span className={`text-xs px-2 py-0.5 rounded ${
                          isLbBullish ? 'text-emerald-400 bg-emerald-950/25' : 'text-rose-400 bg-rose-950/25'
                        }`}>
                          {row.line_break_direction || 'NONE'}
                        </span>
                      </td>
                      
                      {/* Actions */}
                      <td className="py-3 px-3 text-right">
                        <div className="flex items-center gap-1.5 justify-end">
                          <button
                            onClick={() => handleAddToWatchlist(row.symbol)}
                            title="Add to Watchlist"
                            className="p-1 px-2 rounded bg-slate-900 border border-slate-800 hover:border-indigo-500/80 text-slate-500 hover:text-indigo-400 text-xs flex items-center gap-1 transition cursor-pointer"
                          >
                            <Bookmark className="w-3 h-3" />
                          </button>
                          <button
                            onClick={() => handleSelectScreenerMatch(row.symbol)}
                            className="p-1 px-2.5 rounded bg-slate-900 border border-slate-800 hover:border-purple-500/80 text-slate-400 hover:text-white text-xs flex items-center gap-1.5 transition cursor-pointer"
                          >
                            <Eye className="w-3.5 h-3.5" />
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
        </div>
      </div>
    </div>
  );
};
