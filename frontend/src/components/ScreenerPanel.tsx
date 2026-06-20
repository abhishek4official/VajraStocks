import React, { useEffect, useState, useMemo } from 'react';
import { useStockStore } from '../store/useStockStore';
import { Eye, Filter, RefreshCw, BarChart2, Download, Bookmark, Zap, TrendingUp } from 'lucide-react';
import { StockChartWorkspace } from './StockChartWorkspace';
import type { ScreenerRow, StrategyMeta } from '../services/api';
import { apiService } from '../services/api';

// Per-strategy signal chip styling shown in the screener "Patterns / Signals" cell.
const STRAT_SIG_STYLE: Record<string, string> = {
  BUY: 'text-emerald-400 bg-emerald-950/30 border-emerald-800/50',
  WATCH: 'text-amber-400 bg-amber-950/30 border-amber-800/50',
  SELL: 'text-rose-400 bg-rose-950/30 border-rose-800/50',
  NONE: 'text-slate-500 bg-slate-900/40 border-slate-800',
};
const stratCode = (name: string) =>
  name.replace(/[^A-Za-z0-9 ]/g, '').split(' ').map(w => w[0]).join('').slice(0, 3).toUpperCase();

// Per-column in-table filters are cached locally so they survive reloads / tab switches.
const COL_FILTERS_KEY = 'vajra_screener_col_filters';
const SHOW_COL_FILTERS_KEY = 'vajra_screener_show_col_filters';
const DEFAULT_COL_FILTERS = {
  symbol: '', company_name: '', close_price: '', price_pct_change: '', regime_bias: '',
  ret_1w: '', ret_2w: '', ret_3w: '', ret_4w: '', stop_loss: '', target_1: '', target_2: '',
  target_3: '', potential_gain_pct: '', rr_ratio: '', trade_quality_score: '',
  position_size_shares: '', avg_traded_value: '', volume_breakout_ratio: '', rsi_14: '',
  cmf_20: '', stochrsi_k: '', stochrsi_d: '',
  sma_20_cross_direction: '', sma_50_cross_direction: '', sma_200_cross_direction: '',
  macd_trend: '', ha_direction: '', renko_direction: '', line_break_direction: '',
  rs_score_1m: '', patterns: '', ml2_signal: '',
  days_since_ema9_ema20_bull: '', days_since_sma20_sma50_bull: '',
  days_since_macd_bull: '', days_since_cmf_bull: '',
  // Fundamentals
  market_cap: '', pe_ratio: '', pb_ratio: '', ev_ebitda: '',
  roe: '', debt_to_equity: '', profit_margin: '', eps_ttm: '', sector: '',
};
type ColFilters = typeof DEFAULT_COL_FILTERS;

function loadColFilters(): ColFilters {
  try {
    const raw = localStorage.getItem(COL_FILTERS_KEY);
    if (raw) return { ...DEFAULT_COL_FILTERS, ...JSON.parse(raw) };
  } catch { /* ignore */ }
  return { ...DEFAULT_COL_FILTERS };
}

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
  {
    name: 'CMF Accumulation',
    emoji: '💰',
    desc: 'Smart money flowing in — CMF > 0.1, rising',
    filters: { min_cmf: 0.1, cmf_rising: true, sma_200_cross: 'ABOVE' as const },
  },
  {
    name: 'StochRSI Xover',
    emoji: '📈',
    desc: 'StochRSI bullish crossover from oversold within 3 days',
    filters: { stochrsi_bullish_xover_max_days: 3, sma_200_cross: 'ABOVE' as const },
  },
];

// Helper matchers for column-level filters
const matchTextFilter = (val: string | null | undefined, filterStr: string): boolean => {
  if (!filterStr.trim()) return true;
  if (!val) return false;
  return val.toLowerCase().includes(filterStr.toLowerCase().trim());
};

const matchNumericFilter = (val: number | null | undefined, filterStr: string): boolean => {
  if (!filterStr.trim()) return true;
  if (val === null || val === undefined) return false;
  
  const trimmed = filterStr.trim().toLowerCase();
  
  // check comparative prefix: >, <, >=, <=, = and optional suffixes
  const match = trimmed.match(/^([><]=?|=)?\s*([0-9.-]+)\s*(k|m|cr|crore|crores|l|la|lakh|lakhs)?$/);
  if (!match) {
    return String(val).toLowerCase().includes(trimmed);
  }
  
  const op = match[1] || '>='; // default to >= for numeric criteria
  let num = parseFloat(match[2]);
  if (isNaN(num)) return true;
  
  const multiplier = match[3];
  if (multiplier === 'k') {
    num *= 1000;
  } else if (multiplier === 'm') {
    num *= 1000000;
  } else if (multiplier === 'l' || multiplier === 'la' || multiplier === 'lakh' || multiplier === 'lakhs') {
    num *= 100000;
  } else if (multiplier === 'cr' || multiplier === 'crore' || multiplier === 'crores') {
    num *= 10000000;
  }
  
  switch (op) {
    case '>': return val > num;
    case '<': return val < num;
    case '>=': return val >= num;
    case '<=': return val <= num;
    case '=': return val === num;
    default: return val >= num;
  }
};

