import React, { useEffect, useRef, useState } from 'react';
import { createChart, LineSeries } from 'lightweight-charts';
import { useStockStore } from '../store/useStockStore';
import { apiService } from '../services/api';
import type { CandleData } from '../services/api';
import { TrendingUp, X, Plus, RefreshCw } from 'lucide-react';

const COLORS = ['#a855f7', '#22d3ee', '#f59e0b', '#10b981'];

interface CompareSeries {
  symbol: string;
  candles: CandleData[];
  loading: boolean;
  error: string | null;
}

export const ComparePanel: React.FC = () => {
  const { symbols } = useStockStore();
  const [series, setSeries] = useState<CompareSeries[]>([]);
  const [inputVal, setInputVal] = useState('');
  const [timeframe, setTimeframe] = useState<'1M' | '3M' | '6M' | '1Y'>('3M');
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstanceRef = useRef<any>(null);

  // ── Add a ticker ──────────────────────────────────────────────────────────
  const addTicker = async (raw: string) => {
    const sym = raw.trim().toUpperCase();
    if (!sym) return;
    const fullSym = sym.endsWith('.NS') || sym.startsWith('^') ? sym : `${sym}.NS`;
    if (series.find(s => s.symbol === fullSym) || series.length >= 4) return;

    setSeries(prev => [...prev, { symbol: fullSym, candles: [], loading: true, error: null }]);
    setInputVal('');

    try {
      const candles = await apiService.getCandles(fullSym);
      setSeries(prev => prev.map(s => s.symbol === fullSym ? { ...s, candles, loading: false } : s));
    } catch {
      setSeries(prev => prev.map(s => s.symbol === fullSym ? { ...s, loading: false, error: 'Not found' } : s));
    }
  };

  const removeTicker = (sym: string) => setSeries(prev => prev.filter(s => s.symbol !== sym));

  // ── Build/rebuild chart whenever series or timeframe changes ─────────────
  useEffect(() => {
    if (!chartRef.current) return;

    if (chartInstanceRef.current) {
      chartInstanceRef.current.remove();
      chartInstanceRef.current = null;
    }

    const ready = series.filter(s => s.candles.length > 0);
    if (ready.length === 0) return;

    // Date cutoff
    const daysMap = { '1M': 30, '3M': 90, '6M': 180, '1Y': 365 };
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - daysMap[timeframe]);
    const cutStr = cutoff.toISOString().split('T')[0];

    const chart = createChart(chartRef.current, {
      width: chartRef.current.clientWidth,
      height: 420,
      layout: { background: { color: '#101217' }, textColor: '#9ca3af', fontSize: 11 },
      grid: { vertLines: { color: '#1e222d' }, horzLines: { color: '#1e222d' } },
      crosshair: { vertLine: { color: 'rgba(168,85,247,0.4)' }, horzLine: { color: 'rgba(168,85,247,0.4)' } },
      timeScale: { borderColor: '#252a34', timeVisible: true },
      rightPriceScale: { borderColor: '#252a34' },
    } as any);

    chartInstanceRef.current = chart;

    for (let i = 0; i < ready.length; i++) {
      const s = ready[i];
      // Filter to timeframe window
      const filtered = s.candles.filter(c => c.time >= cutStr);
      if (filtered.length < 2) continue;

      // Normalise to 100 at start of window
      const base = filtered[0].close;
      const data = filtered.map(c => ({
        time: (() => {
          const [y, m, d] = c.time.split('-').map(Number);
          return Date.UTC(y, m - 1, d) / 1000;
        })() as any,
        value: (c.close / base) * 100,
      }));

      const lineSeries = chart.addSeries(LineSeries, {
        color: COLORS[i % COLORS.length],
        lineWidth: 2,
        title: s.symbol.replace('.NS', ''),
        priceLineVisible: false,
        lastValueVisible: true,
      });
      lineSeries.setData(data);
    }

    const handleResize = () => {
      if (chartRef.current && chartInstanceRef.current) {
        chartInstanceRef.current.resize(chartRef.current.clientWidth, 420);
      }
    };
    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
      if (chartInstanceRef.current) { chartInstanceRef.current.remove(); chartInstanceRef.current = null; }
    };
  }, [series, timeframe]);

  // Search suggestions
  const suggestions = inputVal.length >= 1
    ? symbols
        .filter(s =>
          s.symbol.replace('.NS', '').toLowerCase().startsWith(inputVal.toLowerCase()) ||
          s.company_name.toLowerCase().includes(inputVal.toLowerCase())
        )
        .slice(0, 6)
    : [];

  const returns = series
    .filter(s => s.candles.length > 0)
    .map(s => {
      const daysMap = { '1M': 30, '3M': 90, '6M': 180, '1Y': 365 };
      const cutoff = new Date(); cutoff.setDate(cutoff.getDate() - daysMap[timeframe]);
      const cutStr = cutoff.toISOString().split('T')[0];
      const filtered = s.candles.filter(c => c.time >= cutStr);
      if (filtered.length < 2) return { symbol: s.symbol, ret: null };
      const ret = (filtered[filtered.length - 1].close - filtered[0].close) / filtered[0].close * 100;
      return { symbol: s.symbol, ret };
    });

  return (
    <div className="flex-1 flex flex-col gap-4 p-5 overflow-y-auto max-h-full">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-purple-500" />
            Compare Stocks
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Add up to 4 tickers — normalised to 100 at start of window
          </p>
        </div>
        <div className="flex bg-slate-950/80 p-0.5 rounded-lg border border-slate-800">
          {(['1M', '3M', '6M', '1Y'] as const).map(tf => (
            <button
              key={tf}
              onClick={() => setTimeframe(tf)}
              className={`px-3 py-1.5 rounded-md text-[10px] font-bold transition cursor-pointer ${
                timeframe === tf ? 'bg-purple-600 text-white' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>

      {/* Ticker chips + add input */}
      <div className="flex flex-wrap items-center gap-2">
        {series.map((s, i) => (
          <div
            key={s.symbol}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-bold"
            style={{ borderColor: COLORS[i % COLORS.length] + '55', color: COLORS[i % COLORS.length], background: COLORS[i % COLORS.length] + '18' }}
          >
            {s.loading ? <RefreshCw className="w-3 h-3 animate-spin" /> : null}
            {s.symbol.replace('.NS', '')}
            {s.error && <span className="text-rose-400 ml-1">✕</span>}
            <button onClick={() => removeTicker(s.symbol)} className="hover:opacity-70 cursor-pointer ml-0.5">
              <X className="w-3 h-3" />
            </button>
          </div>
        ))}
        {series.length < 4 && (
          <div className="relative">
            <div className="flex items-center gap-1.5 bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5">
              <Plus className="w-3.5 h-3.5 text-slate-500" />
              <input
                value={inputVal}
                onChange={e => setInputVal(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') addTicker(inputVal); if (e.key === 'Escape') setInputVal(''); }}
                placeholder="Add ticker (e.g. TCS)…"
                className="text-xs bg-transparent text-text-main focus:outline-none w-36 placeholder-slate-600"
              />
            </div>
            {suggestions.length > 0 && (
              <div className="absolute top-full left-0 mt-1 w-64 bg-bg-surface border border-border-subtle rounded-xl shadow-2xl z-50 overflow-hidden">
                {suggestions.map(s => (
                  <button
                    key={s.symbol}
                    onClick={() => addTicker(s.symbol)}
                    className="w-full flex items-center gap-2 px-3 py-2 hover:bg-slate-800 text-left transition cursor-pointer"
                  >
                    <span className="text-xs font-bold text-text-main font-mono">{s.symbol.replace('.NS', '')}</span>
                    <span className="text-[11px] text-slate-400 truncate">{s.company_name}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Return badges */}
      {returns.length > 0 && (
        <div className="flex flex-wrap gap-3">
          {returns.map((r, i) => (
            <div key={r.symbol} className="flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-800 bg-bg-surface/40">
              <span className="w-2 h-2 rounded-full" style={{ background: COLORS[i % COLORS.length] }} />
              <span className="text-xs font-bold text-slate-300">{r.symbol.replace('.NS', '')}</span>
              <span className={`text-xs font-mono font-bold ${r.ret == null ? 'text-slate-500' : r.ret >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {r.ret == null ? '—' : `${r.ret >= 0 ? '+' : ''}${r.ret.toFixed(2)}%`}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Chart */}
      {series.some(s => s.candles.length > 0) ? (
        <div ref={chartRef} className="w-full rounded-xl overflow-hidden border border-slate-800/80 bg-[#101217]" />
      ) : (
        <div className="flex-1 flex flex-col items-center justify-center text-slate-500 py-20 gap-3">
          <TrendingUp className="w-14 h-14 text-slate-700" />
          <div className="text-center">
            <p className="font-semibold text-slate-400">Add tickers to compare</p>
            <p className="text-xs text-slate-500 mt-1">Type a symbol above and press Enter — up to 4 stocks</p>
          </div>
        </div>
      )}
    </div>
  );
};
