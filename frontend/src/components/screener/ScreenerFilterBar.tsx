import React, { useState, useMemo, useEffect, useRef } from 'react';
import { Zap, ChevronDown, X } from 'lucide-react';
import { useStockStore } from '../../store/useStockStore';
import { PRESETS, EMPTY_FILTERS } from './constants';

export const ScreenerFilterBar: React.FC = () => {
  const { screenerFilters, setScreenerFilters, runScreener, isLoading } = useStockStore();

  const [showPresetMenu, setShowPresetMenu] = useState(false);
  const presetMenuRef = useRef<HTMLDivElement>(null);

  // Close preset dropdown when clicking outside
  useEffect(() => {
    if (!showPresetMenu) return;
    const handler = (e: MouseEvent) => {
      if (presetMenuRef.current && !presetMenuRef.current.contains(e.target as Node)) {
        setShowPresetMenu(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showPresetMenu]);

  // Detect which preset (if any) is currently active so we can highlight it.
  const activePresetName = useMemo(() => {
    return PRESETS.find(p =>
      Object.entries(p.filters).every(
        ([k, v]) => (screenerFilters as Record<string, unknown>)[k] === v
      )
    )?.name ?? null;
  }, [screenerFilters]);

  const handleClearAll = () => {
    setScreenerFilters({ ...EMPTY_FILTERS });
    runScreener();
  };

  return (
    <>
      {/* ── Preset Dropdown ───────────────────────────────────────────────── */}
      <div className="flex items-center gap-2">
        <div className="relative" ref={presetMenuRef}>
          <button
            onClick={() => setShowPresetMenu(v => !v)}
            disabled={isLoading}
            className={`flex items-center gap-2 px-3 py-2 rounded-xl border text-sm font-bold disabled:opacity-40 transition cursor-pointer ${
              activePresetName
                ? 'border-purple-500/70 bg-purple-900/30 text-purple-300'
                : 'border-border-subtle bg-bg-surface/30 hover:bg-bg-surface/70 hover:border-accent-primary/40 text-white'
            }`}
            title="Choose a preset scan"
          >
            <Zap className="w-3.5 h-3.5 text-purple-400" />
            {activePresetName
              ? <><span>{PRESETS.find(p => p.name === activePresetName)?.emoji}</span> {activePresetName}</>
              : 'Presets'
            }
            <ChevronDown className={`w-3.5 h-3.5 transition-transform ${showPresetMenu ? 'rotate-180' : ''}`} />
          </button>

          {showPresetMenu && (
            <div className="absolute top-full left-0 mt-1.5 z-50 w-72 bg-slate-950 border border-slate-700 rounded-xl shadow-xl overflow-hidden">
              <div className="p-1.5 max-h-[60vh] overflow-y-auto">
                {PRESETS.map(p => {
                  const isActive = activePresetName === p.name;
                  return (
                    <button
                      key={p.name}
                      onClick={() => {
                        setScreenerFilters({ ...EMPTY_FILTERS, ...p.filters });
                        runScreener();
                        setShowPresetMenu(false);
                      }}
                      className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left transition cursor-pointer ${
                        isActive
                          ? 'bg-purple-900/40 text-purple-200'
                          : 'hover:bg-slate-800/70 text-slate-200'
                      }`}
                      title={p.desc}
                    >
                      <span className="text-base leading-none shrink-0">{p.emoji}</span>
                      <div className="min-w-0">
                        <div className="text-xs font-bold truncate">{p.name}</div>
                        <div className="text-[10px] text-slate-500 truncate">{p.desc}</div>
                      </div>
                      {isActive && <span className="ml-auto text-purple-400 text-[10px] font-bold shrink-0">✓</span>}
                    </button>
                  );
                })}
                <div className="border-t border-slate-800 mt-1 pt-1">
                  <button
                    onClick={() => { handleClearAll(); setShowPresetMenu(false); }}
                    className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left hover:bg-rose-950/30 transition cursor-pointer text-rose-400"
                  >
                    <span className="text-base leading-none shrink-0">✕</span>
                    <div>
                      <div className="text-xs font-bold">Clear All</div>
                      <div className="text-[10px] text-slate-500">Reset filters &amp; reload</div>
                    </div>
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Active preset badge + quick-clear */}
        {activePresetName && (
          <button
            onClick={handleClearAll}
            className="flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-semibold bg-rose-950/20 border border-rose-800/40 text-rose-400 hover:bg-rose-950/40 transition cursor-pointer"
            title="Clear this preset"
          >
            Clear <X className="w-3 h-3" />
          </button>
        )}
      </div>

      {/* ── Active filter chips ────────────────────────────────────────────── */}
      {(() => {
        const chips: { label: string; onRemove: () => void }[] = [];
        if (screenerFilters.only_vajraturn) chips.push({ label: '🎯 VajraTurn', onRemove: () => { setScreenerFilters({ only_vajraturn: undefined }); runScreener(); } });
        if (screenerFilters.only_bb_squeeze) chips.push({ label: '🗜️ BB Squeeze', onRemove: () => { setScreenerFilters({ only_bb_squeeze: undefined }); runScreener(); } });
        if (screenerFilters.only_weinstein_stage2) chips.push({ label: '📈 Weinstein S2', onRemove: () => { setScreenerFilters({ only_weinstein_stage2: undefined }); runScreener(); } });
        if (screenerFilters.min_tqs != null) chips.push({ label: `💪 TQS ≥ ${screenerFilters.min_tqs}`, onRemove: () => { setScreenerFilters({ min_tqs: undefined }); runScreener(); } });
        if (screenerFilters.only_hilega_buy) chips.push({ label: '🟢 HM Buy', onRemove: () => { setScreenerFilters({ only_hilega_buy: undefined }); runScreener(); } });
        if (screenerFilters.only_rsi_bullish_div) chips.push({ label: '📐 RSI Div', onRemove: () => { setScreenerFilters({ only_rsi_bullish_div: undefined }); runScreener(); } });
        if (screenerFilters.only_macd_bullish_div) chips.push({ label: '📐 MACD Div', onRemove: () => { setScreenerFilters({ only_macd_bullish_div: undefined }); runScreener(); } });
        if (screenerFilters.only_boring_candle) chips.push({ label: '😴 Boring', onRemove: () => { setScreenerFilters({ only_boring_candle: undefined }); runScreener(); } });
        if (screenerFilters.only_explosive_candle) chips.push({ label: '💥 Explosive', onRemove: () => { setScreenerFilters({ only_explosive_candle: undefined }); runScreener(); } });
        if (screenerFilters.only_cpr_narrow) chips.push({ label: '📏 CPR Narrow', onRemove: () => { setScreenerFilters({ only_cpr_narrow: undefined }); runScreener(); } });
        if (screenerFilters.price_above_avwap) chips.push({ label: '🔵 Above AVWAP', onRemove: () => { setScreenerFilters({ price_above_avwap: undefined }); runScreener(); } });
        if (screenerFilters.price_above_zlema21) chips.push({ label: '⚡ Above ZLEMA', onRemove: () => { setScreenerFilters({ price_above_zlema21: undefined }); runScreener(); } });
        if (screenerFilters.min_psy_20 != null) chips.push({ label: `PSY ≥ ${screenerFilters.min_psy_20}`, onRemove: () => { setScreenerFilters({ min_psy_20: undefined }); runScreener(); } });
        if (screenerFilters.max_psy_20 != null) chips.push({ label: `PSY ≤ ${screenerFilters.max_psy_20}`, onRemove: () => { setScreenerFilters({ max_psy_20: undefined }); runScreener(); } });
        if (screenerFilters.min_rsi != null) chips.push({ label: `RSI ≥ ${screenerFilters.min_rsi}`, onRemove: () => { setScreenerFilters({ min_rsi: undefined }); runScreener(); } });
        if (screenerFilters.max_rsi != null) chips.push({ label: `RSI ≤ ${screenerFilters.max_rsi}`, onRemove: () => { setScreenerFilters({ max_rsi: undefined }); runScreener(); } });
        if (screenerFilters.sma_200_cross) chips.push({ label: `SMA200 ${screenerFilters.sma_200_cross}`, onRemove: () => { setScreenerFilters({ sma_200_cross: undefined }); runScreener(); } });
        if (screenerFilters.macd_trend) chips.push({ label: `MACD ${screenerFilters.macd_trend}`, onRemove: () => { setScreenerFilters({ macd_trend: undefined }); runScreener(); } });
        if (screenerFilters.only_nr7) chips.push({ label: '🎯 NR7', onRemove: () => { setScreenerFilters({ only_nr7: undefined }); runScreener(); } });
        if (screenerFilters.only_inside_bar) chips.push({ label: '📦 Inside Bar', onRemove: () => { setScreenerFilters({ only_inside_bar: undefined }); runScreener(); } });
        if (screenerFilters.only_gap_up) chips.push({ label: '⬆️ Gap Up', onRemove: () => { setScreenerFilters({ only_gap_up: undefined }); runScreener(); } });
        if (screenerFilters.only_gap_down) chips.push({ label: '⬇️ Gap Down', onRemove: () => { setScreenerFilters({ only_gap_down: undefined }); runScreener(); } });
        if (screenerFilters.volume_breakout) chips.push({ label: `Vol ${screenerFilters.volume_breakout}`, onRemove: () => { setScreenerFilters({ volume_breakout: undefined }); runScreener(); } });
        if (screenerFilters.stochrsi_bullish_xover_max_days != null) chips.push({ label: `StochRSI Xover ≤ ${screenerFilters.stochrsi_bullish_xover_max_days}d`, onRemove: () => { setScreenerFilters({ stochrsi_bullish_xover_max_days: undefined }); runScreener(); } });
        if (chips.length === 0) return null;
        return (
          <div className="flex flex-wrap gap-1.5 items-center">
            <span className="text-[10px] text-slate-500 uppercase tracking-wide font-semibold">Active:</span>
            {chips.map(chip => (
              <button
                key={chip.label}
                onClick={chip.onRemove}
                className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-purple-900/30 border border-purple-500/40 text-purple-300 hover:bg-rose-900/30 hover:border-rose-500/40 hover:text-rose-300 transition"
                title="Click to remove this filter"
              >
                {chip.label} <span className="opacity-60">✕</span>
              </button>
            ))}
          </div>
        );
      })()}
    </>
  );
};
