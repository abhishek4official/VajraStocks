import React from 'react';
import { useStockStore } from '../store/useStockStore';
import { TrendingUp, TrendingDown, Layers } from 'lucide-react';

export const MetricsTable: React.FC = () => {
  const { indicators } = useStockStore();

  // Show latest 15 indicator logs in reverse chronological order
  const latestIndicators = [...indicators]
    .sort((a, b) => b.time.localeCompare(a.time))
    .slice(0, 15);

  const formatNumber = (val: number | null | undefined, decimals = 2) => {
    if (val === null || val === undefined) return '-';
    return Number(val).toFixed(decimals);
  };

  const getRSICardStyle = (rsi: number | null | undefined) => {
    if (rsi === null || rsi === undefined) return 'text-slate-400';
    if (rsi >= 70) return 'text-rose-400 font-bold bg-rose-950/20 px-2 py-0.5 rounded border border-rose-900/30';
    if (rsi <= 30) return 'text-emerald-400 font-bold bg-emerald-950/20 px-2 py-0.5 rounded border border-emerald-900/30';
    return 'text-slate-300';
  };

  const getMacdStyle = (val: number | null | undefined) => {
    if (val === null || val === undefined) return 'text-slate-400';
    return val >= 0 ? 'text-emerald-400' : 'text-rose-400';
  };

  return (
    <div className="w-full bg-bg-surface/60 rounded-xl border border-border-subtle p-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Layers className="w-5 h-5 text-accent-primary" />
          <h3 className="text-md font-bold text-text-main tracking-wide">EOD Indicator Logs</h3>
        </div>
        <span className="text-xs text-slate-500 font-mono">Showing latest 15 trading days</span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left text-sm text-slate-300">
          <thead>
            <tr className="border-b border-slate-800 text-xs text-slate-400 uppercase tracking-wider font-mono">
              <th className="py-2 px-3">Date</th>
              <th className="py-2 px-3">RSI (14)</th>
              <th className="py-2 px-3">CMF (20)</th>
              <th className="py-2 px-3">StochRSI K</th>
              <th className="py-2 px-3">StochRSI D</th>
              <th className="py-2 px-3">SMA 20</th>
              <th className="py-2 px-3">SMA 50</th>
              <th className="py-2 px-3">SMA 200</th>
              <th className="py-2 px-3">MACD</th>
              <th className="py-2 px-3">Signal</th>
              <th className="py-2 px-3">Histogram</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-850">
            {latestIndicators.length === 0 ? (
              <tr>
                <td colSpan={11} className="py-8 text-center text-slate-500 text-sm">
                  No technical indicators computed for this symbol yet. Trigger a recalculation job inside the Sync Center.
                </td>
              </tr>
            ) : (
              latestIndicators.map((ind, index) => {
                const macdHist = ind.macd_histogram;
                const isBullish = macdHist !== null && macdHist !== undefined && macdHist >= 0;

                return (
                  <tr key={index} className="hover:bg-slate-900/40 transition">
                    <td className="py-2.5 px-3 font-mono text-slate-400">{ind.time}</td>
                    <td className="py-2.5 px-3">
                      <span className={getRSICardStyle(ind.rsi_14)}>
                        {formatNumber(ind.rsi_14)}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 font-mono">
                      <span className={
                        ind.cmf_20 == null ? 'text-slate-400'
                        : ind.cmf_20 >= 0.05 ? 'text-emerald-400 font-semibold'
                        : ind.cmf_20 <= -0.05 ? 'text-rose-400 font-semibold'
                        : 'text-slate-300'
                      }>
                        {formatNumber(ind.cmf_20, 3)}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 font-mono">
                      <span className={
                        ind.stochrsi_k == null ? 'text-slate-400'
                        : ind.stochrsi_k >= 80 ? 'text-rose-400 font-semibold'
                        : ind.stochrsi_k <= 20 ? 'text-emerald-400 font-semibold'
                        : 'text-slate-300'
                      }>
                        {formatNumber(ind.stochrsi_k, 1)}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 font-mono text-slate-300">{formatNumber(ind.stochrsi_d, 1)}</td>
                    <td className="py-2.5 px-3 font-mono">{formatNumber(ind.sma_20)}</td>
                    <td className="py-2.5 px-3 font-mono">{formatNumber(ind.sma_50)}</td>
                    <td className="py-2.5 px-3 font-mono">{formatNumber(ind.sma_200)}</td>
                    <td className="py-2.5 px-3 font-mono">{formatNumber(ind.macd_line)}</td>
                    <td className="py-2.5 px-3 font-mono">{formatNumber(ind.macd_signal)}</td>
                    <td className="py-2.5 px-3">
                      <span className={`font-mono flex items-center gap-1.5 ${getMacdStyle(macdHist)}`}>
                        {isBullish ? (
                          <TrendingUp className="w-3.5 h-3.5" />
                        ) : macdHist !== null && macdHist !== undefined ? (
                          <TrendingDown className="w-3.5 h-3.5" />
                        ) : null}
                        {formatNumber(macdHist)}
                      </span>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
