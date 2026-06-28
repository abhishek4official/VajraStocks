import React, { useEffect, useState } from 'react';
import { useStockStore } from '../store/useStockStore';
import { Filter, HelpCircle, X } from 'lucide-react';
import { StockChartWorkspace } from './StockChartWorkspace';
import type { StrategyMeta } from '../services/api';
import { apiService } from '../services/api';
import { PRESETS } from './screener/constants';
import { ScreenerFilterBar } from './screener/ScreenerFilterBar';
import { ScreenerResultGrid } from './screener/ScreenerResultGrid';

export const ScreenerPanel: React.FC = () => {
  const {
    setSelectedSymbol,
    watchlists,
    activeWatchlistId,
    addToWatchlist,
  } = useStockStore();

  const [modalSymbol, setModalSymbol] = useState<string | null>(null);
  const [showHelp, setShowHelp] = useState(false);
  const [strategies, setStrategies] = useState<StrategyMeta[]>([]);

  // Auto-run on mount — restores last session's scan (or returns full universe if no filters).
  const { runScreener } = useStockStore();
  useEffect(() => { runScreener(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Load the registered strategies once for the per-strategy signal chips (stable column order).
  useEffect(() => { apiService.getStrategies().then(setStrategies).catch(() => setStrategies([])); }, []);

  const handleOpenChartModal = async (symbol: string) => {
    setModalSymbol(symbol);
    await setSelectedSymbol(symbol);
  };

  // Add ticker to the active watchlist (or the first one if none active)
  const handleAddToWatchlist = (symbol: string) => {
    const targetId = activeWatchlistId ?? watchlists[0]?.id;
    if (targetId) addToWatchlist(targetId, symbol);
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
            onClick={() => setShowHelp(true)}
            className="flex items-center gap-1.5 px-3 py-2 bg-bg-surface/80 hover:bg-indigo-900/30 border border-border-subtle hover:border-indigo-500/50 text-slate-400 hover:text-indigo-300 rounded-lg text-sm font-bold transition cursor-pointer"
            title="How to use the screener"
          >
            <HelpCircle className="w-4 h-4" />
            ?
          </button>
        </div>
      </div>

      <ScreenerFilterBar />

      <ScreenerResultGrid
        strategies={strategies}
        onAddToWatchlist={handleAddToWatchlist}
        onOpenChart={handleOpenChartModal}
      />

      {/* ── Help Modal ─────────────────────────────────────────────────────── */}
      {showHelp && (
        <div className="fixed inset-0 bg-bg-base/80 backdrop-blur-md flex items-center justify-center z-50 p-4" onClick={() => setShowHelp(false)}>
          <div className="w-full max-w-3xl bg-bg-surface border border-border-subtle rounded-2xl shadow-2xl flex flex-col max-h-[90vh] overflow-hidden" onClick={e => e.stopPropagation()}>
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-border-subtle">
              <div className="flex items-center gap-2.5">
                <HelpCircle className="w-5 h-5 text-accent-primary" />
                <h2 className="text-base font-bold text-text-main">Screener — How to Use</h2>
              </div>
              <button onClick={() => setShowHelp(false)} className="p-1.5 rounded-lg hover:bg-bg-base/60 text-text-muted hover:text-text-main transition cursor-pointer">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="overflow-y-auto px-6 py-5 space-y-6 text-sm text-text-muted">

              {/* How to use */}
              <section>
                <h3 className="text-xs font-bold uppercase tracking-widest text-accent-primary mb-3">How to Use</h3>
                <div className="space-y-2 text-[13px] leading-relaxed">
                  <p><span className="text-text-main font-semibold">1. Pick a Preset</span> — Click the <strong>Presets</strong> button to open the dropdown and choose a scan (Breakout, Momentum, VajraTurn, HM Buy, etc.). The active preset is highlighted and shown on the button itself.</p>
                  <p><span className="text-text-main font-semibold">2. Clear All</span> — Resets all filters and loads the full stock universe.</p>
                  <p><span className="text-text-main font-semibold">3. Active Filter Chips</span> — Pills shown below the presets confirm which filters are live. Click ✕ on any chip to remove that filter individually.</p>
                  <p><span className="text-text-main font-semibold">4. Column Filters</span> — The input row under the header lets you narrow results further (e.g. <code className="bg-bg-base px-1 rounded text-xs text-text-main">&gt;60</code> in TQS, <code className="bg-bg-base px-1 rounded text-xs text-text-main">&lt;30</code> in RSI). Supports <code className="bg-bg-base px-1 rounded text-xs text-text-main">&gt;</code> <code className="bg-bg-base px-1 rounded text-xs text-text-main">&lt;</code> <code className="bg-bg-base px-1 rounded text-xs text-text-main">=</code> operators.</p>
                  <p><span className="text-text-main font-semibold">5. Sort</span> — Click any column header to sort. Click again to reverse.</p>
                  <p><span className="text-text-main font-semibold">6. Chart</span> — Click <span className="text-purple-400 font-mono">Chart</span> on any row for a quick chart popup. Click <span className="text-purple-400 font-mono">View</span> to open the full Explorer.</p>
                  <p><span className="text-text-main font-semibold">7. Export</span> — <span className="text-purple-400">Export CSV</span> downloads every visible (filtered) row.</p>
                </div>
              </section>

              {/* Ticker badges */}
              <section>
                <h3 className="text-xs font-bold uppercase tracking-widest text-accent-primary mb-3">Ticker Badges</h3>
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { badge: 'VT', color: 'bg-purple-900/50 border-purple-500/40 text-purple-300', label: 'VajraTurn', desc: 'StochRSI K crossed above D in oversold zone within 5 days + RSI 30–52 + volume above avg + price 0–5% above rising SMA200. High R:R early reversal signal.' },
                    { badge: 'SQ', color: 'bg-amber-900/40 border-amber-500/40 text-amber-300', label: 'BB Squeeze', desc: 'Bollinger Band width is at its lowest in 20 days. Volatility contraction — stock is coiling for an explosive move.' },
                    { badge: 'S2', color: 'bg-emerald-900/40 border-emerald-500/40 text-emerald-300', label: 'Weinstein Stage 2', desc: 'Price is above a rising 200-day SMA. Classic markup phase — the ideal stage to be long.' },
                  ].map(b => (
                    <div key={b.badge} className="flex gap-2 items-start p-2.5 rounded-lg bg-bg-base/60 border border-border-subtle">
                      <span className={`shrink-0 text-[9px] font-bold px-1.5 py-0.5 rounded border ${b.color}`}>{b.badge}</span>
                      <div>
                        <p className="text-text-main font-semibold text-[11px]">{b.label}</p>
                        <p className="text-text-muted text-[10px] mt-0.5 leading-relaxed">{b.desc}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </section>

              {/* Grid columns */}
              <section>
                <h3 className="text-xs font-bold uppercase tracking-widest text-accent-primary mb-3">Grid Columns</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1.5">
                  {[
                    ['Price', 'Last End-of-Day closing price (₹).'],
                    ['Chg%', 'Day-over-day price change as a percentage.'],
                    ['Avg Val', 'Average daily traded value (price × volume) over 20 days. Proxy for liquidity.'],
                    ['Bias', 'Composite regime: VERY_BULLISH / BULLISH / NEUTRAL / BEARISH / VERY_BEARISH. Number = composite score (0–100).'],
                    ['1W / 2W / 3W / 4W', 'Rolling returns over last 5 / 10 / 15 / 20 trading days.'],
                    ['Stop', 'ATR-based stop-loss: nearest structural support − 1.5 × ATR.'],
                    ['T1 / T2 / T3', 'Structural resistance targets ranked by confluence strength.'],
                    ['Upside', 'Potential gain % from current price to Target 1.'],
                    ['R:R', 'Risk-to-Reward ratio = (T1 − Price) ÷ (Price − Stop). ≥ 2 is preferred.'],
                    ['TQS', 'Trend Quality Score (0–100). ADX strength (0–40) + price above EMA9/SMA20/SMA50 (0–30) + MA alignment stack (0–20) + RSI in trend zone 45–70 (0–10). Higher = cleaner trend.'],
                    ['Stage', 'Weinstein Stage. S1=Basing · S2=Markup ✓ · S3=Topping · S4=Decline.'],
                    ['Shares', 'Suggested position size: risk budget ÷ (Price − Stop).'],
                    ['Vol Brk', 'Volume Breakout Ratio — today\'s volume ÷ 20-day average. >1.5 = notable.'],
                    ['RSI', 'Relative Strength Index (14). <30 = oversold, >70 = overbought.'],
                    ['CMF', 'Chaikin Money Flow (20). Positive = accumulation, negative = distribution.'],
                    ['StochRSI K/D', 'Stochastic RSI oscillator. K crossing above D in <30 zone = bullish.'],
                    ['SMA 20/50/200', 'Whether price is ABOVE or BELOW each moving average.'],
                    ['MACD', 'MACD trend: BULLISH (histogram positive & rising) or BEARISH.'],
                    ['HA', 'Heikin-Ashi candle direction — smoothed trend indicator.'],
                    ['Renko / LB', 'Renko brick and Three-Line Break direction. Filters noise.'],
                    ['RS 1M', 'Relative Strength vs NIFTY 50 over 21 days. >1 = outperforming.'],
                    ['Patterns', 'NR7 (narrowest 7-day range), Inside Bar, Gap Up, Gap Down.'],
                    ['ML Signal', 'VajraML triple-barrier classifier: Strong Buy / Buy / Watch / Avoid / Market Risk.'],
                    ['EMA Ribbon', 'Days since EMA9 crossed above EMA20 (ribbon flip to bullish).'],
                    ['GX / MACD Xover / CMF Xover', 'Days since Golden Cross (SMA20>SMA50), MACD bullish crossover, CMF crossed above zero.'],
                    ['HM', 'Hilega-Milega: current RSI position vs its 21-period WMA. BUY = RSI above WMA (bullish momentum), SELL = RSI below WMA.'],
                    ['RSI Div / MACD Div', 'Divergence detection (14-bar lookback). BULLISH = lower price low, higher indicator low. BEARISH = opposite.'],
                    ['ZLEMA', 'Zero-Lag EMA(21) position. ▲=price above, ▼=price below. Hover shows ZLEMA value.'],
                    ['Candle', '😴 Boring candle = wicks > body (compression). 💥 Explosive = today range ≥1.5× prior boring candle range.'],
                    ['CPR D / CPR W', 'Central Pivot Range pivot point (PP). N badge = narrow CPR (<0.5% of price) = trending day expected.'],
                    ['PSY', 'Psychological Line (20-day). % of days where close > previous close. >60%=bullish, <40%=bearish.'],
                    ['AVWAP', 'Anchored VWAP from last gap-up candle (open >1% above prev close). ▲=price above, ▼=price below.'],
                    ['Mkt Cap', 'Market capitalisation in crores (₹).'],
                    ['P/E · P/B · EV/EBITDA', 'Fundamental valuation multiples.'],
                    ['ROE · D/E · Margin · EPS', 'Profitability and leverage metrics.'],
                  ].map(([col, desc]) => (
                    <div key={col} className="flex gap-2 py-1 border-b border-border-subtle/50">
                      <span className="shrink-0 w-28 font-mono text-[10px] font-bold text-text-main">{col}</span>
                      <span className="text-[11px] text-text-muted leading-relaxed">{desc}</span>
                    </div>
                  ))}
                </div>
              </section>

              {/* Presets */}
              <section>
                <h3 className="text-xs font-bold uppercase tracking-widest text-accent-primary mb-3">Scan Presets</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {PRESETS.map(p => (
                    <div key={p.name} className="flex gap-2 items-start p-2.5 rounded-lg bg-bg-base/60 border border-border-subtle">
                      <span className="text-base leading-none shrink-0">{p.emoji}</span>
                      <div>
                        <p className="text-text-main font-semibold text-[11px]">{p.name}</p>
                        <p className="text-text-muted text-[10px] mt-0.5 leading-relaxed">{p.desc}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </section>

            </div>

            <div className="px-6 py-3 border-t border-border-subtle flex justify-end">
              <button onClick={() => setShowHelp(false)} className="px-4 py-2 bg-accent-primary hover:bg-accent-primary/80 text-white text-sm font-bold rounded-lg transition cursor-pointer">
                Got it
              </button>
            </div>
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
  );
};
