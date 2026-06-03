import React, { useMemo, useState } from 'react';
import { useStockStore } from '../store/useStockStore';
import { Target, TrendingUp, TrendingDown, AlertTriangle } from 'lucide-react';

export const TradePlanCard: React.FC = () => {
  const { candles, indicators, activeSymbolDetail } = useStockStore();
  const [riskAmount, setRiskAmount] = useState<number>(5000);

  const plan = useMemo(() => {
    if (!candles.length || !indicators.length) return null;

    const latest = candles[candles.length - 1];
    const latestInd = indicators[indicators.length - 1];

    const entry = latest.close;
    const atr = latestInd?.atr_14 ?? entry * 0.02; // fallback 2% if no ATR
    const sma200 = latestInd?.sma_200 ?? null;

    const stopLoss   = entry - atr * 1.5;
    const target1    = entry + atr * 2.0;   // 1.33:1 R/R
    const target2    = entry + atr * 4.0;   // 2.67:1 R/R
    const riskPerUnit = entry - stopLoss;
    const qty        = riskPerUnit > 0 ? Math.floor(riskAmount / riskPerUnit) : 0;
    const rrRatio    = riskPerUnit > 0 ? ((target1 - entry) / riskPerUnit) : 0;

    // Trend bias from SMA 200
    const trend = sma200
      ? (entry > sma200 ? 'BULLISH' : 'BEARISH')
      : 'NEUTRAL';

    return { entry, atr, stopLoss, target1, target2, qty, rrRatio, trend, sma200 };
  }, [candles, indicators, riskAmount]);

  if (!plan) return null;

  const fmtINR = (n: number) =>
    new Intl.NumberFormat('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n);

  const isBull = plan.trend === 'BULLISH';
  const isNeutral = plan.trend === 'NEUTRAL';

  return (
    <div className="p-4 rounded-xl border border-slate-800/80 bg-[#121620]/40 flex flex-col gap-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-bold text-white flex items-center gap-2">
          <Target className="w-4 h-4 text-purple-500" />
          Trade Plan
          {activeSymbolDetail && (
            <span className="text-slate-400 font-normal">— {activeSymbolDetail.symbol.replace('.NS', '')}</span>
          )}
        </h3>
        <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${
          isBull    ? 'text-emerald-400 bg-emerald-950/20 border-emerald-900/30'
          : isNeutral ? 'text-slate-400 bg-slate-900/40 border-slate-800'
          : 'text-rose-400 bg-rose-950/20 border-rose-900/30'
        }`}>
          {isBull ? <TrendingUp className="w-3 h-3 inline mr-1" /> : <TrendingDown className="w-3 h-3 inline mr-1" />}
          {plan.trend}
        </span>
      </div>

      {/* Risk input */}
      <div className="flex items-center gap-2">
        <label className="text-[10px] text-slate-400 shrink-0">Risk per trade (₹)</label>
        <input
          type="number"
          value={riskAmount}
          onChange={e => setRiskAmount(Math.max(100, Number(e.target.value)))}
          className="w-28 px-2 py-1 text-xs rounded bg-slate-900 border border-slate-800 text-white focus:outline-none focus:border-purple-500 transition font-mono"
        />
      </div>

      {/* Plan grid */}
      <div className="grid grid-cols-2 gap-2">
        {[
          { label: 'Entry (CMP)',  value: `₹${fmtINR(plan.entry)}`,   color: 'text-white'        },
          { label: 'ATR (14)',     value: `₹${fmtINR(plan.atr)}`,     color: 'text-slate-300'    },
          { label: 'Stop Loss',    value: `₹${fmtINR(plan.stopLoss)}`, color: 'text-rose-400'    },
          { label: 'Target 1',     value: `₹${fmtINR(plan.target1)}`,  color: 'text-emerald-400' },
          { label: 'Target 2',     value: `₹${fmtINR(plan.target2)}`,  color: 'text-emerald-300' },
          { label: 'R:R Ratio',    value: `1 : ${plan.rrRatio.toFixed(2)}`, color: plan.rrRatio >= 1.5 ? 'text-emerald-400' : 'text-amber-400' },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-slate-900/50 rounded-lg p-2.5 border border-slate-800/60">
            <p className="text-[10px] text-slate-500">{label}</p>
            <p className={`text-xs font-bold font-mono mt-0.5 ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      {/* Position size */}
      <div className="flex items-center justify-between bg-purple-950/20 border border-purple-900/30 rounded-lg px-3 py-2">
        <span className="text-xs text-slate-400">Suggested Qty</span>
        <span className="text-sm font-extrabold text-purple-400 font-mono">
          {plan.qty > 0 ? `${plan.qty.toLocaleString('en-IN')} shares` : '—'}
        </span>
      </div>

      {/* Warning if stop too tight */}
      {plan.rrRatio < 1 && (
        <div className="flex items-center gap-1.5 text-[10px] text-amber-400 bg-amber-950/20 border border-amber-900/30 rounded-lg px-3 py-2">
          <AlertTriangle className="w-3 h-3 shrink-0" />
          R:R below 1:1 — consider waiting for a better entry near support
        </div>
      )}

      <p className="text-[9px] text-slate-600">
        Stop = Entry − 1.5×ATR · T1 = Entry + 2×ATR · T2 = Entry + 4×ATR · Qty = Risk ÷ (Entry − Stop)
      </p>
    </div>
  );
};