interface MultiSelectFilterProps {
  options: { value: string; label: string; className?: string }[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  minWidth?: string;
}

const MultiSelectFilter: React.FC<MultiSelectFilterProps> = ({
  options,
  value,
  onChange,
  placeholder = 'All',
  minWidth = '80px'
}) => {
  const [isOpen, setIsOpen] = React.useState(false);
  const containerRef = React.useRef<HTMLDivElement>(null);
  const selectedValues = React.useMemo(() => value ? value.split(',') : [], [value]);

  const toggleOption = (val: string) => {
    let newSelected: string[];
    if (selectedValues.includes(val)) {
      newSelected = selectedValues.filter(v => v !== val);
    } else {
      newSelected = [...selectedValues, val];
    }
    onChange(newSelected.join(','));
  };

  React.useEffect(() => {
    if (!isOpen) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  const displayLabel = React.useMemo(() => {
    if (selectedValues.length === 0) return placeholder;
    if (selectedValues.length === options.length) return 'All';
    return selectedValues
      .map(val => options.find(o => o.value === val)?.label || val)
      .join(', ');
  }, [selectedValues, options, placeholder]);

  return (
    <div className="relative inline-block w-full text-left" style={{ minWidth }} ref={containerRef}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-1.5 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-355 hover:text-text-main hover:border-slate-700 transition cursor-pointer select-none text-left font-mono h-[22px]"
      >
        <span className="truncate mr-1">{displayLabel}</span>
        <span className="text-[8px] text-slate-500">▼</span>
      </button>
      
      {isOpen && (
        <div className="absolute left-0 mt-1 z-50 min-w-[120px] rounded bg-slate-950 border border-slate-800 shadow-xl py-1 text-[10px] max-h-48 overflow-y-auto">
          {options.map(opt => {
            const isChecked = selectedValues.includes(opt.value);
            return (
              <label
                key={opt.value}
                className="flex items-center gap-2 px-2 py-1.5 hover:bg-slate-900 cursor-pointer select-none text-slate-300 hover:text-text-main"
              >
                <input
                  type="checkbox"
                  checked={isChecked}
                  onChange={() => toggleOption(opt.value)}
                  className="rounded border-slate-850 bg-slate-900 text-purple-600 focus:ring-0 focus:ring-offset-0 w-3 h-3 cursor-pointer"
                />
                <span className={opt.className}>{opt.label}</span>
              </label>
            );
          })}
          {selectedValues.length > 0 && (
            <div className="border-t border-slate-850/80 mt-1 pt-1 px-2 flex justify-end">
              <button
                type="button"
                onClick={() => onChange('')}
                className="text-[9px] text-purple-400 hover:text-purple-300 font-bold transition"
              >
                Clear
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export const ScreenerPanel: React.FC = () => {
  const {
    screenerResults,
    setScreenerFilters,
    runScreener,
    isLoading,
    setActiveTab,
    setSelectedSymbol,
    watchlists,
    activeWatchlistId,
    addToWatchlist,
  } = useStockStore();

  // Client-side sorting + pagination states
  const [sortField, setSortField] = useState<keyof ScreenerRow | null>(null);
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');
  const [visibleCount, setVisibleCount] = useState(50);
  const PAGE_SIZE = 50;
  const [searchQuery, setSearchQuery] = useState('');
  const [strategies, setStrategies] = useState<StrategyMeta[]>([]);

  const [modalSymbol, setModalSymbol] = useState<string | null>(null);

  const handleOpenChartModal = async (symbol: string) => {
    setModalSymbol(symbol);
    await setSelectedSymbol(symbol);
  };

  // Column-level filters state (cached in localStorage so they persist across reloads).
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

  useEffect(() => { runScreener(); }, []);
  // Load the registered strategies once for the per-strategy signal chips (stable column order).
  useEffect(() => { apiService.getStrategies().then(setStrategies).catch(() => setStrategies([])); }, []);
  // Reset to first page whenever results, search query, or column filters update
  useEffect(() => { setVisibleCount(PAGE_SIZE); }, [screenerResults, searchQuery, colFilters]);



  // Navigate in-place to the Explorer Dashboard for the selected symbol
  const handleSelectScreenerMatch = async (symbol: string) => {
    await setSelectedSymbol(symbol);
    setActiveTab('explorer');
  };

  // Add ticker to the active watchlist (or the first one if none active)
  const handleAddToWatchlist = (symbol: string) => {
    const targetId = activeWatchlistId ?? watchlists[0]?.id;
    if (targetId) addToWatchlist(targetId, symbol);
  };

  const formatNumber = (val: number | null | undefined, decimals = 2) => {
    if (val === null || val === undefined) return '-';
    return Number(val).toFixed(decimals);
  };

  const formatTradedValue = (val: number | null | undefined) => {
    if (val === null || val === undefined) return '-';
    const cr = val / 1e7;
    if (cr >= 100) return `${cr.toFixed(0)} Cr`;
    if (cr >= 1) return `${cr.toFixed(2)} Cr`;
    const lakh = val / 1e5;
    return `${lakh.toFixed(1)} L`;
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
        if (!matchNumericFilter(row.trade_quality_score, colFilters.trade_quality_score)) return false;
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

        if (colFilters.ml2_signal) {
          const selected = colFilters.ml2_signal.split(',').filter(Boolean);
          if (selected.length > 0 && !selected.includes((row as any).ml2_signal || '')) return false;
        }
        if (!matchNumericFilter(row.days_since_ema9_ema20_bull, colFilters.days_since_ema9_ema20_bull)) return false;
        if (!matchNumericFilter(row.days_since_sma20_sma50_bull, colFilters.days_since_sma20_sma50_bull)) return false;
        if (!matchNumericFilter(row.days_since_macd_bull, colFilters.days_since_macd_bull)) return false;
        if (!matchNumericFilter(row.days_since_cmf_bull, colFilters.days_since_cmf_bull)) return false;
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
    if (screenerResults.length === 0) return;

    const headers = [
      'Ticker', 'Company Name', 'Last EOD Price', 'Change %',
      'Avg Val', 'Bias', '1W Return %', '2W Return %', '3W Return %', '4W Return %',
      'Stop Loss', 'Target 1', 'Target 2', 'Target 3', 'Upside %', 'R:R', 'TQS', 'Suggested Shares',
      'Vol Breakout Ratio', 'RSI (14)', 'CMF (20)', 'StochRSI K', 'StochRSI D',
      'SMA 20 Position', 'SMA 50 Position', 'SMA 200 Position', 'MACD Trend',
      'Heikin Ashi', 'Renko', 'Three Line Break', 'RS 1M', 'Patterns',
      'ML Signal', 'ML EV Score', 'ML Rank',
      'Days since EMA9/20 Bull', 'Days since SMA20/50 Bull', 'Days since MACD Bull', 'Days since CMF Bull',
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
        row.trade_quality_score ?? '',
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
        (row as any).ml2_signal ?? '',
        (row as any).ml2_ev_score ?? '',
        (row as any).ml2_rank ?? '',
        row.days_since_ema9_ema20_bull ?? '',
        row.days_since_sma20_sma50_bull ?? '',
        row.days_since_macd_bull ?? '',
        row.days_since_cmf_bull ?? '',
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
            className="flex items-center gap-2 px-4 py-2 bg-bg-surface/80 hover:bg-bg-surface disabled:opacity-40 disabled:cursor-not-allowed text-text-muted hover:text-text-main border border-border-subtle rounded-lg text-sm font-bold transition cursor-pointer"
            title="Export filtered results to CSV file"
          >
            <Download className="w-4 h-4" />
            Export CSV
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
                volume_breakout: undefined, min_avg_traded_value: undefined,
                only_nr7: undefined, only_inside_bar: undefined,
                only_gap_up: undefined, only_gap_down: undefined,
                min_rs_1m: undefined,
                min_cmf: undefined, max_cmf: undefined, cmf_rising: undefined, cmf_crossed_zero: undefined,
                min_stochrsi_k: undefined, max_stochrsi_k: undefined, stochrsi_bullish_xover_max_days: undefined,
                ema_ribbon_bull_max_days: undefined, golden_cross_max_days: undefined,
                macd_bull_xover_max_days: undefined, cmf_bull_xover_max_days: undefined,
                ...p.filters,
              });
              runScreener();
            }}
            disabled={isLoading}
            className="flex items-center gap-2 px-3 py-2 rounded-xl border border-border-subtle bg-bg-surface/30 hover:bg-bg-surface/70 hover:border-accent-primary/40 disabled:opacity-40 transition cursor-pointer text-left"
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

      {/* Results Grid Table */}
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
            
            /* Pinned Columns logic (first column: Ticker, second column: Company) */
            .screener-grid th:nth-child(1),
            .screener-grid td:nth-child(1) {
              position: sticky;
              left: 0;
              z-index: 5;
              width: 90px;
              min-width: 90px;
              max-width: 90px;
              border-right: 1px solid rgba(51, 65, 85, 0.4);
            }
            .screener-grid th:nth-child(2),
            .screener-grid td:nth-child(2) {
              position: sticky;
              left: 90px;
              z-index: 5;
              width: 140px;
              min-width: 140px;
              max-width: 140px;
              border-right: 2px solid rgba(139, 92, 246, 0.4); /* Highlight end of pinned columns */
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
            .screener-grid thead th:nth-child(47) { z-index: 25; background-color: var(--bg-surface) !important; }
            .screener-grid thead tr:nth-child(2) td:nth-child(1) { z-index: 25; background-color: var(--bg-surface) !important; }
            .screener-grid thead tr:nth-child(2) td:nth-child(2) { z-index: 25; background-color: var(--bg-surface) !important; }
            .screener-grid thead tr:nth-child(2) td:nth-child(47) { z-index: 25; background-color: var(--bg-surface) !important; }

            /* Zebra striping backgrounds for scrollable cells */
            .screener-grid tbody tr:nth-child(odd) td {
              background-color: var(--bg-base);
            }
            .screener-grid tbody tr:nth-child(even) td {
              background-color: var(--bg-surface);
            }

            /* Pinned cell backgrounds (left columns) */
            .screener-grid tbody tr:nth-child(odd) td:nth-child(1),
            .screener-grid tbody tr:nth-child(odd) td:nth-child(2) {
              background-color: var(--bg-base) !important;
            }
            .screener-grid tbody tr:nth-child(even) td:nth-child(1),
            .screener-grid tbody tr:nth-child(even) td:nth-child(2) {
              background-color: var(--bg-surface) !important;
            }

            /* Pinned cell backgrounds (right Actions column) */
            .screener-grid tbody tr:nth-child(odd) td:nth-child(47) {
              background-color: var(--bg-base) !important;
            }
            .screener-grid tbody tr:nth-child(even) td:nth-child(47) {
              background-color: var(--bg-surface) !important;
            }

            /* Row hovers */
            .screener-grid tbody tr:hover td {
              background-color: rgba(139, 92, 246, 0.15) !important;
            }

            /* Column widths for other cells */
            .screener-grid th:nth-child(3), .screener-grid td:nth-child(3) { width: 100px; min-width: 100px; } /* Price */
            .screener-grid th:nth-child(4), .screener-grid td:nth-child(4) { width: 85px; min-width: 85px; } /* Chg% */
            .screener-grid th:nth-child(5), .screener-grid td:nth-child(5) { width: 105px; min-width: 105px; } /* Avg Vol */
            .screener-grid th:nth-child(6), .screener-grid td:nth-child(6) { width: 95px; min-width: 95px; } /* Bias */
            .screener-grid th:nth-child(7), .screener-grid td:nth-child(7),
            .screener-grid th:nth-child(8), .screener-grid td:nth-child(8),
            .screener-grid th:nth-child(9), .screener-grid td:nth-child(9),
            .screener-grid th:nth-child(10), .screener-grid td:nth-child(10) { width: 75px; min-width: 75px; } /* 1W-4W */
            .screener-grid th:nth-child(11), .screener-grid td:nth-child(11),
            .screener-grid th:nth-child(12), .screener-grid td:nth-child(12),
            .screener-grid th:nth-child(13), .screener-grid td:nth-child(13),
            .screener-grid th:nth-child(14), .screener-grid td:nth-child(14) { width: 95px; min-width: 95px; } /* Stop/T1/T2/T3 */
            .screener-grid th:nth-child(15), .screener-grid td:nth-child(15) { width: 90px; min-width: 90px; } /* Upside */
            .screener-grid th:nth-child(16), .screener-grid td:nth-child(16) { width: 75px; min-width: 75px; } /* R:R */
            .screener-grid th:nth-child(17), .screener-grid td:nth-child(17) { width: 80px; min-width: 80px; } /* TQS */
            .screener-grid th:nth-child(18), .screener-grid td:nth-child(18) { width: 100px; min-width: 100px; } /* Shares */
            .screener-grid th:nth-child(19), .screener-grid td:nth-child(19) { width: 90px; min-width: 90px; } /* Vol Brk */
            .screener-grid th:nth-child(20), .screener-grid td:nth-child(20) { width: 85px; min-width: 85px; } /* RSI */
            .screener-grid th:nth-child(21), .screener-grid td:nth-child(21) { width: 75px; min-width: 75px; } /* CMF */
            .screener-grid th:nth-child(22), .screener-grid td:nth-child(22) { width: 65px; min-width: 65px; } /* StoK */
            .screener-grid th:nth-child(23), .screener-grid td:nth-child(23) { width: 65px; min-width: 65px; } /* StoD */
            .screener-grid th:nth-child(24), .screener-grid td:nth-child(24),
            .screener-grid th:nth-child(25), .screener-grid td:nth-child(25),
            .screener-grid th:nth-child(26), .screener-grid td:nth-child(26),
            .screener-grid th:nth-child(27), .screener-grid td:nth-child(27),
            .screener-grid th:nth-child(28), .screener-grid td:nth-child(28),
            .screener-grid th:nth-child(29), .screener-grid td:nth-child(29),
            .screener-grid th:nth-child(30), .screener-grid td:nth-child(30) { width: 70px; min-width: 70px; } /* Averages & Technicals */
            .screener-grid th:nth-child(31), .screener-grid td:nth-child(31) { width: 90px; min-width: 90px; } /* RS 1M */
            .screener-grid th:nth-child(32), .screener-grid td:nth-child(32) { width: 150px; min-width: 150px; } /* Patterns */
            .screener-grid th:nth-child(33), .screener-grid td:nth-child(33) { width: 120px; min-width: 120px; } /* ML Signal */
            .screener-grid th:nth-child(34), .screener-grid td:nth-child(34) { width: 72px; min-width: 72px; } /* EMA Ribbon */
            .screener-grid th:nth-child(35), .screener-grid td:nth-child(35) { width: 68px; min-width: 68px; } /* Golden-X */
            .screener-grid th:nth-child(36), .screener-grid td:nth-child(36) { width: 72px; min-width: 72px; } /* MACD-X */
            .screener-grid th:nth-child(37), .screener-grid td:nth-child(37) { width: 68px; min-width: 68px; } /* CMF-X */
            /* Fundamental columns */
            .screener-grid th:nth-child(38), .screener-grid td:nth-child(38) { width: 110px; min-width: 110px; } /* Mkt Cap */
            .screener-grid th:nth-child(39), .screener-grid td:nth-child(39) { width: 70px; min-width: 70px; }  /* P/E */
            .screener-grid th:nth-child(40), .screener-grid td:nth-child(40) { width: 70px; min-width: 70px; }  /* P/B */
            .screener-grid th:nth-child(41), .screener-grid td:nth-child(41) { width: 90px; min-width: 90px; }  /* EV/EBITDA */
            .screener-grid th:nth-child(42), .screener-grid td:nth-child(42) { width: 75px; min-width: 75px; }  /* ROE */
            .screener-grid th:nth-child(43), .screener-grid td:nth-child(43) { width: 70px; min-width: 70px; }  /* D/E */
            .screener-grid th:nth-child(44), .screener-grid td:nth-child(44) { width: 85px; min-width: 85px; }  /* Net Mgn */
            .screener-grid th:nth-child(45), .screener-grid td:nth-child(45) { width: 75px; min-width: 75px; }  /* EPS */
            .screener-grid th:nth-child(46), .screener-grid td:nth-child(46) { width: 140px; min-width: 140px; } /* Sector */

            /* Pin Actions column (47th column) to the right */
            .screener-grid th:nth-child(47),
            .screener-grid td:nth-child(47) {
              position: sticky;
              right: 0;
              z-index: 5;
              width: 120px;
              min-width: 120px;
              max-width: 120px;
              border-left: 2px solid rgba(139, 92, 246, 0.4) !important;
              border-right: none;
              box-shadow: -4px 0 8px -3px rgba(0, 0, 0, 0.6);
            }

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
                <th className="py-2 px-1 text-right cursor-pointer hover:text-text-main transition" title="Trade Quality Score (0–100): Trend + Momentum + RS + Volume + R:R" onClick={() => handleSort('trade_quality_score' as any)}>
                  TQS {renderSortIcon('trade_quality_score' as any)}
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
                <th className="py-2 px-1.5 text-center cursor-pointer hover:text-text-main transition" title="VajraML2 triple-barrier signal (EV rank)" onClick={() => handleSort('ml2_rank' as any)}>
                  ML Signal {renderSortIcon('ml2_rank' as any)}
                </th>
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
                <th className="py-2 px-1.5 text-right">Actions</th>
              </tr>
              {showColFilters && (
                <tr className="border-b border-border-subtle bg-bg-base/40 whitespace-nowrap filter-row">
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
                      value={colFilters.trade_quality_score}
                      onChange={(e) => setColFilters({ ...colFilters, trade_quality_score: e.target.value })}
                      className="w-full min-w-[40px] px-1 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-300 placeholder-slate-650 focus:outline-none focus:border-purple-500 focus:text-text-main text-right transition font-mono"
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

                  {/* ML Signal */}
                  <td className="py-1 px-1.5 text-center">
                    <MultiSelectFilter
                      value={colFilters.ml2_signal}
                      onChange={(val) => setColFilters({ ...colFilters, ml2_signal: val })}
                      placeholder="All"
                      minWidth="80px"
                      options={[
                        { value: 'Strong Buy',   label: 'Strong Buy',   className: 'text-emerald-300 font-bold' },
                        { value: 'Buy',          label: 'Buy',          className: 'text-emerald-500' },
                        { value: 'Watch',        label: 'Watch',        className: 'text-amber-400' },
                        { value: 'Avoid',        label: 'Avoid',        className: 'text-slate-500' },
                        { value: 'Market Risk',  label: 'Market Risk',  className: 'text-rose-400 font-bold' },
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

                  {/* Actions */}
                  <td className="py-1 px-1.5 text-right">
                    {/* Empty space matching actions column */}
                  </td>
                </tr>
              )}
            </thead>
            <tbody className="divide-y divide-slate-850">
              {filteredResults.length === 0 ? (
                <tr>
                  <td colSpan={47} className="py-10 text-center text-slate-500 text-xs">
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
                      <td className="py-2 px-1.5 font-bold text-text-main font-mono">
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

                      {/* Avg Traded Value */}
                      <td className="py-2 px-1.5 text-right font-mono text-slate-350">
                        {formatTradedValue(row.avg_traded_value)}
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
                              ? 'text-indigo-400 bg-bg-surface'
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

                      {/* CMF */}
                      <td className="py-2 px-1.5 text-center">
                        {row.cmf_20 != null ? (
                          <span className={`font-mono inline-block px-1 py-0.2 rounded text-xs border ${
                            row.cmf_20 >= 0.1
                              ? 'text-emerald-400 bg-emerald-950/20 border-emerald-900/30 font-bold'
                              : row.cmf_20 <= -0.1
                              ? 'text-rose-400 bg-rose-950/20 border-rose-900/30 font-bold'
                              : 'text-slate-300 bg-slate-900/50 border-slate-800'
                          }`} title={`CMF: ${row.cmf_20.toFixed(3)}${row.cmf_crossed_above_zero ? ' · Crossed Zero' : ''}`}>
                            {row.cmf_20.toFixed(2)}
                          </span>
                        ) : <span className="text-slate-600">—</span>}
                      </td>

                      {/* StochRSI K */}
                      <td className="py-2 px-1.5 text-center">
                        {row.stochrsi_k != null ? (
                          <span className={`font-mono inline-block px-1 py-0.2 rounded text-xs border ${
                            row.stochrsi_k >= 80
                              ? 'text-rose-400 bg-rose-950/20 border-rose-900/30 font-bold'
                              : row.stochrsi_k <= 20
                              ? 'text-emerald-400 bg-emerald-950/20 border-emerald-900/30 font-bold'
                              : 'text-slate-300 bg-slate-900/50 border-slate-800'
                          }`} title={`StochRSI K: ${row.stochrsi_k.toFixed(1)} · Zone: ${row.stochrsi_zone ?? '—'}`}>
                            {row.stochrsi_k.toFixed(0)}
                          </span>
                        ) : <span className="text-slate-600">—</span>}
                      </td>

                      {/* StochRSI D */}
                      <td className="py-2 px-1.5 text-center">
                        {row.stochrsi_d != null ? (
                          <span className="font-mono text-slate-300 text-xs">{row.stochrsi_d.toFixed(0)}</span>
                        ) : <span className="text-slate-600">—</span>}
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
                        {/* Per-strategy signals (Buy / Watch / Sell; Near-miss shows score) */}
                        {strategies.length > 0 && row.strategy_signals && (
                          <div className="flex flex-wrap gap-0.5 justify-center mt-1 pt-1 border-t border-slate-850">
                            {strategies.map(st => {
                              const cell = row.strategy_signals?.[st.id];
                              const sig = cell?.signal ?? 'NONE';
                              const label = sig === 'NONE'
                                ? (cell?.score != null ? String(Math.round(cell.score)) : '·')
                                : stratCode(st.name);
                              return (
                                <span
                                  key={st.id}
                                  title={`${st.name}: ${sig === 'NONE' ? 'Near-miss' : sig}${cell?.score != null ? ` · score ${cell.score}` : ''}`}
                                  className={`text-[8px] font-bold px-1 py-0.5 rounded border leading-none ${STRAT_SIG_STYLE[sig]}`}
                                >
                                  {label}
                                </span>
                              );
                            })}
                          </div>
                        )}
                      </td>

                      {/* ML Signal (VajraML2) */}
                      <td className="py-2 px-1.5 text-center">
                        {(() => {
                          const sig  = (row as any).ml2_signal as string | null | undefined;
                          const rank = (row as any).ml2_rank as number | null | undefined;
                          const ptp  = (row as any).ml2_p_tp as number | null | undefined;
                          if (!sig) return <span className="text-slate-600 text-xs">—</span>;
                          const cfg: Record<string, { bg: string; text: string }> = {
                            'Strong Buy':  { bg: 'bg-emerald-500/20 border-emerald-400/50', text: 'text-emerald-200' },
                            'Buy':         { bg: 'bg-teal-500/15 border-teal-400/40',       text: 'text-teal-300'   },
                            'Watch':       { bg: 'bg-amber-500/15 border-amber-400/40',     text: 'text-amber-300'  },
                            'Avoid':       { bg: 'bg-slate-700/40 border-slate-600/40',     text: 'text-slate-400'  },
                            'Market Risk': { bg: 'bg-rose-500/20 border-rose-400/50',       text: 'text-rose-200'   },
                          };
                          const c = cfg[sig] ?? cfg['Avoid'];
                          return (
                            <span
                              title={`ML2 EV Rank: ${rank ?? '—'} | P(TP): ${ptp != null ? (ptp * 100).toFixed(1) + '%' : '—'}`}
                              className={`inline-flex flex-col items-center gap-0 px-1.5 py-0.5 rounded border text-[10px] font-bold whitespace-nowrap ${c.bg} ${c.text}`}
                            >
                              {sig}
                              {rank != null && (
                                <span className="opacity-60 font-mono text-[9px] font-normal">#{rank}</span>
                              )}
                            </span>
                          );
                        })()}
                      </td>

                      {/* EMA Ribbon crossover */}
                      <td className="py-2 px-1.5 text-center">
                        {row.days_since_ema9_ema20_bull != null ? (
                          <span className={`font-mono text-xs px-1 py-0.5 rounded border ${
                            row.days_since_ema9_ema20_bull <= 3
                              ? 'text-emerald-300 bg-emerald-950/30 border-emerald-700/40 font-bold'
                              : row.days_since_ema9_ema20_bull <= 7
                              ? 'text-teal-400 bg-teal-950/20 border-teal-800/30'
                              : 'text-slate-500 bg-slate-900/30 border-slate-800/30'
                          }`} title={`EMA9 crossed above EMA20: ${row.days_since_ema9_ema20_bull}d ago${row.ema9_ema20_spread != null ? ` · spread ${row.ema9_ema20_spread.toFixed(2)}%` : ''}`}>
                            {row.days_since_ema9_ema20_bull}d
                          </span>
                        ) : <span className="text-slate-700">—</span>}
                      </td>

                      {/* Golden Cross */}
                      <td className="py-2 px-1.5 text-center">
                        {row.days_since_sma20_sma50_bull != null ? (
                          <span className={`font-mono text-xs px-1 py-0.5 rounded border ${
                            row.days_since_sma20_sma50_bull <= 5
                              ? 'text-amber-300 bg-amber-950/30 border-amber-700/40 font-bold'
                              : row.days_since_sma20_sma50_bull <= 10
                              ? 'text-amber-500 bg-amber-950/15 border-amber-800/25'
                              : 'text-slate-500 bg-slate-900/30 border-slate-800/30'
                          }`} title={`SMA20 crossed above SMA50: ${row.days_since_sma20_sma50_bull}d ago`}>
                            {row.days_since_sma20_sma50_bull}d
                          </span>
                        ) : <span className="text-slate-700">—</span>}
                      </td>

                      {/* MACD crossover */}
                      <td className="py-2 px-1.5 text-center">
                        {row.days_since_macd_bull != null ? (
                          <span className={`font-mono text-xs px-1 py-0.5 rounded border ${
                            row.days_since_macd_bull <= 3
                              ? 'text-emerald-300 bg-emerald-950/30 border-emerald-700/40 font-bold'
                              : row.days_since_macd_bull <= 7
                              ? 'text-teal-400 bg-teal-950/20 border-teal-800/30'
                              : 'text-slate-500 bg-slate-900/30 border-slate-800/30'
                          }`} title={`MACD crossed above signal: ${row.days_since_macd_bull}d ago${row.macd_above_zero ? ' · MACD above zero ✓' : ''}${row.macd_histogram_slope != null ? ` · hist slope ${row.macd_histogram_slope > 0 ? '+' : ''}${row.macd_histogram_slope.toFixed(4)}` : ''}`}>
                            {row.days_since_macd_bull}d{row.macd_above_zero ? '↑' : ''}
                          </span>
                        ) : <span className="text-slate-700">—</span>}
                      </td>

                      {/* CMF crossover */}
                      <td className="py-2 px-1.5 text-center">
                        {row.days_since_cmf_bull != null ? (
                          <span className={`font-mono text-xs px-1 py-0.5 rounded border ${
                            row.days_since_cmf_bull <= 3
                              ? 'text-cyan-300 bg-cyan-950/30 border-cyan-700/40 font-bold'
                              : row.days_since_cmf_bull <= 7
                              ? 'text-cyan-500 bg-cyan-950/15 border-cyan-800/25'
                              : 'text-slate-500 bg-slate-900/30 border-slate-800/30'
                          }`} title={`CMF crossed above zero: ${row.days_since_cmf_bull}d ago${row.cmf_slope_5d != null ? ` · 5d slope ${row.cmf_slope_5d > 0 ? '+' : ''}${row.cmf_slope_5d.toFixed(3)}` : ''}`}>
                            {row.days_since_cmf_bull}d
                          </span>
                        ) : <span className="text-slate-700">—</span>}
                      </td>

                      {/* Mkt Cap */}
                      <td className="py-2 px-1.5 text-right font-mono text-xs text-slate-350">
                        {row.market_cap != null ? formatTradedValue(row.market_cap) : <span className="text-slate-700">—</span>}
                      </td>

                      {/* P/E */}
                      <td className="py-2 px-1.5 text-right font-mono text-xs">
                        {row.pe_ratio != null ? (
                          <span className={row.pe_ratio > 50 ? 'text-amber-400' : row.pe_ratio < 15 ? 'text-emerald-400' : 'text-slate-300'}>
                            {row.pe_ratio.toFixed(1)}
                          </span>
                        ) : <span className="text-slate-700">—</span>}
                      </td>

                      {/* P/B */}
                      <td className="py-2 px-1.5 text-right font-mono text-xs">
                        {row.pb_ratio != null ? (
                          <span className={row.pb_ratio > 5 ? 'text-amber-400' : 'text-slate-300'}>
                            {row.pb_ratio.toFixed(1)}
                          </span>
                        ) : <span className="text-slate-700">—</span>}
                      </td>

                      {/* EV/EBITDA */}
                      <td className="py-2 px-1.5 text-right font-mono text-xs">
                        {row.ev_ebitda != null ? (
                          <span className={row.ev_ebitda > 20 ? 'text-amber-400' : 'text-slate-300'}>
                            {row.ev_ebitda.toFixed(1)}x
                          </span>
                        ) : <span className="text-slate-700">—</span>}
                      </td>

                      {/* ROE */}
                      <td className="py-2 px-1.5 text-right font-mono text-xs">
                        {row.roe != null ? (
                          <span className={row.roe >= 0.20 ? 'text-emerald-400' : row.roe >= 0.10 ? 'text-slate-300' : 'text-rose-400'}>
                            {(row.roe * 100).toFixed(1)}%
                          </span>
                        ) : <span className="text-slate-700">—</span>}
                      </td>

                      {/* D/E */}
                      <td className="py-2 px-1.5 text-right font-mono text-xs">
                        {row.debt_to_equity != null ? (
                          <span className={row.debt_to_equity > 1 ? 'text-amber-400' : row.debt_to_equity > 0.5 ? 'text-slate-300' : 'text-emerald-400'}>
                            {row.debt_to_equity.toFixed(2)}
                          </span>
                        ) : <span className="text-slate-700">—</span>}
                      </td>

                      {/* Net Margin */}
                      <td className="py-2 px-1.5 text-right font-mono text-xs">
                        {row.profit_margin != null ? (
                          <span className={row.profit_margin >= 0.15 ? 'text-emerald-400' : row.profit_margin >= 0.05 ? 'text-slate-300' : row.profit_margin < 0 ? 'text-rose-400' : 'text-slate-400'}>
                            {(row.profit_margin * 100).toFixed(1)}%
                          </span>
                        ) : <span className="text-slate-700">—</span>}
                      </td>

                      {/* EPS */}
                      <td className="py-2 px-1.5 text-right font-mono text-xs">
                        {row.eps_ttm != null ? (
                          <span className={row.eps_ttm > 0 ? 'text-slate-300' : 'text-rose-400'}>
                            ₹{row.eps_ttm.toFixed(1)}
                          </span>
                        ) : <span className="text-slate-700">—</span>}
                      </td>

                      {/* Sector */}
                      <td className="py-2 px-1.5 text-xs text-slate-400 truncate max-w-[140px]" title={row.sector ?? undefined}>
                        {row.sector ?? <span className="text-slate-700">—</span>}
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
                            className="p-0.5 px-1.5 rounded bg-slate-900 border border-slate-800 hover:border-purple-500/80 text-slate-400 hover:text-text-main text-xs flex items-center gap-1 transition cursor-pointer"
                          >
                            <Eye className="w-3 h-3" />
                            Inspect
                          </button>
                          <button
                            onClick={() => handleOpenChartModal(row.symbol)}
                            title="Quick Chart View"
                            className="p-0.5 px-1.5 rounded bg-slate-900 border border-slate-800 hover:border-indigo-500/80 text-slate-400 hover:text-text-main text-xs flex items-center gap-1 transition cursor-pointer"
                          >
                            <TrendingUp className="w-3 h-3" />
                            Chart
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
      {/* ── Modal Stock Chart ── */}
      {modalSymbol && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-md flex items-center justify-center z-50 p-4 animate-in fade-in duration-200">
          <div className="w-full max-w-6xl bg-bg-surface border border-border-subtle rounded-2xl shadow-2xl flex flex-col max-h-[95vh] overflow-hidden animate-in zoom-in-95 duration-200">
            <div className="flex-1 flex flex-col p-6 overflow-y-auto">
              <StockChartWorkspace
                onClose={() => setModalSymbol(null)}
                hideWatchlistButton={true}
              />
            </div>
          </div>
        </div>
      )}
        </div>
      </div>
    </div>
  );
};
