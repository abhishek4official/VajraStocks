import React, { useRef } from 'react';
import { useStockStore } from '../store/useStockStore';
import { Upload, Trash2, TrendingUp, TrendingDown, IndianRupee, BarChart2 } from 'lucide-react';
import type { PortfolioHolding } from '../store/useStockStore';

export const PortfolioPanel: React.FC = () => {
  const { portfolioHoldings, importPortfolioCSV, clearPortfolio, setSelectedSymbol, setActiveTab } = useStockStore();
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── Aggregate stats ────────────────────────────────────────────────────────

  const totalInvested = portfolioHoldings.reduce((s, h) => s + h.invested, 0);
  const totalCurrent = portfolioHoldings.reduce((s, h) => s + h.currentVal, 0);
  const totalPnL = totalCurrent - totalInvested;
  const totalReturnPct = totalInvested > 0 ? (totalPnL / totalInvested) * 100 : 0;

  const isBullish = totalPnL >= 0;

  // ── CSV import ─────────────────────────────────────────────────────────────

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      const text = ev.target?.result as string;
      if (text) importPortfolioCSV(text);
    };
    reader.readAsText(file);
    e.target.value = '';
  };

  const handleInspect = async (instrument: string) => {
    const symbol = instrument.endsWith('.NS') ? instrument : `${instrument}.NS`;
    await setSelectedSymbol(symbol);
    setActiveTab('explorer');
  };

  // ── Helpers ────────────────────────────────────────────────────────────────

  const fmt = (n: number, dec = 2) => n.toFixed(dec);
  const fmtINR = (n: number) =>
    new Intl.NumberFormat('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n);

  const pnlClass = (v: number) =>
    v >= 0 ? 'text-emerald-400' : 'text-rose-400';

  // ── Allocation mini-bar ────────────────────────────────────────────────────

  const allocationBars = portfolioHoldings.map(h => ({
    label: h.instrument,
    pct: totalCurrent > 0 ? (h.currentVal / totalCurrent) * 100 : 0,
    bullish: h.pnl >= 0,
  }));

  const COLORS = [
    'bg-purple-500', 'bg-indigo-500', 'bg-blue-500', 'bg-cyan-500',
    'bg-teal-500', 'bg-emerald-500', 'bg-amber-500', 'bg-rose-500',
  ];

  return (
    <div className="flex-1 flex flex-col gap-5 p-5 overflow-y-auto max-h-full">

      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            <IndianRupee className="w-5 h-5 text-purple-500" />
            Portfolio
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Import your Zerodha holdings CSV to track positions and P&amp;L.
          </p>
        </div>
        <div className="flex gap-2">
          <input ref={fileInputRef} type="file" accept=".csv" className="hidden" onChange={handleFileChange} />
          <button
            onClick={() => fileInputRef.current?.click()}
            className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-lg text-sm font-bold transition cursor-pointer shadow-lg shadow-purple-900/20"
          >
            <Upload className="w-4 h-4" />
            Import CSV
          </button>
          {portfolioHoldings.length > 0 && (
            <button
              onClick={clearPortfolio}
              className="flex items-center gap-2 px-3 py-2 bg-slate-800 hover:bg-rose-950/60 border border-slate-700 hover:border-rose-900 text-slate-400 hover:text-rose-400 rounded-lg text-sm font-bold transition cursor-pointer"
            >
              <Trash2 className="w-4 h-4" />
              Clear
            </button>
          )}
        </div>
      </div>

      {portfolioHoldings.length === 0 ? (
        /* ── Empty state ──────────────────────────────────────────────────── */
        <div className="flex-1 flex flex-col items-center justify-center text-slate-500 py-20 gap-4">
          <BarChart2 className="w-14 h-14 text-slate-700" />
          <div className="text-center space-y-1">
            <p className="font-semibold text-slate-400">No portfolio loaded</p>
            <p className="text-xs text-slate-500 max-w-xs">
              Export your holdings from Zerodha Console → Portfolio → Holdings → Download CSV, then import it here.
            </p>
          </div>
          <button
            onClick={() => fileInputRef.current?.click()}
            className="mt-2 px-5 py-2.5 bg-purple-600 hover:bg-purple-500 text-white rounded-xl text-sm font-bold transition cursor-pointer"
          >
            Import Zerodha CSV
          </button>
        </div>
      ) : (
        <>
          {/* ── Summary Cards ──────────────────────────────────────────────── */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: 'Total Invested', value: `₹${fmtINR(totalInvested)}`, sub: null, color: 'text-white' },
              { label: 'Current Value', value: `₹${fmtINR(totalCurrent)}`, sub: null, color: 'text-white' },
              {
                label: 'Net P&L',
                value: `${isBullish ? '+' : ''}₹${fmtINR(totalPnL)}`,
                sub: null,
                color: isBullish ? 'text-emerald-400' : 'text-rose-400',
              },
              {
                label: 'Return',
                value: `${isBullish ? '+' : ''}${fmt(totalReturnPct)}%`,
                sub: `${portfolioHoldings.length} positions`,
                color: isBullish ? 'text-emerald-400' : 'text-rose-400',
              },
            ].map(({ label, value, sub, color }) => (
              <div key={label} className="p-4 rounded-xl border border-slate-800/80 bg-[#121620]/40">
                <p className="text-xs text-slate-400 font-medium">{label}</p>
                <p className={`text-lg font-extrabold mt-1 font-mono ${color}`}>{value}</p>
                {sub && <p className="text-[10px] text-slate-500 mt-0.5">{sub}</p>}
              </div>
            ))}
          </div>

          {/* ── Allocation Strip ───────────────────────────────────────────── */}
          {allocationBars.length > 0 && (
            <div className="p-4 rounded-xl border border-slate-800/80 bg-[#121620]/30">
              <p className="text-xs font-semibold text-slate-400 mb-3">Portfolio Allocation by Current Value</p>
              <div className="flex h-4 rounded-full overflow-hidden gap-0.5">
                {allocationBars.map((bar, i) => (
                  <div
                    key={bar.label}
                    className={`${COLORS[i % COLORS.length]} transition-all`}
                    style={{ width: `${bar.pct}%` }}
                    title={`${bar.label}: ${bar.pct.toFixed(1)}%`}
                  />
                ))}
              </div>
              <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2">
                {allocationBars.map((bar, i) => (
                  <div key={bar.label} className="flex items-center gap-1.5 text-[10px] text-slate-400">
                    <span className={`w-2 h-2 rounded-full ${COLORS[i % COLORS.length]}`} />
                    {bar.label} <span className="text-slate-500">({bar.pct.toFixed(1)}%)</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── Holdings Table ─────────────────────────────────────────────── */}
          <div className="bg-[#121620]/60 rounded-xl border border-slate-800/80 p-4 flex flex-col">
            <h3 className="text-sm font-bold text-white mb-3 flex items-center gap-2">
              Holdings
              <span className="text-xs text-slate-500 font-normal font-mono">({portfolioHoldings.length})</span>
            </h3>
            <div className="overflow-auto">
              <table className="w-full border-collapse text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-800 text-xs text-slate-400 uppercase tracking-wider font-mono">
                    <th className="py-2.5 px-3">Instrument</th>
                    <th className="py-2.5 px-3 text-right">Qty</th>
                    <th className="py-2.5 px-3 text-right">Avg Cost</th>
                    <th className="py-2.5 px-3 text-right">LTP</th>
                    <th className="py-2.5 px-3 text-right">Invested</th>
                    <th className="py-2.5 px-3 text-right">Current Val</th>
                    <th className="py-2.5 px-3 text-right">P&amp;L</th>
                    <th className="py-2.5 px-3 text-right">Return</th>
                    <th className="py-2.5 px-3 text-center">Chart</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-850">
                  {portfolioHoldings.map((h: PortfolioHolding) => {
                    const bull = h.pnl >= 0;
                    return (
                      <tr key={h.instrument} className="hover:bg-slate-900/40 transition">
                        <td className="py-3 px-3 font-bold text-white font-mono tracking-wide">
                          {h.instrument}
                        </td>
                        <td className="py-3 px-3 text-right font-mono text-slate-300">
                          {h.qty.toLocaleString('en-IN')}
                        </td>
                        <td className="py-3 px-3 text-right font-mono text-slate-300">
                          ₹{fmtINR(h.avgCost)}
                        </td>
                        <td className="py-3 px-3 text-right font-mono text-slate-300">
                          ₹{fmtINR(h.ltp)}
                        </td>
                        <td className="py-3 px-3 text-right font-mono text-slate-400">
                          ₹{fmtINR(h.invested)}
                        </td>
                        <td className="py-3 px-3 text-right font-mono text-white">
                          ₹{fmtINR(h.currentVal)}
                        </td>
                        <td className={`py-3 px-3 text-right font-mono font-semibold ${pnlClass(h.pnl)}`}>
                          <span className="flex items-center justify-end gap-1">
                            {bull ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
                            {bull ? '+' : ''}₹{fmtINR(h.pnl)}
                          </span>
                        </td>
                        <td className={`py-3 px-3 text-right font-mono font-semibold ${pnlClass(h.netChgPct)}`}>
                          {bull ? '+' : ''}{fmt(h.netChgPct)}%
                        </td>
                        <td className="py-3 px-3 text-center">
                          <button
                            onClick={() => handleInspect(h.instrument)}
                            className="px-2.5 py-1 rounded bg-slate-900 border border-slate-800 hover:border-purple-500/80 text-slate-400 hover:text-white text-xs transition cursor-pointer"
                          >
                            View
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
