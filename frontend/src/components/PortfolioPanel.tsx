import React, { useEffect, useRef, useState } from 'react';
import { useStockStore } from '../store/useStockStore';
import {
  Upload, Trash2, TrendingUp, TrendingDown, Minus, BarChart2, ShieldAlert,
  Wallet, Gauge, PieChart, ArrowUpRight, ArrowDownRight, Sparkles, RefreshCw,
} from 'lucide-react';
import type { PortfolioHolding } from '../services/api';
import { StockChartWorkspace } from './StockChartWorkspace';

export const PortfolioPanel: React.FC = () => {
  const {
    portfolio, portfolioLoading, fetchPortfolio, importPortfolioFile, clearPortfolio,
    setSelectedSymbol, setActiveTab,
  } = useStockStore();

  useEffect(() => { fetchPortfolio(); }, [fetchPortfolio]);

  const holdings = portfolio?.holdings ?? [];
  const agg = portfolio?.aggregates ?? null;

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [modalSymbol, setModalSymbol] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) importPortfolioFile(file);
    e.target.value = '';
  };

  const handleInspect = async (instrument: string) => {
    const symbol = instrument.endsWith('.NS') ? instrument : `${instrument}.NS`;
    await setSelectedSymbol(symbol);
    setActiveTab('explorer');
  };

  const handleOpenChartModal = async (instrument: string) => {
    const symbol = instrument.endsWith('.NS') ? instrument : `${instrument}.NS`;
    setModalSymbol(symbol);
    await setSelectedSymbol(symbol);
  };

  // ── Formatters ───────────────────────────────────────────────────────────
  const fmt = (n: number, dec = 2) => n.toFixed(dec);
  const fmtINR = (n: number) =>
    new Intl.NumberFormat('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n);
  const fmtINR0 = (n: number) =>
    new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(n);
  const signed = (n: number, dec = 2) => `${n >= 0 ? '+' : ''}${fmt(n, dec)}`;
  const pnlText = (v: number) => (v >= 0 ? 'text-emerald-400' : 'text-rose-400');

  const biasChip = (bias: string | null) => {
    if (bias === 'VERY_BULLISH') return { c: 'text-emerald-200 bg-emerald-500/25 border-emerald-400/50', Icon: TrendingUp };
    if (bias === 'BULLISH')      return { c: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/25', Icon: TrendingUp };
    if (bias === 'VERY_BEARISH') return { c: 'text-rose-200 bg-rose-500/25 border-rose-400/50', Icon: TrendingDown };
    if (bias === 'BEARISH')      return { c: 'text-rose-400 bg-rose-500/10 border-rose-500/25', Icon: TrendingDown };
    return { c: 'text-slate-400 bg-slate-500/10 border-slate-600/30', Icon: Minus };
  };
  const biasAccent = (bias: string | null) => {
    if (bias === 'VERY_BULLISH') return 'bg-emerald-300';
    if (bias === 'BULLISH')      return 'bg-emerald-500';
    if (bias === 'VERY_BEARISH') return 'bg-rose-300';
    if (bias === 'BEARISH')      return 'bg-rose-500';
    return 'bg-slate-600';
  };
  const volText = (v: string | null) =>
    v === 'LOW' ? 'text-emerald-400' : v === 'HIGH' ? 'text-rose-400' : 'text-amber-400';

  const COLORS = [
    'bg-purple-500', 'bg-indigo-500', 'bg-blue-500', 'bg-cyan-500',
    'bg-teal-500', 'bg-emerald-500', 'bg-amber-500', 'bg-rose-500',
    'bg-fuchsia-500', 'bg-sky-500',
  ];

  // ── Header (always shown) ──────────────────────────────────────────────────
  const header = (
    <div className="flex items-center justify-between flex-wrap gap-3">
        <h2 className="text-2xl font-bold text-text-main tracking-tight flex items-center gap-2.5">
          <span className="p-1.5 rounded-lg bg-purple-600/15 border border-purple-500/30 text-purple-400">
            <Wallet className="w-5 h-5" />
          </span>
          Portfolio
        </h2>
      <div className="flex items-center gap-2">
        <input ref={fileInputRef} type="file" accept=".csv" className="hidden" onChange={handleFileChange} />
        <button
          onClick={() => fetchPortfolio()}
          disabled={portfolioLoading}
          title="Refresh"
          className="p-2.5 rounded-lg border border-slate-800 hover:bg-slate-800/60 text-slate-400 hover:text-text-main transition cursor-pointer"
        >
          <RefreshCw className={`w-4 h-4 ${portfolioLoading ? 'animate-spin' : ''}`} />
        </button>
        <button
          onClick={() => fileInputRef.current?.click()}
          className="flex items-center gap-2 px-4 py-2.5 bg-purple-600 hover:bg-purple-500 text-white rounded-lg text-sm font-bold transition cursor-pointer shadow-lg shadow-purple-900/30"
        >
          <Upload className="w-4 h-4" />
          Import CSV
        </button>
        {holdings.length > 0 && (
          <button
            onClick={clearPortfolio}
            title="Clear portfolio"
            className="p-2.5 rounded-lg bg-slate-800/60 hover:bg-rose-950/60 border border-slate-700 hover:border-rose-900 text-slate-400 hover:text-rose-400 transition cursor-pointer"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  );

  if (holdings.length === 0 || !agg) {
    return (
      <div className="flex-1 flex flex-col gap-6 p-6 overflow-y-auto max-h-full">
        {header}
        <div className="flex-1 flex flex-col items-center justify-center text-slate-500 py-20 gap-4">
          <div className="p-5 rounded-2xl bg-slate-900/40 border border-slate-800">
            <BarChart2 className="w-12 h-12 text-slate-700" />
          </div>
          <div className="text-center space-y-1.5">
            <p className="font-semibold text-slate-300">{portfolioLoading ? 'Loading portfolio…' : 'No portfolio loaded'}</p>
            <p className="text-xs text-slate-500 max-w-sm">
              Export your holdings from <span className="text-slate-400">Zerodha Console → Portfolio → Holdings → Download</span>, then import the CSV here.
            </p>
          </div>
          {!portfolioLoading && (
            <button
              onClick={() => fileInputRef.current?.click()}
              className="mt-1 px-5 py-2.5 bg-purple-600 hover:bg-purple-500 text-white rounded-xl text-sm font-bold transition cursor-pointer"
            >
              Import Zerodha CSV
            </button>
          )}
        </div>
      </div>
    );
  }

  const pnl = agg.include_charges ? agg.net_pnl : agg.total_pnl;
  const pnlUp = pnl >= 0;
  const openRiskPct = agg.total_current > 0 ? (agg.open_risk / agg.total_current) * 100 : 0;

  // Heat gauge scale (limit sits at ~62% of the track so the danger zone is visible)
  const heatScaleMax = Math.max(agg.heat_limit * 1.6, agg.heat_pct * 1.1, 1);
  const heatFill = Math.min((agg.heat_pct / heatScaleMax) * 100, 100);
  const limitPos = Math.min((agg.heat_limit / heatScaleMax) * 100, 100);
  const heatOver = agg.heat_pct > agg.heat_limit;
  const heatColor = heatOver ? 'bg-rose-500' : agg.heat_pct > agg.heat_limit * 0.75 ? 'bg-amber-500' : 'bg-emerald-500';

  const regimeStyle =
    agg.regime === 'BULL' ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30'
    : agg.regime === 'BEAR' ? 'text-rose-400 bg-rose-500/10 border-rose-500/30'
    : 'text-amber-400 bg-amber-500/10 border-amber-500/30';

  const allocation = [...holdings]
    .sort((a, b) => b.current_val - a.current_val)
    .map((h, i) => ({
      label: h.instrument,
      pct: agg.total_current > 0 ? (h.current_val / agg.total_current) * 100 : 0,
      color: COLORS[i % COLORS.length],
    }));

  const sectionLabel = (text: string, Icon: React.ElementType) => (
    <div className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-wider text-slate-500">
      <Icon className="w-3.5 h-3.5" /> {text}
    </div>
  );

  return (
    <div className="flex-1 flex flex-col gap-4 p-6 overflow-y-auto max-h-full">
      {header}

      {/* ── Hero: Value + Risk ─────────────────────────────────────────────── */}
      <div className="shrink-0 grid grid-cols-1 lg:grid-cols-3 gap-4">

        {/* Value hero */}
        <div className="lg:col-span-2 relative overflow-hidden rounded-2xl border border-border-subtle bg-gradient-to-br from-bg-surface via-bg-surface/90 to-bg-base/80 px-5 py-4">
          <div className="absolute -top-16 -right-10 w-48 h-48 bg-purple-600/10 blur-3xl rounded-full pointer-events-none" />
          <div className="relative flex items-center justify-between gap-6 h-full flex-wrap">
            {/* Value */}
            <div className="shrink-0">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Current Value</span>
              <div className="flex items-end gap-2.5 mt-1 flex-wrap">
                <span className="text-3xl font-extrabold text-text-main font-mono tracking-tight leading-none">₹{fmtINR0(agg.total_current)}</span>
                <span className={`flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded-lg border ${pnlUp ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/25' : 'text-rose-400 bg-rose-500/10 border-rose-500/25'}`}>
                  {pnlUp ? <ArrowUpRight className="w-3.5 h-3.5" /> : <ArrowDownRight className="w-3.5 h-3.5" />}
                  {signed(agg.total_return_pct)}%
                </span>
                <span className="flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded-lg border text-amber-400 bg-amber-500/10 border-amber-500/25" title="Open risk as % of portfolio value">
                  <ShieldAlert className="w-3 h-3" />
                  Risk {fmt(openRiskPct)}%
                </span>
              </div>
            </div>

            {/* Inline stats */}
            <div className="flex items-center gap-6 sm:gap-8 flex-wrap">
              {[
                { label: 'Invested', value: `₹${fmtINR0(agg.total_invested)}`, color: 'text-text-main' },
                { label: agg.include_charges ? 'Net P&L' : 'P&L', value: `${pnlUp ? '+' : ''}₹${fmtINR0(pnl)}`, sub: `${signed(agg.total_return_pct)}%`, color: pnlText(pnl) },
                { label: 'Positions', value: String(agg.positions), color: 'text-text-main' },
              ].map(({ label, value, color, sub }) => (
                <div key={label}>
                  <p className="text-[10px] uppercase tracking-wide text-slate-500">{label}</p>
                  <p className={`text-sm font-extrabold font-mono mt-0.5 ${color}`}>{value}</p>
                  {sub && <p className={`text-[10px] font-mono ${color} opacity-70`}>{sub}</p>}
                </div>
              ))}
              {/* Rolling alpha chips */}
              <div>
                <p className="text-[10px] uppercase tracking-wide text-slate-500 mb-1">Alpha vs NIFTY</p>
                <div className="flex items-center gap-1.5">
                  {([['1W', agg.alpha_1w], ['4W', agg.alpha_4w], ['3M', agg.alpha_3m]] as [string, number | null | undefined][]).map(([lbl, val]) => (
                    <span
                      key={lbl}
                      title={`${lbl} portfolio alpha vs NIFTY (portfolio return − benchmark return)`}
                      className={`px-1.5 py-0.5 rounded text-[10px] font-bold border ${
                        val == null
                          ? 'text-slate-500 bg-slate-800/30 border-slate-700/30'
                          : val >= 0
                          ? 'text-purple-300 bg-purple-900/15 border-purple-500/25'
                          : 'text-amber-400 bg-amber-900/15 border-amber-500/25'
                      }`}
                    >
                      {lbl} {val != null ? `${signed(val)}%` : '—'}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Risk & Regime */}
        <div className="rounded-2xl border border-border-subtle bg-bg-surface/50 px-4 py-3.5 flex flex-col gap-2.5">
          <div className="flex items-center justify-between">
            {sectionLabel('Risk & Regime', ShieldAlert)}
            <span className={`text-[11px] font-bold px-2 py-0.5 rounded-md border ${regimeStyle}`}>{agg.regime}</span>
          </div>

          {/* Heat gauge */}
          <div>
            <div className="flex items-end justify-between mb-1.5">
              <span className="text-xs text-slate-400 flex items-center gap-1.5"><Gauge className="w-3.5 h-3.5" /> Portfolio Heat</span>
              <span className={`text-sm font-mono font-bold ${heatOver ? 'text-rose-400' : 'text-emerald-400'}`}>
                {fmt(agg.heat_pct)}% <span className="text-[10px] text-slate-500 font-normal">/ {fmt(agg.heat_limit, 0)}%</span>
              </span>
            </div>
            <div className="relative h-2 bg-slate-900 rounded-full">
              <div className={`h-full rounded-full transition-all ${heatColor}`} style={{ width: `${heatFill}%` }} />
              <div className="absolute -top-0.5 -bottom-0.5 w-px bg-slate-400/70" style={{ left: `${limitPos}%` }} title={`${fmt(agg.heat_limit, 0)}% cap`} />
            </div>
            {heatOver && (
              <p className="text-[10px] text-rose-400 mt-1.5">Above {agg.regime.toLowerCase()}-market limit — pause new buys.</p>
            )}
          </div>

          {/* mini stats */}
          <div className="grid grid-cols-2 gap-2.5">
            <div className="rounded-lg bg-slate-900/40 border border-slate-800/60 px-2.5 py-2">
              <p className="text-[10px] uppercase tracking-wide text-slate-500">Open Risk</p>
              <p className="text-sm font-bold font-mono text-text-main mt-0.5">₹{fmtINR0(agg.open_risk)}</p>
              <p className="text-[10px] font-mono text-amber-400 mt-0.5">{fmt(openRiskPct)}% of portfolio</p>
            </div>
            <div className="rounded-lg bg-slate-900/40 border border-slate-800/60 px-2.5 py-2">
              <p className="text-[10px] uppercase tracking-wide text-slate-500">Breadth &gt;200d</p>
              <p className="text-sm font-bold font-mono text-text-main mt-0.5">{fmt(agg.breadth_pct, 0)}%</p>
            </div>
          </div>
        </div>
      </div>

      {/* ── Allocation ─────────────────────────────────────────────────────── */}
      <div className="shrink-0 rounded-2xl border border-border-subtle bg-bg-surface/40 px-5 py-3.5">
        <div className="flex items-center justify-between mb-3">
          {sectionLabel('Allocation by Value', PieChart)}
          {agg.clusters.length > 0 && (
            <span className="text-[10px] text-amber-400 flex items-center gap-1">
              <ShieldAlert className="w-3 h-3" />
              Concentration: {agg.clusters.map(c => `${c.instrument} ${c.weight_pct}%`).join(' · ')} (cap {fmt(agg.max_cluster_pct, 0)}%)
            </span>
          )}
        </div>
        <div className="flex h-3 rounded-full overflow-hidden gap-0.5">
          {allocation.map(bar => (
            <div key={bar.label} className={`${bar.color} transition-all`} style={{ width: `${bar.pct}%` }} title={`${bar.label}: ${bar.pct.toFixed(1)}%`} />
          ))}
        </div>
        <div className="flex flex-wrap gap-x-4 gap-y-1.5 mt-3">
          {allocation.map(bar => (
            <div key={bar.label} className="flex items-center gap-1.5 text-[11px] text-slate-400">
              <span className={`w-2 h-2 rounded-full ${bar.color}`} />
              {bar.label} <span className="text-slate-600 font-mono">{bar.pct.toFixed(1)}%</span>
            </div>
          ))}
        </div>
      </div>

      {/* ── Holdings table ─────────────────────────────────────────────────── */}
      <div className="shrink-0 rounded-2xl border border-border-subtle bg-bg-surface/50 overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-800/70">
          {sectionLabel('Holdings', BarChart2)}
          <span className="text-xs text-slate-500 font-mono">{holdings.length}</span>
        </div>
        <div className="overflow-auto">
          <table className="w-full border-collapse text-sm">
            <thead className="sticky top-0 z-10">
              <tr className="bg-bg-base text-[10px] text-text-muted uppercase tracking-wider font-semibold">
                <th className="py-2.5 pl-5 pr-3 text-left font-semibold">Instrument</th>
                <th className="py-2.5 px-3 text-right font-semibold">Qty</th>
                <th className="py-2.5 px-3 text-right font-semibold">Avg · LTP</th>
                <th className="py-2.5 px-3 text-right font-semibold">Cur. Value</th>
                <th className="py-2.5 px-3 text-right font-semibold">P&amp;L</th>
                <th className="py-2.5 px-3 text-right font-semibold">Return</th>
                <th className="py-2.5 px-2 text-right font-semibold" title="1-week return">1W</th>
                <th className="py-2.5 px-2 text-right font-semibold" title="2-week return">2W</th>
                <th className="py-2.5 px-2 text-right font-semibold" title="3-week return">3W</th>
                <th className="py-2.5 px-2 text-right font-semibold" title="4-week return">4W</th>
                <th className="py-2.5 px-3 text-center font-semibold">Bias</th>
                <th className="py-2.5 px-3 text-center font-semibold">MTF</th>
                <th className="py-2.5 px-3 text-right font-semibold">ATR%</th>
                <th className="py-2.5 px-3 text-right font-semibold">Risk · Stop</th>
                <th className="py-2.5 px-3 text-right font-semibold" title="ATR-based first target (close + 1.5×ATR) and % upside">Target 1</th>
                <th className="py-2.5 px-3 text-right font-semibold">R:R</th>
                <th className="py-2.5 px-3 text-right font-semibold">RS</th>
                <th className="py-2.5 px-3 text-right font-semibold" title="Composite score (trend + volume + RS + momentum + CMF + breakout, 0–100)">Score</th>
                <th className="py-2.5 pr-5 pl-3 text-center font-semibold"></th>
              </tr>
            </thead>
            <tbody>
              {holdings.map((h: PortfolioHolding) => {
                const bull = h.pnl >= 0;
                const { c: biasC, Icon: BiasIcon } = biasChip(h.bias);
                return (
                  <tr key={h.instrument} className={`border-t border-slate-800/50 hover:bg-slate-800/25 transition ${h.weak ? 'bg-amber-950/[0.07]' : ''}`}>
                    <td className="py-3 pl-0 pr-3">
                      <div className="flex items-stretch">
                        <span className={`w-1 rounded-full mr-3 ${biasAccent(h.bias)}`} />
                        <div className="flex items-center gap-1.5 py-0.5">
                          <span className="font-bold text-text-main font-mono tracking-wide">{h.instrument}</span>
                          {!h.matched && <span className="text-[9px] text-amber-500" title="Not in synced universe">⚠</span>}
                          {h.weak && (
                            <span className="text-[8px] font-bold px-1.5 py-0.5 rounded bg-amber-500/10 border border-amber-500/30 text-amber-400" title={h.weak_reason ?? ''}>
                              ROTATE
                            </span>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="py-3 px-3 text-right font-mono text-slate-300">{h.qty.toLocaleString('en-IN')}</td>
                    <td className="py-3 px-3 text-right font-mono text-slate-400 whitespace-nowrap">
                      ₹{fmtINR(h.avg_cost)}<span className="text-slate-600"> · </span>
                      <span className="text-text-main" title={h.ltp_source === 'imported' ? 'From CSV (not synced)' : 'Latest synced close'}>
                        ₹{fmtINR(h.ltp)}{h.ltp_source === 'imported' && <span className="text-[9px] text-amber-500">*</span>}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-right font-mono text-text-main">₹{fmtINR0(h.current_val)}</td>
                    <td className={`py-3 px-3 text-right font-mono font-semibold ${pnlText(h.pnl)}`}>
                      {bull ? '+' : ''}₹{fmtINR0(h.pnl)}
                    </td>
                    <td className={`py-3 px-3 text-right font-mono font-semibold ${pnlText(h.return_pct)}`}>
                      {signed(h.return_pct)}%
                    </td>
                    {[h.ret_1w, h.ret_2w, h.ret_3w, h.ret_4w].map((r, i) => (
                      <td key={i} className={`py-3 px-2 text-right font-mono text-xs ${r === null ? 'text-slate-600' : pnlText(r)}`}>
                        {r === null ? '—' : `${signed(r, 1)}%`}
                      </td>
                    ))}
                    <td className="py-3 px-3 text-center">
                      {h.bias ? (
                        <span className={`inline-flex items-center gap-0.5 text-[10px] font-bold px-1.5 py-0.5 rounded-md border ${biasC}`}>
                          <BiasIcon className="w-2.5 h-2.5" />{h.bias}
                        </span>
                      ) : <span className="text-slate-600">—</span>}
                    </td>
                    <td className="py-3 px-3 text-center">
                      {h.mtf_confirmed === null ? <span className="text-slate-600">—</span>
                        : h.mtf_confirmed
                          ? <span className="inline-flex w-5 h-5 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-400 text-xs" title="Daily bias confirmed by weekly trend">✓</span>
                          : <span className="inline-flex w-5 h-5 items-center justify-center rounded-full bg-slate-700/40 text-slate-500 text-xs" title={`Weekly trend: ${h.weekly_trend ?? 'n/a'}`}>✗</span>}
                    </td>
                    <td className={`py-3 px-3 text-right font-mono ${volText(h.vol_class)}`} title={h.vol_class ?? ''}>
                      {h.atr_pct !== null ? `${fmt(h.atr_pct)}%` : '—'}
                    </td>
                    <td className="py-3 px-3 text-right font-mono text-slate-300 whitespace-nowrap">
                      {h.open_risk !== null
                        ? <>
                            ₹{fmtINR0(h.open_risk)}
                            <span className="text-slate-600 text-[10px]"> @{fmtINR0(h.stop ?? 0)}</span>
                            {h.stop_type === 'supertrend' && (
                              <span className="ml-1 text-[8px] font-bold text-purple-400/80" title="Supertrend trailing stop">ST</span>
                            )}
                          </>
                        : '—'}
                    </td>
                    <td className="py-3 px-3 text-right font-mono text-slate-300 whitespace-nowrap">
                      {h.target_1 !== null
                        ? <div className="flex flex-col items-end gap-0.5">
                            <span>T1 ₹{fmtINR0(h.target_1)}<span className="text-emerald-400/80 text-[10px]"> +{fmt(h.potential_gain_pct ?? 0, 1)}%</span></span>
                            {h.target_2 != null && <span className="text-emerald-400/60 text-[10px]">T2 ₹{fmtINR0(h.target_2)}</span>}
                            {h.target_3 != null && <span className="text-emerald-400/40 text-[10px]">T3 ₹{fmtINR0(h.target_3)}</span>}
                            {h.position_size_shares != null && <span className="text-purple-400 text-[10px]">{h.position_size_shares.toLocaleString('en-IN')} sh</span>}
                          </div>
                        : '—'}
                    </td>
                    <td className="py-3 px-3 text-right font-mono text-xs">
                      {h.rr_ratio !== undefined && h.rr_ratio !== null ? (
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                          h.rr_ratio >= 2.0 
                            ? 'text-emerald-400 bg-emerald-950/20' 
                            : h.rr_ratio >= 1.0 
                            ? 'text-indigo-400 bg-bg-surface' 
                            : 'text-rose-400 bg-rose-950/20'
                        }`}>
                          {h.rr_ratio.toFixed(2)}x
                        </span>
                      ) : '—'}
                    </td>
                    <td className={`py-3 px-3 text-right font-mono ${h.rs_score_1m !== null && h.rs_score_1m >= 1 ? 'text-emerald-400' : 'text-slate-400'}`}>
                      {h.rs_score_1m !== null ? fmt(h.rs_score_1m) : '—'}
                    </td>
                    <td className="py-3 px-3 text-right">
                      {h.composite_score != null ? (
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                          h.composite_score >= 65 ? 'text-emerald-400 bg-emerald-950/20'
                          : h.composite_score >= 40 ? 'text-amber-400 bg-amber-950/20'
                          : 'text-rose-400 bg-rose-950/20'
                        }`}>
                          {h.composite_score.toFixed(0)}
                        </span>
                      ) : <span className="text-slate-600 text-xs">—</span>}
                    </td>
                    <td className="py-3 pr-5 pl-3 text-center">
                      <div className="flex items-center gap-1 justify-center">
                        <button
                          onClick={() => handleInspect(h.instrument)}
                          className="px-2 py-1 rounded bg-slate-900 border border-slate-800 hover:border-purple-500/80 text-slate-400 hover:text-text-main text-xs transition cursor-pointer"
                        >
                          View
                        </button>
                        <button
                          onClick={() => handleOpenChartModal(h.instrument)}
                          title="Quick Chart View"
                          className="p-1 px-1.5 rounded bg-slate-900 border border-slate-800 hover:border-indigo-500/80 text-slate-400 hover:text-text-main text-xs flex items-center gap-1 transition cursor-pointer"
                        >
                          <TrendingUp className="w-3 h-3" />
                          Chart
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="text-[10px] text-slate-600 px-5 py-3 border-t border-slate-800/50">
          <span className="text-amber-500">*</span> LTP from CSV (symbol not synced). Bias, MTF and risk are computed server-side from synced EOD data.
        </p>
      </div>

      {/* ── Rotation candidates ────────────────────────────────────────────── */}
      <div className="shrink-0 rounded-2xl border border-border-subtle bg-bg-surface/40 p-5">
        <div className="flex items-center justify-between mb-1">
          {sectionLabel('Rotation Candidates', Sparkles)}
          {agg.weak_holdings.length > 0 && (
            <span className="text-[10px] text-amber-400">
              {agg.weak_holdings.length} weak position{agg.weak_holdings.length > 1 ? 's' : ''}: {agg.weak_holdings.join(', ')}
            </span>
          )}
        </div>
        <p className="text-[11px] text-slate-500 mb-4">
          Strong bullish, weekly-confirmed names you don't hold (non-high-volatility), ranked by momentum — to rotate weak positions into.
        </p>
        {agg.replacement_candidates.length === 0 ? (
          <p className="text-xs text-slate-600 py-6 text-center">
            No qualifying candidates right now — the broad market regime is {agg.regime.toLowerCase()}.
          </p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {agg.replacement_candidates.map((c, i) => (
              <button
                key={c.symbol}
                onClick={() => handleInspect(c.symbol)}
                className="group text-left p-3.5 rounded-xl bg-slate-900/40 border border-slate-800/70 hover:border-emerald-500/40 hover:bg-emerald-950/10 transition cursor-pointer"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono text-slate-600">#{i + 1}</span>
                    <span className="text-sm font-bold text-text-main font-mono group-hover:text-emerald-300 transition">{c.symbol}</span>
                  </div>
                  <div className="flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
                    <button
                      onClick={() => handleOpenChartModal(c.symbol)}
                      title="Quick Chart View"
                      className="p-1 rounded bg-slate-955 border border-slate-800 hover:border-indigo-500/80 text-slate-400 hover:text-text-main transition cursor-pointer"
                    >
                      <TrendingUp className="w-3 h-3" />
                    </button>
                    <span className="text-[9px] font-bold px-1.5 py-0.5 rounded border text-emerald-400 bg-emerald-500/10 border-emerald-500/25">
                      {c.bias}
                    </span>
                  </div>
                </div>
                <p className="text-[10px] text-slate-500 truncate mt-1">{c.company_name}</p>
                <div className="flex items-center gap-3 mt-2.5 text-[10px] font-mono text-slate-400">
                  <span className="text-text-main">₹{fmtINR0(c.close_price)}</span>
                  {c.rsi_14 !== null && <span>RSI {c.rsi_14}</span>}
                  {c.atr_pct !== null && <span className={volText(c.vol_class)}>ATR {fmt(c.atr_pct)}%</span>}
                  <span className="ml-auto text-emerald-400/70 flex items-center gap-0.5"><TrendingUp className="w-3 h-3" />{c.weekly_trend}</span>
                </div>

                {/* Weekly returns */}
                <div className="flex items-center gap-2 mt-2 text-[10px] font-mono">
                  {([['1W', c.ret_1w], ['2W', c.ret_2w], ['3W', c.ret_3w], ['4W', c.ret_4w]] as const).map(([lbl, r]) => (
                    <span key={lbl} className="flex flex-col items-center">
                      <span className="text-slate-600 text-[8px]">{lbl}</span>
                      <span className={r === null ? 'text-slate-600' : r >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
                        {r === null ? '—' : `${r >= 0 ? '+' : ''}${r.toFixed(1)}`}
                      </span>
                    </span>
                  ))}
                </div>

                {/* Trade setup: stop / target / upside */}
                {c.target_1 !== null && (
                  <div className="mt-2 pt-2 border-t border-slate-800/60 text-[10px] font-mono">
                    <div className="flex items-center justify-between">
                      <span className="text-rose-400/80">SL ₹{fmtINR0(c.stop_loss ?? 0)}</span>
                      <div className="flex items-center gap-1.5">
                        {c.rr_ratio != null && (
                          <span className={`px-1 rounded font-bold ${
                            c.rr_ratio >= 2.0 ? 'text-emerald-400 bg-emerald-950/30'
                            : c.rr_ratio >= 1.0 ? 'text-indigo-400 bg-indigo-950/30'
                            : 'text-rose-400 bg-rose-950/30'
                          }`}>{c.rr_ratio.toFixed(1)}x</span>
                        )}
                        {c.position_size_shares != null && (
                          <span className="text-purple-400">{c.position_size_shares.toLocaleString('en-IN')} sh</span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center justify-between mt-0.5">
                      <span className="text-emerald-400">T1 ₹{fmtINR0(c.target_1)} <span className="text-emerald-400/70">+{fmt(c.potential_gain_pct ?? 0, 1)}%</span></span>
                      <div className="flex items-center gap-1.5">
                        {c.target_2 != null && <span className="text-emerald-400/60">T2 ₹{fmtINR0(c.target_2)}</span>}
                        {c.target_3 != null && <span className="text-emerald-400/40">T3 ₹{fmtINR0(c.target_3)}</span>}
                      </div>
                    </div>
                  </div>
                )}
              </button>
            ))}
          </div>
        )}
      </div>

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
  );
};
