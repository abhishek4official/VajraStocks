import React, { useState, useMemo, useEffect } from 'react';
import { Filter, RefreshCw, BarChart2, Download } from 'lucide-react';
import { useStockStore } from '../../store/useStockStore';
import type { ScreenerRow, StrategyMeta } from '../../services/api';
import {
  COL_FILTERS_KEY,
  SHOW_COL_FILTERS_KEY,
  DEFAULT_COL_FILTERS,
} from './constants';
import type { ColFilters } from './constants';
import { matchTextFilter, matchNumericFilter, loadColFilters, MultiSelectFilter } from './filterUtils';
import { ScreenerRow as ScreenerResultRow } from './ScreenerRow';

interface Props {
  strategies: StrategyMeta[];
  onAddToWatchlist: (symbol: string) => void;
  onOpenChart: (symbol: string) => void;
}

const PAGE_SIZE = 50;

export const ScreenerResultGrid: React.FC<Props> = ({ strategies, onAddToWatchlist, onOpenChart }) => {
  const { screenerResults, isLoading, qualifyQueue, addToQualifyQueue } = useStockStore();

  const [sortField, setSortField] = useState<keyof ScreenerRow | null>(null);
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const [searchQuery, setSearchQuery] = useState('');

  const [showColFilters, setShowColFilters] = useState(() => {
    try { return localStorage.getItem(SHOW_COL_FILTERS_KEY) !== 'false'; } catch { return true; }
  });
  const [colFilters, setColFilters] = useState<ColFilters>(loadColFilters);

  // Persist the in-table filters + toggle whenever they change.
  useEffect(() => {
    try { localStorage.setItem(COL_FILTERS_KEY, JSON.stringify(colFilters)); } catch { /* ignore */ }
  }, [colFilters]);
  useEffect(() => {
    try { localStorage.setItem(SHOW_COL_FILTERS_KEY, String(showColFilters)); } catch { /* ignore */ }
  }, [showColFilters]);

  const isAnyColFilterActive = useMemo(() => {
    return Object.values(colFilters).some(val => val !== '');
  }, [colFilters]);

  const handleClearColFilters = () => {
    setColFilters({ ...DEFAULT_COL_FILTERS });
  };

  // Reset to first page whenever results, search query, or column filters update
  useEffect(() => { setVisibleCount(PAGE_SIZE); }, [screenerResults, searchQuery, colFilters]);

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

  // Filtered Results Memo (applies client-side search query and column filters)
  const filteredResults = useMemo(() => {
    let results = sortedResults;

    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase().trim();
      results = results.filter(
        row => row.symbol.toLowerCase().includes(query) ||
               row.company_name.toLowerCase().includes(query)
      );
    }

    if (isAnyColFilterActive) {
      results = results.filter((row) => {
        if (!matchTextFilter(row.symbol, colFilters.symbol)) return false;
        if (!matchTextFilter(row.company_name, colFilters.company_name)) return false;
        if (!matchNumericFilter(row.close_price, colFilters.close_price)) return false;
        if (!matchNumericFilter(row.price_pct_change, colFilters.price_pct_change)) return false;
        if (colFilters.regime_bias) {
          const selected = colFilters.regime_bias.split(',').filter(Boolean);
          if (selected.length > 0 && !selected.includes((row as any).regime_bias)) return false;
        }
        if (!matchNumericFilter(row.ret_1w, colFilters.ret_1w)) return false;
        if (!matchNumericFilter(row.ret_2w, colFilters.ret_2w)) return false;
        if (!matchNumericFilter(row.ret_3w, colFilters.ret_3w)) return false;
        if (!matchNumericFilter(row.ret_4w, colFilters.ret_4w)) return false;
        if (!matchNumericFilter(row.stop_loss, colFilters.stop_loss)) return false;
        if (!matchNumericFilter(row.target_1, colFilters.target_1)) return false;
        if (!matchNumericFilter(row.target_2, colFilters.target_2)) return false;
        if (!matchNumericFilter(row.target_3, colFilters.target_3)) return false;
        if (!matchNumericFilter(row.potential_gain_pct, colFilters.potential_gain_pct)) return false;
        if (!matchNumericFilter(row.rr_ratio, colFilters.rr_ratio)) return false;
        if (!matchNumericFilter(row.tqs, colFilters.tqs)) return false;
        if (!matchNumericFilter(row.weinstein_stage, colFilters.weinstein_stage)) return false;
        if (!matchNumericFilter(row.position_size_shares, colFilters.position_size_shares)) return false;
        if (!matchNumericFilter(row.avg_traded_value, colFilters.avg_traded_value)) return false;
        if (!matchNumericFilter(row.volume_breakout_ratio, colFilters.volume_breakout_ratio)) return false;
        if (!matchNumericFilter(row.rsi_14, colFilters.rsi_14)) return false;
        if (!matchNumericFilter(row.cmf_20, colFilters.cmf_20)) return false;
        if (!matchNumericFilter(row.stochrsi_k, colFilters.stochrsi_k)) return false;
        if (!matchNumericFilter(row.stochrsi_d, colFilters.stochrsi_d)) return false;
        if (colFilters.sma_20_cross_direction) {
          const selected = colFilters.sma_20_cross_direction.split(',').filter(Boolean);
          if (selected.length > 0 && !selected.includes(row.sma_20_cross_direction || '')) return false;
        }
        if (colFilters.sma_50_cross_direction) {
          const selected = colFilters.sma_50_cross_direction.split(',').filter(Boolean);
          if (selected.length > 0 && !selected.includes(row.sma_50_cross_direction || '')) return false;
        }
        if (colFilters.sma_200_cross_direction) {
          const selected = colFilters.sma_200_cross_direction.split(',').filter(Boolean);
          if (selected.length > 0 && !selected.includes(row.sma_200_cross_direction || '')) return false;
        }
        if (colFilters.macd_trend) {
          const selected = colFilters.macd_trend.split(',').filter(Boolean);
          if (selected.length > 0 && !selected.includes(row.macd_trend || '')) return false;
        }
        if (colFilters.ha_direction) {
          const selected = colFilters.ha_direction.split(',').filter(Boolean);
          if (selected.length > 0 && !selected.includes(row.ha_direction || '')) return false;
        }
        if (colFilters.renko_direction) {
          const selected = colFilters.renko_direction.split(',').filter(Boolean);
          if (selected.length > 0 && !selected.includes(row.renko_direction || '')) return false;
        }
        if (colFilters.line_break_direction) {
          const selected = colFilters.line_break_direction.split(',').filter(Boolean);
          if (selected.length > 0 && !selected.includes(row.line_break_direction || '')) return false;
        }
        if (!matchNumericFilter((row as any).rs_score_1m, colFilters.rs_score_1m)) return false;

        if (colFilters.patterns) {
          const selected = colFilters.patterns.split(',').filter(Boolean);
          if (selected.length > 0) {
            let matched = false;
            if (selected.includes('NR7') && row.is_nr7) matched = true;
            if (selected.includes('Inside') && row.is_inside_bar) matched = true;
            if (selected.includes('Gap+') && row.is_gap_up) matched = true;
            if (selected.includes('Gap-') && row.is_gap_down) matched = true;
            if (!matched) return false;
          }
        }

        if (!matchNumericFilter(row.days_since_ema9_ema20_bull, colFilters.days_since_ema9_ema20_bull)) return false;
        if (!matchNumericFilter(row.days_since_sma20_sma50_bull, colFilters.days_since_sma20_sma50_bull)) return false;
        if (!matchNumericFilter(row.days_since_macd_bull, colFilters.days_since_macd_bull)) return false;
        if (!matchNumericFilter(row.days_since_cmf_bull, colFilters.days_since_cmf_bull)) return false;
        // New indicator column filters
        if (!matchNumericFilter(row.hilega_milega_signal, colFilters.hilega_milega_signal)) return false;
        if (!matchNumericFilter(row.rsi_divergence, colFilters.rsi_divergence)) return false;
        if (!matchNumericFilter(row.macd_divergence, colFilters.macd_divergence)) return false;
        if (colFilters.price_vs_zlema21 && row.price_vs_zlema21 !== colFilters.price_vs_zlema21) return false;
        if (colFilters.candle_type === 'BORING' && !row.is_boring_candle) return false;
        if (colFilters.candle_type === 'EXPLOSIVE' && !row.is_explosive_candle) return false;
        if (colFilters.cpr_daily_narrow === 'NARROW' && !row.cpr_daily_narrow) return false;  // cpr_daily_narrow is boolean
        if (colFilters.cpr_weekly_narrow === 'NARROW') {
          const wPivot = row.cpr_weekly_pivot, wTc = row.cpr_weekly_tc, wBc = row.cpr_weekly_bc;
          const isWeeklyNarrow = wPivot != null && wTc != null && wBc != null && Math.abs(wTc - wBc) / wPivot * 100 < 0.5;
          if (!isWeeklyNarrow) return false;
        }
        if (!matchNumericFilter(row.psy_20, colFilters.psy_20)) return false;
        if (colFilters.price_vs_avwap && row.price_vs_avwap !== colFilters.price_vs_avwap) return false;
        // Fundamentals (ratio fields converted to % for intuitive ">15" style filtering)
        if (!matchNumericFilter(row.market_cap, colFilters.market_cap)) return false;
        if (!matchNumericFilter(row.pe_ratio, colFilters.pe_ratio)) return false;
        if (!matchNumericFilter(row.pb_ratio, colFilters.pb_ratio)) return false;
        if (!matchNumericFilter(row.ev_ebitda, colFilters.ev_ebitda)) return false;
        if (!matchNumericFilter(row.roe != null ? row.roe * 100 : undefined, colFilters.roe)) return false;
        if (!matchNumericFilter(row.debt_to_equity, colFilters.debt_to_equity)) return false;
        if (!matchNumericFilter(row.profit_margin != null ? row.profit_margin * 100 : undefined, colFilters.profit_margin)) return false;
        if (!matchNumericFilter(row.eps_ttm, colFilters.eps_ttm)) return false;
        if (!matchTextFilter(row.sector, colFilters.sector)) return false;

        return true;
      });
    }

    return results;
  }, [sortedResults, searchQuery, colFilters, isAnyColFilterActive]);

  // CSV Exporter
  const exportToCSV = () => {
    if (filteredResults.length === 0) return;

    const headers = [
      'Ticker', 'Company Name', 'Last EOD Price', 'Change %',
      'Avg Val', 'Bias', '1W Return %', '2W Return %', '3W Return %', '4W Return %',
      'Stop Loss', 'Target 1', 'Target 2', 'Target 3', 'Upside %', 'R:R', 'TQS', 'Weinstein Stage', 'Suggested Shares',
      'Vol Breakout Ratio', 'RSI (14)', 'CMF (20)', 'StochRSI K', 'StochRSI D',
      'SMA 20 Position', 'SMA 50 Position', 'SMA 200 Position', 'MACD Trend',
      'Heikin Ashi', 'Renko', 'Three Line Break', 'RS 1M', 'Patterns',
      'ML Signal', 'ML EV Score', 'ML Rank',
      'Days since EMA9/20 Bull', 'Days since SMA20/50 Bull', 'Days since MACD Bull', 'Days since CMF Bull',
      'HM Signal', 'RSI Div', 'MACD Div', 'ZLEMA Pos', 'Boring Candle', 'Explosive Candle',
      'CPR Daily Pivot', 'CPR Daily TC', 'CPR Daily BC', 'CPR Daily Narrow',
      'CPR Weekly Pivot', 'CPR Weekly TC', 'CPR Weekly BC', 'PSY-20', 'AVWAP', 'AVWAP Pos',
      'Mkt Cap', 'P/E', 'P/B', 'EV/EBITDA', 'ROE %', 'D/E', 'Net Margin %', 'EPS TTM', 'Sector'
    ];

    const rows = filteredResults.map(row => {
      const patterns = [
        row.is_nr7 && 'NR7',
        row.is_inside_bar && 'Inside',
        row.is_gap_up && 'GapUp',
        row.is_gap_down && 'GapDown'
      ].filter(Boolean).join('; ');

      return [
        row.symbol.replace('.NS', ''),
        `"${row.company_name.replace(/"/g, '""')}"`,
        row.close_price,
        row.price_pct_change ?? '',
        row.avg_traded_value ?? '',
        (row as any).regime_bias ?? '',
        row.ret_1w ?? '',
        row.ret_2w ?? '',
        row.ret_3w ?? '',
        row.ret_4w ?? '',
        row.stop_loss ?? '',
        row.target_1 ?? '',
        row.target_2 ?? '',
        row.target_3 ?? '',
        row.potential_gain_pct ?? '',
        row.rr_ratio ?? '',
        row.tqs ?? '',
        row.weinstein_stage ?? '',
        row.position_size_shares ?? '',
        row.volume_breakout_ratio ?? '',
        row.rsi_14 ?? '',
        row.cmf_20 ?? '',
        row.stochrsi_k ?? '',
        row.stochrsi_d ?? '',
        row.sma_20_cross_direction ?? '',
        row.sma_50_cross_direction ?? '',
        row.sma_200_cross_direction ?? '',
        row.macd_trend ?? '',
        row.ha_direction ?? '',
        row.renko_direction ?? '',
        row.line_break_direction ?? '',
        (row as any).rs_score_1m ?? '',
        patterns,
        row.days_since_ema9_ema20_bull ?? '',
        row.days_since_sma20_sma50_bull ?? '',
        row.days_since_macd_bull ?? '',
        row.days_since_cmf_bull ?? '',
        row.hilega_milega_signal ?? '',
        row.rsi_divergence ?? '',
        row.macd_divergence ?? '',
        row.price_vs_zlema21 ?? '',
        row.is_boring_candle != null ? (row.is_boring_candle ? 'Y' : '') : '',
        row.is_explosive_candle != null ? (row.is_explosive_candle ? 'Y' : '') : '',
        row.cpr_daily_pivot ?? '',
        row.cpr_daily_tc ?? '',
        row.cpr_daily_bc ?? '',
        row.cpr_daily_narrow != null ? (row.cpr_daily_narrow ? 'Y' : '') : '',
        row.cpr_weekly_pivot ?? '',
        row.cpr_weekly_tc ?? '',
        row.cpr_weekly_bc ?? '',
        row.psy_20 != null ? row.psy_20.toFixed(1) : '',
        row.avwap ?? '',
        row.price_vs_avwap ?? '',
        row.market_cap ?? '',
        row.pe_ratio ?? '',
        row.pb_ratio ?? '',
        row.ev_ebitda ?? '',
        row.roe != null ? (row.roe * 100).toFixed(2) : '',
        row.debt_to_equity ?? '',
        row.profit_margin != null ? (row.profit_margin * 100).toFixed(2) : '',
        row.eps_ttm ?? '',
        row.sector ? `"${row.sector.replace(/"/g, '""')}"` : ''
      ];
    });

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
    <div className="flex-1 bg-bg-surface/60 rounded-xl border border-border-subtle p-4 overflow-hidden flex flex-col min-h-[300px]">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-800 mb-3 shrink-0">
        <h3 className="text-sm font-bold text-white tracking-wide flex items-center gap-1.5">
          <BarChart2 className="w-4 h-4 text-purple-400" />
          Matching Stocks
          <span className="font-mono text-xs text-slate-400 font-normal">
            ({filteredResults.length.toLocaleString()} result{filteredResults.length !== 1 ? 's' : ''})
          </span>
        </h3>
        <div className="flex items-center gap-3">
          {isAnyColFilterActive && (
            <button
              onClick={handleClearColFilters}
              className="text-[10px] text-purple-400 hover:text-purple-355 font-bold border border-purple-500/30 px-2.5 py-1 rounded-lg bg-purple-950/20 transition cursor-pointer"
            >
              Clear Column Filters
            </button>
          )}
          <button
            onClick={() => setShowColFilters(!showColFilters)}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold border transition cursor-pointer ${
              showColFilters
                ? 'bg-purple-950/40 border-purple-500/50 text-purple-200'
                : 'bg-slate-800 border-slate-700 text-slate-350 hover:text-text-main hover:bg-slate-700'
            }`}
            title="Toggle inline column filters"
          >
            <Filter className="w-3.5 h-3.5" />
            {showColFilters ? 'Hide Column Filters' : 'Column Filters'}
          </button>
          <button
            onClick={exportToCSV}
            disabled={filteredResults.length === 0}
            className="flex items-center gap-2 px-4 py-2 bg-bg-surface/80 hover:bg-bg-surface disabled:opacity-40 disabled:cursor-not-allowed text-text-muted hover:text-text-main border border-border-subtle rounded-lg text-sm font-bold transition cursor-pointer"
            title="Export filtered results to CSV file"
          >
            <Download className="w-4 h-4" />
            Export CSV
          </button>
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

      <div className="flex-1 overflow-auto flex flex-col relative">
        <style>{`
          .screener-grid {
            table-layout: fixed;
          }
          .screener-grid th, .screener-grid td {
            border-right: 1px solid rgba(51, 65, 85, 0.25);
            padding: 8px 10px;
            font-size: 12px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }
          .screener-grid th:last-child, .screener-grid td:last-child {
            border-right: none;
          }

          /* Pinned Columns: col 1 = Actions, col 2 = Ticker, col 3 = Company */
          .screener-grid th:nth-child(1),
          .screener-grid td:nth-child(1) {
            position: sticky;
            left: 0;
            z-index: 5;
            width: 160px;
            min-width: 160px;
            max-width: 160px;
            overflow: visible;
            border-right: 2px solid rgba(139, 92, 246, 0.4);
            box-shadow: 4px 0 8px -3px rgba(0, 0, 0, 0.6);
          }
          .screener-grid th:nth-child(2),
          .screener-grid td:nth-child(2) {
            position: sticky;
            left: 160px;
            z-index: 5;
            width: 90px;
            min-width: 90px;
            max-width: 90px;
            border-right: 1px solid rgba(51, 65, 85, 0.4);
          }
          .screener-grid th:nth-child(3),
          .screener-grid td:nth-child(3) {
            position: sticky;
            left: 250px;
            z-index: 5;
            width: 140px;
            min-width: 140px;
            max-width: 140px;
            border-right: 2px solid rgba(139, 92, 246, 0.4);
            box-shadow: 4px 0 8px -3px rgba(0, 0, 0, 0.6);
          }

          /* Sticky Headers & Filters */
          .screener-grid thead th {
            position: sticky;
            top: 0;
            background-color: var(--bg-surface);
            z-index: 10;
            border-bottom: 1px solid var(--border-subtle);
          }
          .screener-grid thead tr:nth-child(2) td {
            position: sticky;
            top: 32px; /* height of header row */
            background-color: var(--bg-surface);
            z-index: 10;
            border-bottom: 2px solid var(--border-subtle);
          }

          /* Sticky overrides for headers of pinned columns */
          .screener-grid thead th:nth-child(1) { z-index: 25; background-color: var(--bg-surface) !important; }
          .screener-grid thead th:nth-child(2) { z-index: 25; background-color: var(--bg-surface) !important; }
          .screener-grid thead th:nth-child(3) { z-index: 25; background-color: var(--bg-surface) !important; }
          .screener-grid thead tr:nth-child(2) td:nth-child(1) { z-index: 25; background-color: var(--bg-surface) !important; }
          .screener-grid thead tr:nth-child(2) td:nth-child(2) { z-index: 25; background-color: var(--bg-surface) !important; }
          .screener-grid thead tr:nth-child(2) td:nth-child(3) { z-index: 25; background-color: var(--bg-surface) !important; }

          /* Zebra striping backgrounds for scrollable cells */
          .screener-grid tbody tr:nth-child(odd) td {
            background-color: var(--bg-base);
          }
          .screener-grid tbody tr:nth-child(even) td {
            background-color: var(--bg-surface);
          }

          /* Pinned cell backgrounds (Actions + Ticker + Company) */
          .screener-grid tbody tr:nth-child(odd) td:nth-child(1),
          .screener-grid tbody tr:nth-child(odd) td:nth-child(2),
          .screener-grid tbody tr:nth-child(odd) td:nth-child(3) {
            background-color: var(--bg-base) !important;
          }
          .screener-grid tbody tr:nth-child(even) td:nth-child(1),
          .screener-grid tbody tr:nth-child(even) td:nth-child(2),
          .screener-grid tbody tr:nth-child(even) td:nth-child(3) {
            background-color: var(--bg-surface) !important;
          }

          /* Row hovers */
          .screener-grid tbody tr:hover td {
            background-color: rgba(139, 92, 246, 0.15) !important;
          }

          /* Column widths for data cells (Actions=1, Ticker=2, Company=3, data starts at 4) */
          .screener-grid th:nth-child(4), .screener-grid td:nth-child(4) { width: 100px; min-width: 100px; } /* Price */
          .screener-grid th:nth-child(5), .screener-grid td:nth-child(5) { width: 85px; min-width: 85px; } /* Chg% */
          .screener-grid th:nth-child(6), .screener-grid td:nth-child(6) { width: 105px; min-width: 105px; } /* Avg Vol */
          .screener-grid th:nth-child(7), .screener-grid td:nth-child(7) { width: 95px; min-width: 95px; } /* Bias */
          .screener-grid th:nth-child(8), .screener-grid td:nth-child(8),
          .screener-grid th:nth-child(9), .screener-grid td:nth-child(9),
          .screener-grid th:nth-child(10), .screener-grid td:nth-child(10),
          .screener-grid th:nth-child(11), .screener-grid td:nth-child(11) { width: 75px; min-width: 75px; } /* 1W-4W */
          .screener-grid th:nth-child(12), .screener-grid td:nth-child(12),
          .screener-grid th:nth-child(13), .screener-grid td:nth-child(13),
          .screener-grid th:nth-child(14), .screener-grid td:nth-child(14),
          .screener-grid th:nth-child(15), .screener-grid td:nth-child(15) { width: 95px; min-width: 95px; } /* Stop/T1/T2/T3 */
          .screener-grid th:nth-child(16), .screener-grid td:nth-child(16) { width: 90px; min-width: 90px; } /* Upside */
          .screener-grid th:nth-child(17), .screener-grid td:nth-child(17) { width: 75px; min-width: 75px; } /* R:R */
          .screener-grid th:nth-child(18), .screener-grid td:nth-child(18) { width: 80px; min-width: 80px; } /* TQS */
          .screener-grid th:nth-child(19), .screener-grid td:nth-child(19) { width: 100px; min-width: 100px; } /* Shares */
          .screener-grid th:nth-child(20), .screener-grid td:nth-child(20) { width: 90px; min-width: 90px; } /* Vol Brk */
          .screener-grid th:nth-child(21), .screener-grid td:nth-child(21) { width: 85px; min-width: 85px; } /* RSI */
          .screener-grid th:nth-child(22), .screener-grid td:nth-child(22) { width: 75px; min-width: 75px; } /* CMF */
          .screener-grid th:nth-child(23), .screener-grid td:nth-child(23) { width: 65px; min-width: 65px; } /* StoK */
          .screener-grid th:nth-child(24), .screener-grid td:nth-child(24) { width: 65px; min-width: 65px; } /* StoD */
          .screener-grid th:nth-child(25), .screener-grid td:nth-child(25),
          .screener-grid th:nth-child(26), .screener-grid td:nth-child(26),
          .screener-grid th:nth-child(27), .screener-grid td:nth-child(27),
          .screener-grid th:nth-child(28), .screener-grid td:nth-child(28),
          .screener-grid th:nth-child(29), .screener-grid td:nth-child(29),
          .screener-grid th:nth-child(30), .screener-grid td:nth-child(30),
          .screener-grid th:nth-child(31), .screener-grid td:nth-child(31) { width: 70px; min-width: 70px; } /* Averages & Technicals */
          .screener-grid th:nth-child(32), .screener-grid td:nth-child(32) { width: 90px; min-width: 90px; } /* RS 1M */
          .screener-grid th:nth-child(33), .screener-grid td:nth-child(33) { width: 150px; min-width: 150px; } /* Patterns */
          .screener-grid th:nth-child(34), .screener-grid td:nth-child(34) { width: 120px; min-width: 120px; } /* ML Signal */
          .screener-grid th:nth-child(35), .screener-grid td:nth-child(35) { width: 72px; min-width: 72px; } /* EMA Ribbon */
          .screener-grid th:nth-child(36), .screener-grid td:nth-child(36) { width: 68px; min-width: 68px; } /* Golden-X */
          .screener-grid th:nth-child(37), .screener-grid td:nth-child(37) { width: 72px; min-width: 72px; } /* MACD-X */
          .screener-grid th:nth-child(38), .screener-grid td:nth-child(38) { width: 68px; min-width: 68px; } /* CMF-X */
          /* New indicator columns */
          .screener-grid th:nth-child(39), .screener-grid td:nth-child(39) { width: 68px; min-width: 68px; } /* HM Signal */
          .screener-grid th:nth-child(40), .screener-grid td:nth-child(40) { width: 68px; min-width: 68px; } /* RSI Div */
          .screener-grid th:nth-child(41), .screener-grid td:nth-child(41) { width: 68px; min-width: 68px; } /* MACD Div */
          .screener-grid th:nth-child(42), .screener-grid td:nth-child(42) { width: 68px; min-width: 68px; } /* ZLEMA Pos */
          .screener-grid th:nth-child(43), .screener-grid td:nth-child(43) { width: 70px; min-width: 70px; } /* Candle */
          .screener-grid th:nth-child(44), .screener-grid td:nth-child(44) { width: 90px; min-width: 90px; } /* CPR Daily */
          .screener-grid th:nth-child(45), .screener-grid td:nth-child(45) { width: 80px; min-width: 80px; } /* CPR Weekly */
          .screener-grid th:nth-child(46), .screener-grid td:nth-child(46) { width: 62px; min-width: 62px; } /* PSY */
          .screener-grid th:nth-child(47), .screener-grid td:nth-child(47) { width: 68px; min-width: 68px; } /* AVWAP */
          /* Fundamental columns */
          .screener-grid th:nth-child(48), .screener-grid td:nth-child(48) { width: 110px; min-width: 110px; } /* Mkt Cap */
          .screener-grid th:nth-child(49), .screener-grid td:nth-child(49) { width: 70px; min-width: 70px; }  /* P/E */
          .screener-grid th:nth-child(50), .screener-grid td:nth-child(50) { width: 70px; min-width: 70px; }  /* P/B */
          .screener-grid th:nth-child(51), .screener-grid td:nth-child(51) { width: 90px; min-width: 90px; }  /* EV/EBITDA */
          .screener-grid th:nth-child(52), .screener-grid td:nth-child(52) { width: 75px; min-width: 75px; }  /* ROE */
          .screener-grid th:nth-child(53), .screener-grid td:nth-child(53) { width: 70px; min-width: 70px; }  /* D/E */
          .screener-grid th:nth-child(54), .screener-grid td:nth-child(54) { width: 85px; min-width: 85px; }  /* Net Mgn */
          .screener-grid th:nth-child(55), .screener-grid td:nth-child(55) { width: 75px; min-width: 75px; }  /* EPS */
          .screener-grid th:nth-child(56), .screener-grid td:nth-child(56) { width: 140px; min-width: 140px; } /* Sector */

          /* Compact active indicators */
          .screener-grid input:focus, .screener-grid select:focus {
            border-color: rgba(168, 85, 247, 0.8) !important;
            box-shadow: 0 0 0 1px rgba(168, 85, 247, 0.2);
          }

          .screener-grid tr.filter-row td {
            overflow: visible !important;
            position: relative;
          }
          .screener-grid tr.filter-row td:focus-within {
            z-index: 40 !important;
          }
        `}</style>
        <table className="screener-grid min-w-max w-full border-collapse text-left text-xs text-slate-300">
          <thead>
            <tr className="border-b border-slate-800 text-xs text-slate-400 uppercase tracking-wider font-mono select-none whitespace-nowrap">
              <th className="py-2 px-2 text-left">Actions</th>
              <th className="py-2 px-1.5 cursor-pointer hover:text-text-main transition" onClick={() => handleSort('symbol')}>
                Ticker {renderSortIcon('symbol')}
              </th>
              <th className="py-2 px-1.5 cursor-pointer hover:text-text-main transition" title="Company Name" onClick={() => handleSort('company_name')}>
                Company {renderSortIcon('company_name')}
              </th>
              <th className="py-2 px-1.5 cursor-pointer hover:text-text-main transition" title="Last End of Day Price" onClick={() => handleSort('close_price')}>
                Price {renderSortIcon('close_price')}
              </th>
              <th className="py-2 px-1.5 cursor-pointer hover:text-text-main transition" title="Price Percentage Change" onClick={() => handleSort('price_pct_change')}>
                Chg% {renderSortIcon('price_pct_change')}
              </th>
              <th className="py-2 px-1.5 text-right cursor-pointer hover:text-text-main transition" title="Average Daily Traded Value (price × volume)" onClick={() => handleSort('avg_traded_value')}>
                Avg Val {renderSortIcon('avg_traded_value')}
              </th>
              <th className="py-2 px-1.5 cursor-pointer hover:text-text-main transition" title="Composite Bias (5-tier: VERY_BULLISH / BULLISH / NEUTRAL / BEARISH / VERY_BEARISH) — sort by composite score" onClick={() => handleSort('composite_score' as any)}>
                Bias {renderSortIcon('composite_score' as any)}
              </th>
              <th className="py-2 px-1 text-right cursor-pointer hover:text-text-main transition" title="1-week rolling return" onClick={() => handleSort('ret_1w')}>
                1W {renderSortIcon('ret_1w')}
              </th>
              <th className="py-2 px-1 text-right cursor-pointer hover:text-text-main transition" title="2-week rolling return" onClick={() => handleSort('ret_2w')}>
                2W {renderSortIcon('ret_2w')}
              </th>
              <th className="py-2 px-1 text-right cursor-pointer hover:text-text-main transition" title="3-week rolling return" onClick={() => handleSort('ret_3w')}>
                3W {renderSortIcon('ret_3w')}
              </th>
              <th className="py-2 px-1 text-right cursor-pointer hover:text-text-main transition" title="4-week rolling return" onClick={() => handleSort('ret_4w')}>
                4W {renderSortIcon('ret_4w')}
              </th>
              <th className="py-2 px-1 text-right cursor-pointer hover:text-text-main transition" title="Stop Loss (Close - 1.5 * ATR)" onClick={() => handleSort('stop_loss')}>
                Stop {renderSortIcon('stop_loss')}
              </th>
              <th className="py-2 px-1 text-right cursor-pointer hover:text-text-main transition" title="Target 1 — strongest structural resistance above price" onClick={() => handleSort('target_1')}>
                T1 {renderSortIcon('target_1')}
              </th>
              <th className="py-2 px-1 text-right cursor-pointer hover:text-text-main transition" title="Target 2 — next structural resistance above T1" onClick={() => handleSort('target_2' as any)}>
                T2 {renderSortIcon('target_2' as any)}
              </th>
              <th className="py-2 px-1 text-right cursor-pointer hover:text-text-main transition" title="Target 3 — third structural resistance" onClick={() => handleSort('target_3' as any)}>
                T3 {renderSortIcon('target_3' as any)}
              </th>
              <th className="py-2 px-1 text-right cursor-pointer hover:text-text-main transition" title="Potential Gain % to Target 1" onClick={() => handleSort('potential_gain_pct')}>
                Upside {renderSortIcon('potential_gain_pct')}
              </th>
              <th className="py-2 px-1 text-right cursor-pointer hover:text-text-main transition" title="Risk-to-Reward Ratio" onClick={() => handleSort('rr_ratio')}>
                R:R {renderSortIcon('rr_ratio')}
              </th>
              <th className="py-2 px-1 text-right cursor-pointer hover:text-text-main transition" title="Trend Quality Score (0–100): ADX strength + price above MAs + MA alignment + RSI zone" onClick={() => handleSort('tqs' as any)}>
                TQS {renderSortIcon('tqs' as any)}
              </th>
              <th className="py-2 px-1 text-center cursor-pointer hover:text-text-main transition" title="Weinstein Stage (1=Basing, 2=Markup, 3=Topping, 4=Decline)" onClick={() => handleSort('weinstein_stage' as any)}>
                Stage {renderSortIcon('weinstein_stage' as any)}
              </th>
              <th className="py-2 px-1 text-right cursor-pointer hover:text-text-main transition" title="Suggested position size (shares) based on risk budget ÷ stop distance" onClick={() => handleSort('position_size_shares' as any)}>
                Shares {renderSortIcon('position_size_shares' as any)}
              </th>
              <th className="py-2 px-1.5 text-center cursor-pointer hover:text-text-main transition" title="Volume Breakout Ratio" onClick={() => handleSort('volume_breakout_ratio')}>
                Vol Brk {renderSortIcon('volume_breakout_ratio')}
              </th>
              <th className="py-2 px-1.5 text-center cursor-pointer hover:text-text-main transition" title="Relative Strength Index (14)" onClick={() => handleSort('rsi_14')}>
                RSI {renderSortIcon('rsi_14')}
              </th>
              <th className="py-2 px-1.5 text-center cursor-pointer hover:text-text-main transition" title="Chaikin Money Flow (20)" onClick={() => handleSort('cmf_20' as any)}>
                CMF {renderSortIcon('cmf_20' as any)}
              </th>
              <th className="py-2 px-1.5 text-center cursor-pointer hover:text-text-main transition" title="StochRSI %K (14,14,3,3)" onClick={() => handleSort('stochrsi_k' as any)}>
                StoK {renderSortIcon('stochrsi_k' as any)}
              </th>
              <th className="py-2 px-1.5 text-center cursor-pointer hover:text-text-main transition" title="StochRSI %D (signal line)" onClick={() => handleSort('stochrsi_d' as any)}>
                StoD {renderSortIcon('stochrsi_d' as any)}
              </th>
              <th className="py-2 px-1.5 text-center cursor-pointer hover:text-text-main transition" title="SMA 20 position" onClick={() => handleSort('sma_20_cross_direction')}>
                S20 {renderSortIcon('sma_20_cross_direction')}
              </th>
              <th className="py-2 px-1.5 text-center cursor-pointer hover:text-text-main transition" title="SMA 50 position" onClick={() => handleSort('sma_50_cross_direction')}>
                S50 {renderSortIcon('sma_50_cross_direction')}
              </th>
              <th className="py-2 px-1.5 text-center cursor-pointer hover:text-text-main transition" title="SMA 200 position" onClick={() => handleSort('sma_200_cross_direction')}>
                S200 {renderSortIcon('sma_200_cross_direction')}
              </th>
              <th className="py-2 px-1.5 text-center cursor-pointer hover:text-text-main transition" title="MACD Trend (BULLISH / BEARISH)" onClick={() => handleSort('macd_trend')}>
                MACD {renderSortIcon('macd_trend')}
              </th>
              <th className="py-2 px-1.5 text-center cursor-pointer hover:text-text-main transition" title="Heikin Ashi Direction (UP / DOWN)" onClick={() => handleSort('ha_direction')}>
                HA {renderSortIcon('ha_direction')}
              </th>
              <th className="py-2 px-1.5 text-center cursor-pointer hover:text-text-main transition" title="Renko Brick Direction (UP / DOWN)" onClick={() => handleSort('renko_direction')}>
                Renko {renderSortIcon('renko_direction')}
              </th>
              <th className="py-2 px-1.5 text-center cursor-pointer hover:text-text-main transition" title="Three Line Break Direction (UP / DOWN)" onClick={() => handleSort('line_break_direction')}>
                TLB {renderSortIcon('line_break_direction')}
              </th>
              <th className="py-2 px-1.5 text-center cursor-pointer hover:text-text-main transition" title="1-Month Relative Strength vs NIFTY 50" onClick={() => handleSort('rs_score_1m' as any)}>
                RS 1M {renderSortIcon('rs_score_1m' as any)}
              </th>
              <th className="py-2 px-1.5 text-center" title="Pattern triggers">Patterns</th>
              <th className="py-2 px-1.5 text-center cursor-pointer hover:text-text-main transition" title="Days since EMA9 crossed above EMA20 (golden ribbon)" onClick={() => handleSort('days_since_ema9_ema20_bull')}>
                EMA Rbbn {renderSortIcon('days_since_ema9_ema20_bull')}
              </th>
              <th className="py-2 px-1.5 text-center cursor-pointer hover:text-text-main transition" title="Days since SMA20 crossed above SMA50 (golden cross)" onClick={() => handleSort('days_since_sma20_sma50_bull')}>
                Gold-X {renderSortIcon('days_since_sma20_sma50_bull')}
              </th>
              <th className="py-2 px-1.5 text-center cursor-pointer hover:text-text-main transition" title="Days since MACD crossed above signal line" onClick={() => handleSort('days_since_macd_bull')}>
                MACD-X {renderSortIcon('days_since_macd_bull')}
              </th>
              <th className="py-2 px-1.5 text-center cursor-pointer hover:text-text-main transition" title="Days since CMF crossed above zero" onClick={() => handleSort('days_since_cmf_bull')}>
                CMF-X {renderSortIcon('days_since_cmf_bull')}
              </th>
              <th className="py-2 px-1 text-center cursor-pointer hover:text-text-main transition" title="Hilega-Milega: BUY = RSI currently above its 21-WMA (bullish momentum), SELL = below" onClick={() => handleSort('hilega_milega_signal' as any)}>
                HM {renderSortIcon('hilega_milega_signal' as any)}
              </th>
              <th className="py-2 px-1 text-center cursor-pointer hover:text-text-main transition" title="RSI Divergence: BULLISH (lower price low, higher RSI low) or BEARISH" onClick={() => handleSort('rsi_divergence' as any)}>
                RSI Div {renderSortIcon('rsi_divergence' as any)}
              </th>
              <th className="py-2 px-1 text-center cursor-pointer hover:text-text-main transition" title="MACD Histogram Divergence: BULLISH or BEARISH" onClick={() => handleSort('macd_divergence' as any)}>
                MACD Div {renderSortIcon('macd_divergence' as any)}
              </th>
              <th className="py-2 px-1 text-center cursor-pointer hover:text-text-main transition" title="Zero-Lag EMA(21) position — ABOVE or BELOW" onClick={() => handleSort('price_vs_zlema21' as any)}>
                ZLEMA {renderSortIcon('price_vs_zlema21' as any)}
              </th>
              <th className="py-2 px-1 text-center" title="Candle type: 😴 Boring (wicks > body) / 💥 Explosive (≥1.5× prior boring range)">
                Candle
              </th>
              <th className="py-2 px-1 text-center cursor-pointer hover:text-text-main transition" title="Daily CPR Pivot (PP). Narrow badge if CPR range < 0.5% of price" onClick={() => handleSort('cpr_daily_pivot' as any)}>
                CPR D {renderSortIcon('cpr_daily_pivot' as any)}
              </th>
              <th className="py-2 px-1 text-center cursor-pointer hover:text-text-main transition" title="Weekly CPR Pivot (PP)" onClick={() => handleSort('cpr_weekly_pivot' as any)}>
                CPR W {renderSortIcon('cpr_weekly_pivot' as any)}
              </th>
              <th className="py-2 px-1 text-center cursor-pointer hover:text-text-main transition" title="Psychological Line (20-day): % of days where close > prev close" onClick={() => handleSort('psy_20' as any)}>
                PSY {renderSortIcon('psy_20' as any)}
              </th>
              <th className="py-2 px-1 text-center cursor-pointer hover:text-text-main transition" title="Anchored VWAP (from last gap-up candle): ABOVE or BELOW" onClick={() => handleSort('price_vs_avwap' as any)}>
                AVWAP {renderSortIcon('price_vs_avwap' as any)}
              </th>
              <th className="py-2 px-1.5 text-right cursor-pointer hover:text-text-main transition" title="Market Capitalisation" onClick={() => handleSort('market_cap' as any)}>
                Mkt Cap {renderSortIcon('market_cap' as any)}
              </th>
              <th className="py-2 px-1.5 text-right cursor-pointer hover:text-text-main transition" title="Price-to-Earnings Ratio (TTM)" onClick={() => handleSort('pe_ratio' as any)}>
                P/E {renderSortIcon('pe_ratio' as any)}
              </th>
              <th className="py-2 px-1.5 text-right cursor-pointer hover:text-text-main transition" title="Price-to-Book Ratio" onClick={() => handleSort('pb_ratio' as any)}>
                P/B {renderSortIcon('pb_ratio' as any)}
              </th>
              <th className="py-2 px-1.5 text-right cursor-pointer hover:text-text-main transition" title="EV / EBITDA" onClick={() => handleSort('ev_ebitda' as any)}>
                EV/EB {renderSortIcon('ev_ebitda' as any)}
              </th>
              <th className="py-2 px-1.5 text-right cursor-pointer hover:text-text-main transition" title="Return on Equity (%)" onClick={() => handleSort('roe' as any)}>
                ROE {renderSortIcon('roe' as any)}
              </th>
              <th className="py-2 px-1.5 text-right cursor-pointer hover:text-text-main transition" title="Debt to Equity Ratio" onClick={() => handleSort('debt_to_equity' as any)}>
                D/E {renderSortIcon('debt_to_equity' as any)}
              </th>
              <th className="py-2 px-1.5 text-right cursor-pointer hover:text-text-main transition" title="Net Profit Margin (%)" onClick={() => handleSort('profit_margin' as any)}>
                Net Mgn {renderSortIcon('profit_margin' as any)}
              </th>
              <th className="py-2 px-1.5 text-right cursor-pointer hover:text-text-main transition" title="Earnings Per Share (TTM)" onClick={() => handleSort('eps_ttm' as any)}>
                EPS {renderSortIcon('eps_ttm' as any)}
              </th>
              <th className="py-2 px-1.5 cursor-pointer hover:text-text-main transition" title="Sector" onClick={() => handleSort('sector' as any)}>
                Sector {renderSortIcon('sector' as any)}
              </th>
            </tr>
            {showColFilters && (
              <tr className="border-b border-border-subtle bg-bg-base/40 whitespace-nowrap filter-row">
                {/* Actions — empty, no filter */}
                <td className="py-1 px-2" />
                {/* Ticker */}
                <td className="py-1 px-1.5">
                  <input
                    type="text"
                    placeholder="Filter..."
                    value={colFilters.symbol}
                    onChange={(e) => setColFilters({ ...colFilters, symbol: e.target.value })}
                    className="w-full min-w-[50px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 placeholder-slate-650 focus:outline-none focus:border-purple-500 focus:text-text-main transition font-mono"
                  />
                </td>

                {/* Company */}
                <td className="py-1 px-1.5">
                  <input
                    type="text"
                    placeholder="Filter..."
                    value={colFilters.company_name}
                    onChange={(e) => setColFilters({ ...colFilters, company_name: e.target.value })}
                    className="w-full min-w-[75px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 placeholder-slate-650 focus:outline-none focus:border-purple-500 focus:text-text-main transition"
                  />
                </td>

                {/* Price */}
                <td className="py-1 px-1.5">
                  <input
                    type="text"
                    placeholder=">100"
                    value={colFilters.close_price}
                    onChange={(e) => setColFilters({ ...colFilters, close_price: e.target.value })}
                    className="w-full min-w-[50px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 placeholder-slate-650 focus:outline-none focus:border-purple-500 focus:text-text-main transition font-mono"
                  />
                </td>

                {/* Chg% */}
                <td className="py-1 px-1.5">
                  <input
                    type="text"
                    placeholder=">0"
                    value={colFilters.price_pct_change}
                    onChange={(e) => setColFilters({ ...colFilters, price_pct_change: e.target.value })}
                    className="w-full min-w-[45px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 placeholder-slate-650 focus:outline-none focus:border-purple-500 focus:text-text-main transition font-mono"
                  />
                </td>

                {/* Avg Vol */}
                <td className="py-1 px-1.5">
                  <input
                    type="text"
                    placeholder=">100k"
                    value={colFilters.avg_traded_value}
                    onChange={(e) => setColFilters({ ...colFilters, avg_traded_value: e.target.value })}
                    className="w-full min-w-[60px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 placeholder-slate-650 focus:outline-none focus:border-purple-500 focus:text-text-main text-right transition font-mono"
                  />
                </td>

                {/* Bias */}
                <td className="py-1 px-1.5">
                  <MultiSelectFilter
                    value={colFilters.regime_bias}
                    onChange={(val) => setColFilters({ ...colFilters, regime_bias: val })}
                    placeholder="All"
                    minWidth="65px"
                    options={[
                      { value: 'VERY_BULLISH', label: 'VB+', className: 'text-emerald-400 font-bold' },
                      { value: 'BULLISH', label: 'Bull', className: 'text-emerald-500' },
                      { value: 'NEUTRAL', label: 'Neut', className: 'text-slate-400' },
                      { value: 'BEARISH', label: 'Bear', className: 'text-rose-500' },
                      { value: 'VERY_BEARISH', label: 'VB-', className: 'text-rose-400 font-bold' },
                    ]}
                  />
                </td>

                {/* 1W */}
                <td className="py-1 px-1">
                  <input
                    type="text"
                    placeholder=">0"
                    value={colFilters.ret_1w}
                    onChange={(e) => setColFilters({ ...colFilters, ret_1w: e.target.value })}
                    className="w-full min-w-[40px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-350 placeholder-slate-650 focus:outline-none focus:border-purple-500 focus:text-text-main text-right transition font-mono"
                  />
                </td>
                {/* 2W */}
                <td className="py-1 px-1">
                  <input
                    type="text"
                    placeholder=">0"
                    value={colFilters.ret_2w}
                    onChange={(e) => setColFilters({ ...colFilters, ret_2w: e.target.value })}
                    className="w-full min-w-[40px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-355 placeholder-slate-650 focus:outline-none focus:border-purple-500 focus:text-text-main text-right transition font-mono"
                  />
                </td>
                {/* 3W */}
                <td className="py-1 px-1">
                  <input
                    type="text"
                    placeholder=">0"
                    value={colFilters.ret_3w}
                    onChange={(e) => setColFilters({ ...colFilters, ret_3w: e.target.value })}
                    className="w-full min-w-[40px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-350 placeholder-slate-650 focus:outline-none focus:border-purple-500 focus:text-text-main text-right transition font-mono"
                  />
                </td>
                {/* 4W */}
                <td className="py-1 px-1">
                  <input
                    type="text"
                    placeholder=">0"
                    value={colFilters.ret_4w}
                    onChange={(e) => setColFilters({ ...colFilters, ret_4w: e.target.value })}
                    className="w-full min-w-[40px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-350 placeholder-slate-650 focus:outline-none focus:border-purple-500 focus:text-text-main text-right transition font-mono"
                  />
                </td>

                {/* Stop */}
                <td className="py-1 px-1">
                  <input
                    type="text"
                    placeholder=">0"
                    value={colFilters.stop_loss}
                    onChange={(e) => setColFilters({ ...colFilters, stop_loss: e.target.value })}
                    className="w-full min-w-[50px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 placeholder-slate-650 focus:outline-none focus:border-purple-500 focus:text-text-main text-right transition font-mono"
                  />
                </td>
                {/* T1 */}
                <td className="py-1 px-1">
                  <input
                    type="text"
                    placeholder=">0"
                    value={colFilters.target_1}
                    onChange={(e) => setColFilters({ ...colFilters, target_1: e.target.value })}
                    className="w-full min-w-[50px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 placeholder-slate-650 focus:outline-none focus:border-purple-500 focus:text-text-main text-right transition font-mono"
                  />
                </td>
                {/* T2 */}
                <td className="py-1 px-1">
                  <input
                    type="text"
                    placeholder=">0"
                    value={colFilters.target_2}
                    onChange={(e) => setColFilters({ ...colFilters, target_2: e.target.value })}
                    className="w-full min-w-[50px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 placeholder-slate-650 focus:outline-none focus:border-purple-500 focus:text-text-main text-right transition font-mono"
                  />
                </td>
                {/* T3 */}
                <td className="py-1 px-1">
                  <input
                    type="text"
                    placeholder=">0"
                    value={colFilters.target_3}
                    onChange={(e) => setColFilters({ ...colFilters, target_3: e.target.value })}
                    className="w-full min-w-[50px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 placeholder-slate-650 focus:outline-none focus:border-purple-500 focus:text-text-main text-right transition font-mono"
                  />
                </td>
                {/* Upside */}
                <td className="py-1 px-1">
                  <input
                    type="text"
                    placeholder=">5"
                    value={colFilters.potential_gain_pct}
                    onChange={(e) => setColFilters({ ...colFilters, potential_gain_pct: e.target.value })}
                    className="w-full min-w-[45px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 placeholder-slate-650 focus:outline-none focus:border-purple-500 focus:text-text-main text-right transition font-mono"
                  />
                </td>
                {/* R:R */}
                <td className="py-1 px-1">
                  <input
                    type="text"
                    placeholder=">2"
                    value={colFilters.rr_ratio}
                    onChange={(e) => setColFilters({ ...colFilters, rr_ratio: e.target.value })}
                    className="w-full min-w-[40px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 placeholder-slate-650 focus:outline-none focus:border-purple-500 focus:text-text-main text-right transition font-mono"
                  />
                </td>
                {/* TQS */}
                <td className="py-1 px-1">
                  <input
                    type="text"
                    placeholder=">60"
                    value={colFilters.tqs}
                    onChange={(e) => setColFilters({ ...colFilters, tqs: e.target.value })}
                    className="w-full min-w-[40px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 placeholder-slate-650 focus:outline-none focus:border-purple-500 focus:text-text-main text-right transition font-mono"
                  />
                </td>
                {/* Weinstein Stage */}
                <td className="py-1 px-1">
                  <input
                    type="text"
                    placeholder="=2"
                    value={colFilters.weinstein_stage}
                    onChange={(e) => setColFilters({ ...colFilters, weinstein_stage: e.target.value })}
                    className="w-full min-w-[36px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 placeholder-slate-650 focus:outline-none focus:border-purple-500 focus:text-text-main text-center transition font-mono"
                  />
                </td>
                {/* Shares */}
                <td className="py-1 px-1">
                  <input
                    type="text"
                    placeholder=">0"
                    value={colFilters.position_size_shares}
                    onChange={(e) => setColFilters({ ...colFilters, position_size_shares: e.target.value })}
                    className="w-full min-w-[50px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 placeholder-slate-650 focus:outline-none focus:border-purple-500 focus:text-text-main text-right transition font-mono"
                  />
                </td>
                {/* Vol Brk */}
                <td className="py-1 px-1.5 text-center">
                  <input
                    type="text"
                    placeholder=">1.5"
                    value={colFilters.volume_breakout_ratio}
                    onChange={(e) => setColFilters({ ...colFilters, volume_breakout_ratio: e.target.value })}
                    className="w-full min-w-[45px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 placeholder-slate-650 focus:outline-none focus:border-purple-500 focus:text-text-main text-center transition font-mono"
                  />
                </td>
                {/* RSI */}
                <td className="py-1 px-1.5 text-center">
                  <input
                    type="text"
                    placeholder="<30"
                    value={colFilters.rsi_14}
                    onChange={(e) => setColFilters({ ...colFilters, rsi_14: e.target.value })}
                    className="w-full min-w-[45px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 placeholder-slate-650 focus:outline-none focus:border-purple-500 focus:text-text-main text-center transition font-mono"
                  />
                </td>

                {/* CMF */}
                <td className="py-1 px-1.5 text-center">
                  <input
                    type="text"
                    placeholder=">0.1"
                    value={colFilters.cmf_20}
                    onChange={(e) => setColFilters({ ...colFilters, cmf_20: e.target.value })}
                    className="w-full min-w-[45px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 placeholder-slate-650 focus:outline-none focus:border-purple-500 focus:text-text-main text-center transition font-mono"
                  />
                </td>

                {/* StoK */}
                <td className="py-1 px-1.5 text-center">
                  <input
                    type="text"
                    placeholder="<20"
                    value={colFilters.stochrsi_k}
                    onChange={(e) => setColFilters({ ...colFilters, stochrsi_k: e.target.value })}
                    className="w-full min-w-[40px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 placeholder-slate-650 focus:outline-none focus:border-purple-500 focus:text-text-main text-center transition font-mono"
                  />
                </td>

                {/* StoD */}
                <td className="py-1 px-1.5 text-center">
                  <input
                    type="text"
                    placeholder="<20"
                    value={colFilters.stochrsi_d}
                    onChange={(e) => setColFilters({ ...colFilters, stochrsi_d: e.target.value })}
                    className="w-full min-w-[40px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 placeholder-slate-650 focus:outline-none focus:border-purple-500 focus:text-text-main text-center transition font-mono"
                  />
                </td>

                {/* S20 */}
                <td className="py-1 px-1.5 text-center">
                  <MultiSelectFilter
                    value={colFilters.sma_20_cross_direction}
                    onChange={(val) => setColFilters({ ...colFilters, sma_20_cross_direction: val })}
                    placeholder="All"
                    minWidth="50px"
                    options={[
                      { value: 'ABOVE', label: '▲ Above', className: 'text-indigo-400 font-bold' },
                      { value: 'BELOW', label: '▼ Below', className: 'text-amber-500 font-bold' },
                    ]}
                  />
                </td>
                {/* S50 */}
                <td className="py-1 px-1.5 text-center">
                  <MultiSelectFilter
                    value={colFilters.sma_50_cross_direction}
                    onChange={(val) => setColFilters({ ...colFilters, sma_50_cross_direction: val })}
                    placeholder="All"
                    minWidth="50px"
                    options={[
                      { value: 'ABOVE', label: '▲ Above', className: 'text-indigo-400 font-bold' },
                      { value: 'BELOW', label: '▼ Below', className: 'text-amber-500 font-bold' },
                    ]}
                  />
                </td>
                {/* S200 */}
                <td className="py-1 px-1.5 text-center">
                  <MultiSelectFilter
                    value={colFilters.sma_200_cross_direction}
                    onChange={(val) => setColFilters({ ...colFilters, sma_200_cross_direction: val })}
                    placeholder="All"
                    minWidth="50px"
                    options={[
                      { value: 'ABOVE', label: '▲ Above', className: 'text-indigo-400 font-bold' },
                      { value: 'BELOW', label: '▼ Below', className: 'text-amber-500 font-bold' },
                    ]}
                  />
                </td>

                {/* MACD */}
                <td className="py-1 px-1.5 text-center">
                  <MultiSelectFilter
                    value={colFilters.macd_trend}
                    onChange={(val) => setColFilters({ ...colFilters, macd_trend: val })}
                    placeholder="All"
                    minWidth="50px"
                    options={[
                      { value: 'BULLISH', label: '▲ Bull', className: 'text-emerald-400 font-bold' },
                      { value: 'BEARISH', label: '▼ Bear', className: 'text-rose-400 font-bold' },
                    ]}
                  />
                </td>

                {/* HA */}
                <td className="py-1 px-1.5 text-center">
                  <MultiSelectFilter
                    value={colFilters.ha_direction}
                    onChange={(val) => setColFilters({ ...colFilters, ha_direction: val })}
                    placeholder="All"
                    minWidth="50px"
                    options={[
                      { value: 'UP', label: '▲ UP', className: 'text-emerald-400 font-bold' },
                      { value: 'DOWN', label: '▼ DOWN', className: 'text-rose-400 font-bold' },
                    ]}
                  />
                </td>

                {/* Renko */}
                <td className="py-1 px-1.5 text-center">
                  <MultiSelectFilter
                    value={colFilters.renko_direction}
                    onChange={(val) => setColFilters({ ...colFilters, renko_direction: val })}
                    placeholder="All"
                    minWidth="50px"
                    options={[
                      { value: 'UP', label: '▲ UP', className: 'text-emerald-400 font-bold' },
                      { value: 'DOWN', label: '▼ DOWN', className: 'text-rose-400 font-bold' },
                    ]}
                  />
                </td>

                {/* TLB */}
                <td className="py-1 px-1.5 text-center">
                  <MultiSelectFilter
                    value={colFilters.line_break_direction}
                    onChange={(val) => setColFilters({ ...colFilters, line_break_direction: val })}
                    placeholder="All"
                    minWidth="50px"
                    options={[
                      { value: 'UP', label: '▲ UP', className: 'text-emerald-400 font-bold' },
                      { value: 'DOWN', label: '▼ DOWN', className: 'text-rose-400 font-bold' },
                    ]}
                  />
                </td>

                {/* RS 1M */}
                <td className="py-1 px-1.5 text-center">
                  <input
                    type="text"
                    placeholder=">1.2"
                    value={colFilters.rs_score_1m}
                    onChange={(e) => setColFilters({ ...colFilters, rs_score_1m: e.target.value })}
                    className="w-full min-w-[45px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 placeholder-slate-650 focus:outline-none focus:border-purple-500 focus:text-text-main text-center transition font-mono"
                  />
                </td>

                {/* Patterns */}
                <td className="py-1 px-1.5 text-center">
                  <MultiSelectFilter
                    value={colFilters.patterns}
                    onChange={(val) => setColFilters({ ...colFilters, patterns: val })}
                    placeholder="All"
                    minWidth="65px"
                    options={[
                      { value: 'NR7', label: 'NR7' },
                      { value: 'Inside', label: 'Inside' },
                      { value: 'Gap+', label: 'Gap+' },
                      { value: 'Gap-', label: 'Gap-' },
                    ]}
                  />
                </td>

                {/* EMA Ribbon */}
                <td className="py-1 px-1.5 text-center">
                  <input
                    type="text"
                    placeholder="<5"
                    value={colFilters.days_since_ema9_ema20_bull}
                    onChange={(e) => setColFilters({ ...colFilters, days_since_ema9_ema20_bull: e.target.value })}
                    className="w-full min-w-[40px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 placeholder-slate-650 focus:outline-none focus:border-purple-500 focus:text-text-main text-center transition font-mono"
                  />
                </td>

                {/* Golden Cross */}
                <td className="py-1 px-1.5 text-center">
                  <input
                    type="text"
                    placeholder="<10"
                    value={colFilters.days_since_sma20_sma50_bull}
                    onChange={(e) => setColFilters({ ...colFilters, days_since_sma20_sma50_bull: e.target.value })}
                    className="w-full min-w-[40px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 placeholder-slate-650 focus:outline-none focus:border-purple-500 focus:text-text-main text-center transition font-mono"
                  />
                </td>

                {/* MACD Xover */}
                <td className="py-1 px-1.5 text-center">
                  <input
                    type="text"
                    placeholder="<5"
                    value={colFilters.days_since_macd_bull}
                    onChange={(e) => setColFilters({ ...colFilters, days_since_macd_bull: e.target.value })}
                    className="w-full min-w-[40px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 placeholder-slate-650 focus:outline-none focus:border-purple-500 focus:text-text-main text-center transition font-mono"
                  />
                </td>

                {/* CMF Xover */}
                <td className="py-1 px-1.5 text-center">
                  <input
                    type="text"
                    placeholder="<5"
                    value={colFilters.days_since_cmf_bull}
                    onChange={(e) => setColFilters({ ...colFilters, days_since_cmf_bull: e.target.value })}
                    className="w-full min-w-[40px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 placeholder-slate-650 focus:outline-none focus:border-purple-500 focus:text-text-main text-center transition font-mono"
                  />
                </td>

                {/* HM Signal — days in buy zone */}
                <td className="py-1 px-1.5 text-center">
                  <input
                    type="text"
                    placeholder="<10"
                    title="Days since RSI crossed above WMA. Filter: <5 (fresh), >0 (any buy zone)"
                    value={colFilters.hilega_milega_signal}
                    onChange={(e) => setColFilters({ ...colFilters, hilega_milega_signal: e.target.value })}
                    className="w-full min-w-[40px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 placeholder-slate-650 focus:outline-none focus:border-purple-500 focus:text-text-main text-center transition font-mono"
                  />
                </td>

                {/* RSI Div — days since bullish divergence */}
                <td className="py-1 px-1.5 text-center">
                  <input
                    type="text"
                    placeholder="<7"
                    title="Days since bullish RSI divergence swing low. NULL = no bullish divergence."
                    value={colFilters.rsi_divergence}
                    onChange={(e) => setColFilters({ ...colFilters, rsi_divergence: e.target.value })}
                    className="w-full min-w-[40px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 placeholder-slate-650 focus:outline-none focus:border-purple-500 focus:text-text-main text-center transition font-mono"
                  />
                </td>

                {/* MACD Div — days since bullish divergence */}
                <td className="py-1 px-1.5 text-center">
                  <input
                    type="text"
                    placeholder="<7"
                    title="Days since bullish MACD divergence swing low. NULL = no bullish divergence."
                    value={colFilters.macd_divergence}
                    onChange={(e) => setColFilters({ ...colFilters, macd_divergence: e.target.value })}
                    className="w-full min-w-[40px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 placeholder-slate-650 focus:outline-none focus:border-purple-500 focus:text-text-main text-center transition font-mono"
                  />
                </td>

                {/* ZLEMA Position */}
                <td className="py-1 px-1.5 text-center">
                  <select
                    value={colFilters.price_vs_zlema21}
                    onChange={(e) => setColFilters({ ...colFilters, price_vs_zlema21: e.target.value })}
                    className="w-full min-w-[52px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 focus:outline-none focus:border-purple-500 focus:text-text-main transition"
                  >
                    <option value="">All</option>
                    <option value="ABOVE">ABOVE</option>
                    <option value="BELOW">BELOW</option>
                  </select>
                </td>

                {/* Candle */}
                <td className="py-1 px-1.5 text-center">
                  <select
                    value={colFilters.candle_type}
                    onChange={(e) => setColFilters({ ...colFilters, candle_type: e.target.value })}
                    className="w-full min-w-[52px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 focus:outline-none focus:border-purple-500 focus:text-text-main transition"
                  >
                    <option value="">All</option>
                    <option value="BORING">😴 Boring</option>
                    <option value="EXPLOSIVE">💥 Explos</option>
                  </select>
                </td>

                {/* CPR Daily */}
                <td className="py-1 px-1.5 text-center">
                  <select
                    value={colFilters.cpr_daily_narrow}
                    onChange={(e) => setColFilters({ ...colFilters, cpr_daily_narrow: e.target.value })}
                    className="w-full min-w-[52px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 focus:outline-none focus:border-purple-500 focus:text-text-main transition"
                  >
                    <option value="">All</option>
                    <option value="NARROW">Narrow</option>
                  </select>
                </td>

                {/* CPR Weekly */}
                <td className="py-1 px-1.5 text-center">
                  <select
                    value={colFilters.cpr_weekly_narrow}
                    onChange={(e) => setColFilters({ ...colFilters, cpr_weekly_narrow: e.target.value })}
                    className="w-full min-w-[52px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 focus:outline-none focus:border-purple-500 focus:text-text-main transition"
                  >
                    <option value="">All</option>
                    <option value="NARROW">Narrow</option>
                  </select>
                </td>

                {/* PSY-20 */}
                <td className="py-1 px-1.5 text-center">
                  <input
                    type="text"
                    placeholder=">50"
                    value={colFilters.psy_20}
                    onChange={(e) => setColFilters({ ...colFilters, psy_20: e.target.value })}
                    className="w-full min-w-[40px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 placeholder-slate-650 focus:outline-none focus:border-purple-500 focus:text-text-main text-center transition font-mono"
                  />
                </td>

                {/* AVWAP Position */}
                <td className="py-1 px-1.5 text-center">
                  <select
                    value={colFilters.price_vs_avwap}
                    onChange={(e) => setColFilters({ ...colFilters, price_vs_avwap: e.target.value })}
                    className="w-full min-w-[52px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 focus:outline-none focus:border-purple-500 focus:text-text-main transition"
                  >
                    <option value="">All</option>
                    <option value="ABOVE">ABOVE</option>
                    <option value="BELOW">BELOW</option>
                  </select>
                </td>

                {/* Mkt Cap */}
                <td className="py-1 px-1.5 text-right">
                  <input
                    type="text"
                    placeholder=">1000cr"
                    value={colFilters.market_cap}
                    onChange={(e) => setColFilters({ ...colFilters, market_cap: e.target.value })}
                    className="w-full min-w-[65px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 placeholder-slate-650 focus:outline-none focus:border-blue-500 focus:text-text-main text-right transition font-mono"
                  />
                </td>

                {/* P/E */}
                <td className="py-1 px-1.5 text-right">
                  <input
                    type="text"
                    placeholder="<30"
                    value={colFilters.pe_ratio}
                    onChange={(e) => setColFilters({ ...colFilters, pe_ratio: e.target.value })}
                    className="w-full min-w-[40px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 placeholder-slate-650 focus:outline-none focus:border-blue-500 focus:text-text-main text-right transition font-mono"
                  />
                </td>

                {/* P/B */}
                <td className="py-1 px-1.5 text-right">
                  <input
                    type="text"
                    placeholder="<5"
                    value={colFilters.pb_ratio}
                    onChange={(e) => setColFilters({ ...colFilters, pb_ratio: e.target.value })}
                    className="w-full min-w-[40px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 placeholder-slate-650 focus:outline-none focus:border-blue-500 focus:text-text-main text-right transition font-mono"
                  />
                </td>

                {/* EV/EBITDA */}
                <td className="py-1 px-1.5 text-right">
                  <input
                    type="text"
                    placeholder="<20"
                    value={colFilters.ev_ebitda}
                    onChange={(e) => setColFilters({ ...colFilters, ev_ebitda: e.target.value })}
                    className="w-full min-w-[50px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 placeholder-slate-650 focus:outline-none focus:border-blue-500 focus:text-text-main text-right transition font-mono"
                  />
                </td>

                {/* ROE */}
                <td className="py-1 px-1.5 text-right">
                  <input
                    type="text"
                    placeholder=">15"
                    value={colFilters.roe}
                    onChange={(e) => setColFilters({ ...colFilters, roe: e.target.value })}
                    className="w-full min-w-[40px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 placeholder-slate-650 focus:outline-none focus:border-blue-500 focus:text-text-main text-right transition font-mono"
                  />
                </td>

                {/* D/E */}
                <td className="py-1 px-1.5 text-right">
                  <input
                    type="text"
                    placeholder="<1"
                    value={colFilters.debt_to_equity}
                    onChange={(e) => setColFilters({ ...colFilters, debt_to_equity: e.target.value })}
                    className="w-full min-w-[40px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 placeholder-slate-650 focus:outline-none focus:border-blue-500 focus:text-text-main text-right transition font-mono"
                  />
                </td>

                {/* Net Margin */}
                <td className="py-1 px-1.5 text-right">
                  <input
                    type="text"
                    placeholder=">10"
                    value={colFilters.profit_margin}
                    onChange={(e) => setColFilters({ ...colFilters, profit_margin: e.target.value })}
                    className="w-full min-w-[40px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 placeholder-slate-650 focus:outline-none focus:border-blue-500 focus:text-text-main text-right transition font-mono"
                  />
                </td>

                {/* EPS */}
                <td className="py-1 px-1.5 text-right">
                  <input
                    type="text"
                    placeholder=">10"
                    value={colFilters.eps_ttm}
                    onChange={(e) => setColFilters({ ...colFilters, eps_ttm: e.target.value })}
                    className="w-full min-w-[40px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 placeholder-slate-650 focus:outline-none focus:border-blue-500 focus:text-text-main text-right transition font-mono"
                  />
                </td>

                {/* Sector */}
                <td className="py-1 px-1.5">
                  <input
                    type="text"
                    placeholder="Filter..."
                    value={colFilters.sector}
                    onChange={(e) => setColFilters({ ...colFilters, sector: e.target.value })}
                    className="w-full min-w-[70px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 placeholder-slate-650 focus:outline-none focus:border-blue-500 focus:text-text-main transition"
                  />
                </td>

              </tr>
            )}
          </thead>
          <tbody className="divide-y divide-slate-850">
            {filteredResults.length === 0 ? (
              <tr>
                <td colSpan={47} className="py-16 text-center">
                  {isLoading ? (
                    <span className="text-slate-500 text-xs">Executing database snapshot sweep...</span>
                  ) : screenerResults.length === 0 ? (
                    <div className="flex flex-col items-center gap-3">
                      <span className="text-3xl">🔍</span>
                      <p className="text-slate-400 text-sm font-semibold">No matches</p>
                      <p className="text-slate-600 text-xs max-w-xs">No stocks match the current filters. Try loosening or clearing them.</p>
                    </div>
                  ) : (
                    <span className="text-slate-500 text-xs">No stock matches found for the current criteria.</span>
                  )}
                </td>
              </tr>
            ) : (
              filteredResults.slice(0, visibleCount).map((row) => (
                <ScreenerResultRow
                  key={row.symbol_id}
                  row={row}
                  strategies={strategies}
                  onAddToWatchlist={onAddToWatchlist}
                  onOpenChart={onOpenChart}
                  onAddToQualify={addToQualifyQueue}
                  qualifyQueue={qualifyQueue}
                />
              ))
            )}
          </tbody>
        </table>
        {/* Pagination footer */}
        {filteredResults.length > PAGE_SIZE && (
          <div className="shrink-0 flex items-center justify-between px-4 py-2 border-t border-border-subtle bg-bg-base mt-2">
            <span className="text-xs text-slate-500">
              Showing <span className="text-slate-300 font-semibold">{Math.min(visibleCount, filteredResults.length).toLocaleString()}</span> of <span className="text-slate-300 font-semibold">{filteredResults.length.toLocaleString()}</span> results
            </span>
            <div className="flex gap-2">
              {visibleCount < filteredResults.length && (
                <button
                  onClick={() => setVisibleCount(v => Math.min(v + PAGE_SIZE, filteredResults.length))}
                  className="px-2.5 py-1 text-xs font-bold bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 hover:text-text-main rounded transition cursor-pointer"
                >
                  Load {Math.min(PAGE_SIZE, filteredResults.length - visibleCount)} More
                </button>
              )}
              {visibleCount < filteredResults.length && (
                <button
                  onClick={() => setVisibleCount(filteredResults.length)}
                  className="px-2.5 py-1 text-xs font-bold bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-400 hover:text-text-main rounded transition cursor-pointer"
                >
                  Load All ({filteredResults.length.toLocaleString()})
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
