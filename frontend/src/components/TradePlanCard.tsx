import React, { useEffect, useState } from 'react';
import { useStockStore } from '../store/useStockStore';
import { apiService, type TradePlan } from '../services/api';
import { Target, TrendingUp, TrendingDown, Minus, AlertTriangle } from 'lucide-react';

/**
 * Trade Plan card — pure presentation.
 * All trend/bias/sizing math is computed by the backend
 * (`GET /symbols/{symbol}/trade-plan`). This component only renders.
 */
export const TradePlanCard: React.FC = () => {
  const { activeSymbol, activeSymbolDetail } = useStockStore();
  const [plan, setPlan] = useState<TradePlan | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      if (!activeSymbol) { setPlan(null); return; }
      setLoading(true);
      const p = await apiService.getTradePlan(activeSymbol);
      if (!cancelled) { setPlan(p); setLoading(false); }
    };
    run();
    return () => { cancelled = true; };
  }, [activeSymbol]);

  if (loading && !plan) return null;
  if (!plan) return null;

  const fmtINR = (n: number) =>
    new Intl.NumberFormat('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n);

  const isBull = plan.bias === 'BULLISH';
  const isBear = plan.bias === 'BEARISH';

  const biasClass = isBull
    ? 'text-emerald-400 bg-emerald-950/20 border-emerald-900/30'
    : isBear
    ? 'text-rose-400 bg-rose-950/20 border-rose-900/30'
    : 'text-slate-400 bg-slate-900/40 border-slate-800';

  const BiasIcon = isBull ? TrendingUp : isBear ? TrendingDown : Minus;

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
        <span
          className={`text-[10px] font-bold px-2 py-0.5 rounded border ${biasClass}`}
          title={plan.reasons.join(' · ')}
        >
          <BiasIcon className="w-3 h-3 inline mr-1" />
          {plan.bias}
        </span>
      </div>

      {/* Bias reasons */}
      {plan.reasons.length > 0 && (
        <p className="text-[10px] text-slate-500 leading-relaxed">
          {plan.reasons.join(' · ')}
        </p>
      )}

      {/* Plan grid */}
      <div className="grid grid-cols-2 gap-2">
        {[
          { label: 'Entry (CMP)', value: `₹${fmtINR(plan.entry)}`,    color: 'text-white'        },
          { label: 'ATR (14)',    value: `₹${fmtINR(plan.atr_14)}`,   color: 'text-slate-300'    },
          { label: 'Stop Loss',   value: `₹${fmtINR(plan.stop_loss)}`, color: 'text-rose-400'    },
          { label: 'Target 1',    value: `₹${fmtINR(plan.target_1)}`,  color: 'text-emerald-400' },
          { label: 'Target 2',    value: `₹${fmtINR(plan.target_2)}`,  color: 'text-emerald-300' },
          { label: 'R:R Ratio',   value: `1 : ${plan.rr_ratio.toFixed(2)}`, color: plan.rr_ratio >= 1.5 ? 'text-emerald-400' : 'text-amber-400' },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-slate-900/50 rounded-lg p-2.5 border border-slate-800/60">
            <p className="text-[10px] text-slate-500">{label}</p>
            <p className={`text-xs font-bold font-mono mt-0.5 ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      {/* Position size */}
      <div className="flex items-center justify-between bg-purple-950/20 border border-purple-900/30 rounded-lg px-3 py-2">
        <span className="text-xs text-slate-400">
          Suggested Qty
          <span className="text-[10px] text-slate-600 ml-1.5">(risk ₹{fmtINR(plan.risk_per_trade)})</span>
        </span>
        <span className="text-sm font-extrabold text-purple-400 font-mono">
          {plan.position_size_shares > 0 ? `${plan.position_size_shares.toLocaleString('en-IN')} shares` : '—'}
        </span>
      </div>

      {/* Warning if R:R too low */}
      {plan.rr_ratio < 1 && (
        <div className="flex items-center gap-1.5 text-[10px] text-amber-400 bg-amber-950/20 border border-amber-900/30 rounded-lg px-3 py-2">
          <AlertTriangle className="w-3 h-3 shrink-0" />
          R:R below 1:1 — consider waiting for a better entry near support
        </div>
      )}

      <p className="text-[9px] text-slate-600">
        Entry zone {plan.entry_zone} · Risk per trade configurable in Settings → Portfolio.
      </p>
    </div>
  );
};
