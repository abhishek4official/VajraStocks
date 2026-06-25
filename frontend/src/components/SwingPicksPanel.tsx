import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useStockStore } from '../store/useStockStore';
import { apiService, type SwingPick, type SwingPicksResponse, type SwingPicksParams } from '../services/api';
import {
  Zap, RefreshCw, AlertTriangle, Eye, Target, SlidersHorizontal,
  ChevronDown, ChevronUp, ShieldAlert, FlaskConical, XIcon, RotateCcw,
  HelpCircle,
} from 'lucide-react';

// ─── Default config ───────────────────────────────────────────────────────────

const DEFAULTS: Required<SwingPicksParams> = {
  min_tqs: 80,
  min_volume_ratio: 2.0,
  min_atv_cr: 20,
  min_rr_buy: 1.0,
  min_rr_watchlist: 0.4,
  stop_atr_mult: 1.5,
  entry_atr_low: 0.5,
  entry_atr_high: 0.25,
  min_res_strength: 30,
  risk_per_trade: 0,
};

// ─── Target Reach Day calculator ─────────────────────────────────────────────

function projectDay(entry: number, target: number, atr: number, mult: number, decay: number, max = 10): number | null {
  let price = entry, speed = mult;
  for (let d = 1; d <= max; d++) {
    price += atr * speed;
    speed *= (1 - decay);
    if (price >= target) return d;
  }
  return null;
}

function addTradingDays(from: Date, n: number): Date {
  const d = new Date(from);
  let c = 0;
  while (c < n) { d.setDate(d.getDate() + 1); if (d.getDay() !== 0 && d.getDay() !== 6) c++; }
  return d;
}

const SCENARIOS = [
  { label: 'Slow',      mult: 0.40, decay: 0.10, cls: 'text-slate-400'   },
  { label: 'Normal',    mult: 0.75, decay: 0.05, cls: 'text-amber-400'   },
  { label: 'Strong',    mult: 1.00, decay: 0.03, cls: 'text-emerald-400' },
  { label: 'Explosive', mult: 1.50, decay: 0.00, cls: 'text-purple-400'  },
] as const;

interface TargetWidgetProps { entry: number; t1: number; t2: number; atr: number; today: Date; }

const TargetWidget: React.FC<TargetWidgetProps> = ({ entry, t1, t2, atr, today }) => {
  const [mult, setMult] = useState(0.75);
  const [decay, setDecay] = useState(0.05);
  const d1 = projectDay(entry, t1, atr, mult, decay);
  const d2 = projectDay(entry, t2, atr, mult, decay);
  const dayLabel = (d: number | null) => {
    if (!d) return 'Beyond 10 days';
    const dt = addTradingDays(today, d);
    return `Day ${d} — ${dt.toLocaleDateString('en-IN', { weekday: 'short', month: 'short', day: 'numeric' })}`;
  };

  return (
    <div className="flex flex-col gap-2.5 mt-3 pt-3 border-t border-border-subtle">
      <div className="flex flex-col gap-1.5">
        <div className="flex justify-between text-[10px] text-text-muted mb-0.5">
          <span>Momentum Multiplier</span>
          <span className="font-mono text-accent-primary">{mult.toFixed(2)}x ATR/day</span>
        </div>
        <input type="range" min="0.3" max="1.5" step="0.05" value={mult}
          onChange={e => setMult(parseFloat(e.target.value))} className="w-full h-1.5 accent-purple-500" />
        <div className="flex justify-between text-[9px] text-text-muted">
          <span>Drift 0.3x</span><span>Normal 0.75x</span><span>Explosive 1.5x</span>
        </div>
      </div>
      <div className="flex flex-col gap-1.5">
        <div className="flex justify-between text-[10px] text-text-muted mb-0.5">
          <span>Momentum Decay / Day</span>
          <span className="font-mono text-accent-primary">{(decay * 100).toFixed(0)}%</span>
        </div>
        <input type="range" min="0" max="0.20" step="0.01" value={decay}
          onChange={e => setDecay(parseFloat(e.target.value))} className="w-full h-1.5 accent-purple-500" />
        <div className="flex justify-between text-[9px] text-text-muted">
          <span>No decay 0%</span><span>Fast fade 20%</span>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-1.5">
        <div className="bg-emerald-950/20 border border-emerald-900/30 rounded-lg p-2">
          <p className="text-[9px] text-text-muted">Target 1</p>
          <p className="text-[10px] font-bold text-emerald-400 mt-0.5">{dayLabel(d1)}</p>
        </div>
        <div className="bg-emerald-950/10 border border-emerald-900/20 rounded-lg p-2">
          <p className="text-[9px] text-text-muted">Target 2</p>
          <p className="text-[10px] font-bold text-emerald-300 mt-0.5">{dayLabel(d2)}</p>
        </div>
      </div>
      <div className="grid grid-cols-4 gap-1">
        {SCENARIOS.map(s => {
          const sd = projectDay(entry, t1, atr, s.mult, s.decay);
          return (
            <div key={s.label} className="bg-bg-surface border border-border-subtle rounded-lg p-1.5 text-center">
              <p className={`text-[9px] font-bold ${s.cls}`}>{s.label}</p>
              <p className="text-[10px] font-mono text-text-main mt-0.5">{sd ? `D${sd}` : '>D10'}</p>
              <p className="text-[9px] text-text-muted">{s.mult}x/{(s.decay * 100).toFixed(0)}%</p>
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ─── MACD arrow label ─────────────────────────────────────────────────────────

function macdLabel(hist: number | null, slope: number | null): string {
  if (hist === null) return '';
  const sign = hist >= 0 ? '+' : '';
  const val = `${sign}${hist.toFixed(2)}`;
  if (!slope) return val;
  const dir = slope > 0 ? '▲' : '▼';
  const mag = Math.abs(slope);
  const arrows = mag > 5 ? dir.repeat(3) : mag > 1 ? dir.repeat(2) : dir;
  const tag = mag > 5 ? ' explosive' : '';
  return `${val} ${arrows}${tag}`;
}

function t1DayLabel(entry: number, t1: number, atr: number, today: Date): string {
  const d = projectDay(entry, t1, atr, 0.75, 0.05);
  if (!d) return 'Resistance pivot';
  const dt = addTradingDays(today, d);
  return `${dt.toLocaleDateString('en-IN', { weekday: 'long' })} swing target`;
}

// ─── Pick Card ────────────────────────────────────────────────────────────────

interface CardProps {
  pick: SwingPick;
  notes: Record<string, string>;
  onNote: (sym: string, note: string) => void;
  today: Date;
  onView: (sym: string) => void;
}

const PickCard: React.FC<CardProps> = ({ pick, notes, onNote, today, onView }) => {
  const [showProjection, setShowProjection] = useState(false);
  const [editNote, setEditNote] = useState(false);
  const [noteText, setNoteText] = useState(notes[pick.symbol] ?? '');
  const noteRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => { setNoteText(notes[pick.symbol] ?? ''); }, [notes, pick.symbol]);

  const fmt = (n: number) =>
    new Intl.NumberFormat('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n);
  const fmtShort = (n: number) => n.toLocaleString('en-IN', { maximumFractionDigits: 0 });

  const entry = pick.close_price;
  const sl = pick.stop_loss ?? 0;
  const t1 = pick.target_1 ?? entry * 1.15;
  const t2 = pick.target_2 ?? entry * 1.22;
  const atr = pick.atr_14 ?? entry * 0.02;
  const rr = pick.rr_ratio ?? 0;
  const qty = pick.position_size_shares ?? 0;
  const notional = qty * entry;
  const t1Pct = ((t1 - entry) / entry * 100).toFixed(1);
  const t2Pct = ((t2 - entry) / entry * 100).toFixed(1);
  const inside = entry >= (pick.entry_zone_low ?? 0) && entry <= (pick.entry_zone_high ?? Infinity);

  const note = notes[pick.symbol] ?? '';
  const hasNote = note.length > 0;
  const isNewsPlay = pick.is_news_play;

  const rrColor = rr >= 1.5 ? 'text-emerald-400' : 'text-amber-400';
  const macdColor = (pick.macd_histogram ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400';
  const cmfColor = (pick.cmf_20 ?? 0) > 0.1 ? 'text-emerald-400' : (pick.cmf_20 ?? 0) > 0 ? 'text-amber-400' : 'text-rose-400';
  const rsiColor = (pick.rsi_14 ?? 0) > 80 ? 'text-rose-400' : (pick.rsi_14 ?? 0) > 55 ? 'text-emerald-400' : 'text-text-muted';
  const slopeArrow = (s: number | null) => !s ? '' : s > 0 ? '↗' : '↘';

  return (
    <div className={`rounded-xl border bg-bg-surface/60 overflow-hidden flex flex-col border-l-4 ${
      pick.category === 'BUY'
        ? 'border-border-subtle border-l-emerald-500'
        : pick.category === 'WATCHLIST'
        ? 'border-border-subtle border-l-amber-500'
        : 'border-border-subtle border-l-rose-800 opacity-75'
    }`}>
      {/* Header */}
      <div className="flex items-start justify-between px-4 pt-4 pb-3">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-base font-extrabold text-text-main font-mono tracking-tight">{pick.symbol}</span>
            <span className="text-[10px] font-semibold text-text-muted">{pick.company_name}</span>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0 flex-wrap justify-end">
          {isNewsPlay ? (
            <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-blue-600 text-white">NEWS PLAY · BUY</span>
          ) : pick.category === 'BUY' ? (
            <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-emerald-600 text-white">BUY</span>
          ) : pick.category === 'WATCHLIST' ? (
            <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-amber-600 text-white">WATCH</span>
          ) : (
            <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-rose-900/60 text-rose-300 border border-rose-800/50">REJECTED</span>
          )}
          <span className={`text-[11px] font-bold font-mono border border-border-subtle rounded px-2 py-0.5 ${rrColor}`}>
            R:R {rr.toFixed(2)}:1
          </span>
        </div>
      </div>

      {/* News alert banner */}
      {isNewsPlay && hasNote && (
        <div className="mx-4 mb-3 px-3 py-2 rounded-lg bg-orange-950/40 border border-orange-800/40 flex items-start gap-2">
          <Zap className="w-3.5 h-3.5 text-orange-400 shrink-0 mt-0.5" />
          <p className="text-[10px] text-orange-300 leading-relaxed">{note}</p>
        </div>
      )}

      {/* Elimination reason */}
      {pick.category === 'ELIMINATED' && pick.elimination_reason && (
        <div className="mx-4 mb-3 px-3 py-2 rounded-lg bg-rose-950/30 border border-rose-800/40 flex items-center gap-2">
          <ShieldAlert className="w-3.5 h-3.5 text-rose-400 shrink-0" />
          <p className="text-[10px] text-rose-300">{pick.elimination_reason}</p>
        </div>
      )}

      {/* 5-column trade plan */}
      {pick.category !== 'ELIMINATED' && (
        <div className="grid grid-cols-5 gap-px bg-border-subtle mx-4 mb-3 rounded-lg overflow-hidden border border-border-subtle">
          {[
            {
              label: 'Entry zone',
              value: pick.entry_zone_low && pick.entry_zone_high
                ? `₹${fmtShort(pick.entry_zone_low)}–₹${fmtShort(pick.entry_zone_high)}`
                : `₹${fmt(entry)}`,
              sub: `CMP ₹${fmtShort(entry)} — ${inside ? 'inside' : 'outside'}`,
              cls: 'text-text-main',
            },
            {
              label: 'Stop loss',
              value: `₹${fmt(sl)}`,
              sub: `ATR × stop mult`,
              cls: 'text-rose-400',
            },
            {
              label: 'Target 1',
              value: `₹${fmtShort(t1)} (+${t1Pct}%)`,
              sub: t1DayLabel(entry, t1, atr, today),
              cls: 'text-emerald-400',
            },
            {
              label: 'Target 2',
              value: `₹${fmtShort(t2)} (+${t2Pct}%)`,
              sub: 'Extended target',
              cls: 'text-emerald-300',
            },
            {
              label: 'Position',
              value: qty > 0 ? `${qty} shares` : '—',
              sub: qty > 0 ? (pick.notional_capped ? `~₹${fmtShort(notional)} ⚠ capped` : `~₹${fmtShort(notional)}`) : '',
              cls: pick.notional_capped ? 'text-amber-400' : 'text-purple-400',
            },
          ].map(({ label, value, sub, cls }) => (
            <div key={label} className="bg-bg-base/40 px-2 py-2.5">
              <p className="text-[9px] text-text-muted mb-1">{label}</p>
              <p className={`text-[11px] font-bold font-mono leading-tight ${cls}`}>{value}</p>
              <p className="text-[9px] text-text-muted mt-0.5 leading-tight">{sub}</p>
            </div>
          ))}
        </div>
      )}

      {/* Intermediate resistance warning */}
      {pick.intermediate_resistance && pick.intermediate_resistance_price && (
        <div className="mx-4 mb-3 px-3 py-1.5 rounded-lg bg-amber-950/30 border border-amber-800/40 flex items-center gap-2">
          <AlertTriangle className="w-3 h-3 text-amber-400 shrink-0" />
          <p className="text-[10px] text-amber-300">
            Intermediate resistance wall at ₹{pick.intermediate_resistance_price.toLocaleString('en-IN')} — stock must break this before reaching T1
          </p>
        </div>
      )}

      {/* Indicator pills */}
      <div className="flex gap-1.5 flex-wrap px-4 mb-3">
        {pick.rsi_14 !== null && (
          <span className={`text-[10px] px-2 py-0.5 rounded border bg-bg-surface border-border-subtle font-mono ${rsiColor}`}>
            RSI {pick.rsi_14.toFixed(1)}
          </span>
        )}
        {pick.macd_histogram !== null && (
          <span className={`text-[10px] px-2 py-0.5 rounded border bg-bg-surface border-border-subtle font-mono ${macdColor}`}>
            MACD {macdLabel(pick.macd_histogram, pick.macd_histogram_slope)}
          </span>
        )}
        {pick.cmf_20 !== null && (
          <span className={`text-[10px] px-2 py-0.5 rounded border bg-bg-surface border-border-subtle font-mono ${cmfColor}`}>
            CMF {pick.cmf_20 > 0 ? '+' : ''}{pick.cmf_20.toFixed(3)}
          </span>
        )}
        {pick.volume_breakout_ratio !== null && (
          <span className="text-[10px] px-2 py-0.5 rounded border bg-bg-surface border-border-subtle font-mono text-purple-400">
            Vol {pick.volume_breakout_ratio.toFixed(2)}×
          </span>
        )}
        {pick.tqs !== null && (
          <span className="text-[10px] px-2 py-0.5 rounded border bg-bg-surface border-border-subtle font-mono text-text-main">
            TQS {pick.tqs.toFixed(0)}{pick.composite_score ? ` · Bias ${pick.composite_score.toFixed(0)}` : ''}
          </span>
        )}
        {pick.supertrend_dir && (
          <span className={`text-[10px] px-2 py-0.5 rounded border bg-bg-surface ${
            pick.supertrend_dir === 'UP' ? 'text-emerald-400 border-emerald-900/40' : 'text-rose-400 border-rose-900/40'
          }`}>
            Supertrend {pick.supertrend_dir}
          </span>
        )}
      </div>

      {/* Support trendline row */}
      {(pick.support_score !== null || pick.support_slope_pct !== null) && (
        <div className="flex items-center gap-4 px-4 mb-3 text-[10px] text-text-muted">
          {pick.support_score !== null && (
            <span>
              Support score <span className="text-text-main font-mono">{pick.support_score.toFixed(1)}</span>
              {pick.support_touch_count !== null && (
                <> · <span className="text-text-main font-mono">{pick.support_touch_count}</span> touches</>
              )}
            </span>
          )}
          {pick.support_slope_pct !== null && (
            <span>
              Support slope{' '}
              <span className={`font-mono ${pick.support_slope_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {pick.support_slope_pct >= 0 ? '+' : ''}{pick.support_slope_pct.toFixed(3)}%/day {slopeArrow(pick.support_slope_pct)}
              </span>
            </span>
          )}
        </div>
      )}

      {/* Catalyst note */}
      <div className="mx-4 mb-3">
        {editNote ? (
          <div className="border-l-2 border-amber-500 pl-3 bg-amber-950/20 rounded-r-lg p-2">
            <textarea
              ref={noteRef}
              rows={3}
              value={noteText}
              onChange={e => setNoteText(e.target.value)}
              placeholder="Add news catalyst, order wins, analyst coverage, or notes…"
              autoFocus
              className="w-full text-[10px] bg-transparent text-text-main resize-none outline-none placeholder-text-muted leading-relaxed"
            />
            <div className="flex gap-2 mt-1.5">
              <button onClick={() => { onNote(pick.symbol, noteText); setEditNote(false); }}
                className="text-[9px] text-emerald-400 font-bold hover:text-emerald-300">Save</button>
              <button onClick={() => { setNoteText(note); setEditNote(false); }}
                className="text-[9px] text-text-muted hover:text-text-main">Cancel</button>
            </div>
          </div>
        ) : (
          <div
            onClick={() => setEditNote(true)}
            className={`border-l-2 pl-3 rounded-r-lg p-2 cursor-pointer transition-colors ${
              hasNote
                ? 'border-amber-500 bg-amber-950/20 hover:bg-amber-950/30'
                : 'border-border-subtle bg-bg-surface/20 hover:bg-bg-surface/40'
            }`}
          >
            {hasNote ? (
              <p className="text-[10px] text-amber-300/90 leading-relaxed">
                <span className="text-text-muted mr-1">📋 Catalyst:</span>{note}
              </p>
            ) : (
              <p className="text-[10px] text-text-muted italic">+ Add news catalyst or trade note…</p>
            )}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between px-4 pb-3 border-t border-border-subtle pt-3">
        <button onClick={() => setShowProjection(v => !v)}
          className="flex items-center gap-1.5 text-[10px] font-bold text-accent-primary hover:opacity-80 transition">
          <Target className="w-3 h-3" />
          Target Reach Day
          {showProjection ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        </button>
        <button onClick={() => onView(pick.symbol)}
          className="flex items-center gap-1 text-[10px] text-text-muted hover:text-text-main transition">
          <Eye className="w-3 h-3" />
          View in Explorer
        </button>
      </div>

      {showProjection && pick.category !== 'ELIMINATED' && (
        <div className="px-4 pb-4">
          <TargetWidget entry={entry} t1={t1} t2={t2} atr={atr} today={today} />
        </div>
      )}
    </div>
  );
};

// ─── Help Modal ───────────────────────────────────────────────────────────────

interface HelpRow {
  name: string;
  what: string;
  higher: string;
  lower: string;
  goodDirection: 'higher' | 'lower' | 'both';
  affectsCount: boolean;
}

const HELP_SECTIONS: { title: string; intro: string; rows: HelpRow[] }[] = [
  {
    title: 'Screening Filters — who gets in',
    intro: 'These run first and decide which stocks even enter the pipeline. Change these to control the size of your stock universe.',
    rows: [
      {
        name: 'Min TQS (Trend Quality Score)',
        what: 'Measures how clean and consistent the uptrend is. A stock scoring 90 has a smoother, stronger trend than one scoring 60.',
        higher: 'Fewer stocks, but each one is in a very strong confirmed uptrend. Great for high-conviction trading.',
        lower: 'More stocks enter the pipeline including early-stage or choppy trends. Better for discovery.',
        goodDirection: 'higher',
        affectsCount: true,
      },
      {
        name: 'Min Volume Ratio',
        what: 'Compares today\'s volume to the stock\'s average. A ratio of 3× means the stock traded 3 times its normal volume — someone is accumulating.',
        higher: 'Only stocks with strong institutional-sized volume activity. Fewer but higher conviction.',
        lower: 'Includes stocks with moderate volume pickup. Wider net but weaker confirmation.',
        goodDirection: 'higher',
        affectsCount: true,
      },
      {
        name: 'Min ATV (Avg Traded Value ₹Cr)',
        what: 'Average daily rupee traded value. Low ATV stocks are illiquid — hard to enter or exit without moving the price against you.',
        higher: 'Only liquid mid/large caps. Easier to trade, safer exits.',
        lower: 'Includes smaller, less liquid stocks. Higher potential but higher slippage risk.',
        goodDirection: 'higher',
        affectsCount: true,
      },
    ],
  },
  {
    title: 'Classification Thresholds — BUY vs WATCH vs ELIMINATED',
    intro: 'These don\'t change how many stocks appear — they decide which category each stock lands in. All stocks still show; they just get reclassified.',
    rows: [
      {
        name: 'BUY Min R:R',
        what: 'Risk-to-Reward ratio required for a BUY label. R:R of 1.5 means the stock can gain ₹1.50 for every ₹1 risked.',
        higher: 'Fewer BUY picks, but each has a much better potential payout vs risk.',
        lower: 'More stocks get the BUY label. Useful if you want a wider selection but quality drops.',
        goodDirection: 'higher',
        affectsCount: false,
      },
      {
        name: 'WATCHLIST Min R:R',
        what: 'The floor R:R before a stock is rejected outright. Below this, the risk is not worth taking at any entry.',
        higher: 'Stricter — more stocks get ELIMINATED instead of WATCHLIST.',
        lower: 'More permissive — more stocks stay in WATCHLIST even with poor setups.',
        goodDirection: 'higher',
        affectsCount: false,
      },
    ],
  },
  {
    title: 'Trade Plan Parameters — how the numbers are calculated',
    intro: 'These change the stop loss, entry zone, and target calculations on each card. They can indirectly move a stock between BUY/WATCH/ELIMINATED by changing its R:R.',
    rows: [
      {
        name: 'Stop ATR Multiplier',
        what: 'Sets how far below the support level your stop loss is placed. ATR is the stock\'s average daily range — a multiplier of 1.5 means stop = support minus 1.5 days\' range.',
        higher: 'Wider stop. Less chance of being stopped out by normal noise, but position size (shares) is smaller.',
        lower: 'Tighter stop. Larger position size but more likely to get stopped out prematurely.',
        goodDirection: 'both',
        affectsCount: false,
      },
      {
        name: 'Entry Zone Low',
        what: 'How far below CMP the bottom of the buy zone extends. Expressed as a multiple of ATR.',
        higher: 'Wider zone below — allows you to enter on a deeper pullback.',
        lower: 'Tighter zone — only enter very close to current price.',
        goodDirection: 'both',
        affectsCount: false,
      },
      {
        name: 'Entry Zone High',
        what: 'How far above CMP the top of the buy zone extends. Higher means you\'re willing to chase slightly.',
        higher: 'Wider zone above — allows chasing a breakout. Increases chasing risk.',
        lower: 'Don\'t chase — only buy at or slightly above current price.',
        goodDirection: 'lower',
        affectsCount: false,
      },
      {
        name: 'Risk Per Trade ₹',
        what: 'How much money you\'re willing to lose if the stock hits your stop. This determines how many shares you buy. Set to 0 to use your Settings default.',
        higher: 'Larger position sizes (more shares per trade).',
        lower: 'Smaller positions, more conservative sizing.',
        goodDirection: 'both',
        affectsCount: false,
      },
    ],
  },
  {
    title: 'Advanced — resistance target quality',
    intro: 'Controls which resistance levels are used as price targets.',
    rows: [
      {
        name: 'Min Resistance Strength',
        what: 'Each resistance level has a strength score (0–100) based on how many times price has bounced from it, volume at the level, and how it aligns with pivots. Higher score = more reliable level.',
        higher: 'Only use well-tested, high-confidence resistance as T1/T2 targets. More conservative targets, but more reliable.',
        lower: 'Use any nearby resistance even if weakly tested. Targets may be optimistic.',
        goodDirection: 'higher',
        affectsCount: false,
      },
    ],
  },
];

const HelpModal: React.FC<{ onClose: () => void }> = ({ onClose }) => (
  <div
    className="fixed inset-0 z-50 flex items-center justify-center p-4"
    style={{ backgroundColor: 'rgba(0,0,0,0.7)' }}
    onClick={e => { if (e.target === e.currentTarget) onClose(); }}
  >
    <div className="bg-bg-base border border-border-subtle rounded-2xl w-full max-w-2xl max-h-[85vh] flex flex-col overflow-hidden shadow-2xl">
      {/* Modal header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-border-subtle shrink-0">
        <div className="flex items-center gap-2">
          <HelpCircle className="w-4 h-4 text-accent-primary" />
          <h2 className="text-sm font-extrabold text-text-main">How Filters Work</h2>
        </div>
        <button onClick={onClose} className="text-text-muted hover:text-text-main transition">
          <XIcon className="w-4 h-4" />
        </button>
      </div>

      {/* Scrollable body */}
      <div className="overflow-y-auto flex-1 px-5 py-4 flex flex-col gap-6">

        {/* Key concept banner */}
        <div className="rounded-xl border border-purple-800/40 bg-purple-950/20 px-4 py-3">
          <p className="text-[11px] text-purple-300 font-semibold mb-1">Important to understand</p>
          <p className="text-[10px] text-text-muted leading-relaxed">
            After changing any filter value, you <span className="text-text-main font-bold">must click Run Pipeline</span> for it to take effect.
            Filters don't auto-run. The number of stocks you see depends on your database snapshot — filters can only work with what's already been synced.
          </p>
        </div>

        {HELP_SECTIONS.map(section => (
          <div key={section.title} className="flex flex-col gap-3">
            <div>
              <h3 className="text-[11px] font-bold text-text-main uppercase tracking-wider">{section.title}</h3>
              <p className="text-[10px] text-text-muted mt-1 leading-relaxed">{section.intro}</p>
            </div>

            {section.rows.map(row => (
              <div key={row.name} className="border border-border-subtle rounded-xl overflow-hidden">
                {/* Filter name */}
                <div className="flex items-center justify-between px-3 py-2.5 bg-bg-surface/60">
                  <span className="text-[11px] font-bold text-text-main">{row.name}</span>
                  <div className="flex items-center gap-1.5">
                    {row.affectsCount ? (
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-blue-950/50 border border-blue-800/40 text-blue-300 font-bold">
                        Changes stock count
                      </span>
                    ) : (
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-bg-base border border-border-subtle text-text-muted">
                        Reclassifies only
                      </span>
                    )}
                  </div>
                </div>

                {/* What it does */}
                <div className="px-3 py-2 border-t border-border-subtle">
                  <p className="text-[10px] text-text-muted leading-relaxed">{row.what}</p>
                </div>

                {/* Higher / Lower grid */}
                <div className="grid grid-cols-2 gap-px bg-border-subtle border-t border-border-subtle">
                  <div className={`px-3 py-2.5 ${row.goodDirection === 'higher' ? 'bg-emerald-950/20' : 'bg-bg-base/40'}`}>
                    <div className="flex items-center gap-1 mb-1">
                      <span className="text-[10px] font-bold text-text-muted">Higher value</span>
                      {row.goodDirection === 'higher' && (
                        <span className="text-[9px] text-emerald-400 font-bold">✓ recommended</span>
                      )}
                    </div>
                    <p className="text-[10px] text-text-muted leading-relaxed">{row.higher}</p>
                  </div>
                  <div className={`px-3 py-2.5 ${row.goodDirection === 'lower' ? 'bg-emerald-950/20' : 'bg-bg-base/40'}`}>
                    <div className="flex items-center gap-1 mb-1">
                      <span className="text-[10px] font-bold text-text-muted">Lower value</span>
                      {row.goodDirection === 'lower' && (
                        <span className="text-[9px] text-emerald-400 font-bold">✓ recommended</span>
                      )}
                    </div>
                    <p className="text-[10px] text-text-muted leading-relaxed">{row.lower}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ))}

        {/* Footer tip */}
        <div className="rounded-xl border border-amber-800/30 bg-amber-950/20 px-4 py-3">
          <p className="text-[10px] text-amber-300 leading-relaxed">
            <span className="font-bold">Tip for finding more stocks:</span> Lower TQS to 60, Volume Ratio to 1.5, and ATV to 10Cr — then click Run Pipeline.
            You'll see more candidates, including earlier-stage setups. Tighten filters again once you've identified your watchlist.
          </p>
        </div>
      </div>
    </div>
  </div>
);

// ─── Config Panel ─────────────────────────────────────────────────────────────

interface SliderRowProps {
  label: string;
  hint: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
  format?: (v: number) => string;
}

const SliderRow: React.FC<SliderRowProps> = ({ label, hint, value, min, max, step, onChange, format }) => (
  <div className="flex flex-col gap-1">
    <div className="flex justify-between text-[10px]">
      <span className="text-text-muted">{label}</span>
      <span className="font-mono text-accent-primary">{format ? format(value) : value}</span>
    </div>
    <input type="range" min={min} max={max} step={step} value={value}
      onChange={e => onChange(parseFloat(e.target.value))}
      className="w-full h-1.5 accent-purple-500" />
    <p className="text-[9px] text-text-muted">{hint}</p>
  </div>
);

interface ConfigGroup {
  title: string;
  children: React.ReactNode;
}

const ConfigSection: React.FC<ConfigGroup> = ({ title, children }) => {
  const [open, setOpen] = useState(true);
  return (
    <div className="border border-border-subtle rounded-lg overflow-hidden">
      <button onClick={() => setOpen(v => !v)}
        className="w-full flex items-center justify-between px-3 py-2 bg-bg-surface/60 text-[10px] font-bold text-text-muted uppercase tracking-wider hover:text-text-main transition">
        {title}
        {open ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
      </button>
      {open && <div className="px-3 py-3 flex flex-col gap-3">{children}</div>}
    </div>
  );
};

// ─── Main Panel ───────────────────────────────────────────────────────────────

const NOTES_KEY = 'vajra_swing_picks_notes';
const loadLocalNotes = (): Record<string, string> => {
  try { return JSON.parse(localStorage.getItem(NOTES_KEY) || '{}'); } catch { return {}; }
};

export const SwingPicksPanel: React.FC = () => {
  const { setActiveTab, setSelectedSymbol, qualifyQueue, clearQualifyQueue } = useStockStore();

  const [data, setData]         = useState<SwingPicksResponse | null>(null);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState<string | null>(null);
  const [mode, setMode]         = useState<'pipeline' | 'manual'>('pipeline');
  const [manualInput, setManualInput] = useState('');
  const [notes, setNotes]       = useState<Record<string, string>>(loadLocalNotes);
  const [showConfig, setShowConfig] = useState(false);
  const [showHelp, setShowHelp]     = useState(false);
  const [config, setConfig]     = useState<Required<SwingPicksParams>>({ ...DEFAULTS });

  const today = new Date();

  // Load notes from DB on mount, merge with localStorage fallback
  useEffect(() => {
    apiService.getSwingNotes().then(dbNotes => {
      setNotes(prev => ({ ...prev, ...dbNotes }));
    });
  }, []);

  const set = <K extends keyof SwingPicksParams>(k: K, v: number) =>
    setConfig(c => ({ ...c, [k]: v }));

  const resetConfig = () => setConfig({ ...DEFAULTS });

  const saveNote = async (sym: string, note: string) => {
    const updated = { ...notes, [sym]: note };
    setNotes(updated);
    localStorage.setItem(NOTES_KEY, JSON.stringify(updated));
    await apiService.saveSwingNote(sym, note);
  };

  const handleView = async (symbol: string) => {
    await setSelectedSymbol(`${symbol}.NS`);
    setActiveTab('explorer');
  };

  const runPipeline = useCallback(async () => {
    setLoading(true); setError(null); setMode('pipeline');
    try {
      setData(await apiService.getSwingPicks(config));
    } catch (e: any) {
      setError(e?.message ?? 'Pipeline failed. Ensure backend is running and data is synced.');
    } finally { setLoading(false); }
  }, [config]);

  const runManual = useCallback(async (symbols: string[]) => {
    if (!symbols.length) return;
    setLoading(true); setError(null); setMode('manual');
    try {
      setData(await apiService.qualifyStocks(symbols, config));
    } catch (e: any) {
      setError(e?.message ?? 'Qualify failed.');
    } finally { setLoading(false); }
  }, [config]);

  useEffect(() => { runPipeline(); }, []);

  const hasQueue = qualifyQueue.length > 0;

  const handleQualifyQueue = () => { runManual(qualifyQueue); clearQualifyQueue(); };
  const handleQualifyManual = () => {
    const syms = manualInput.split(/[\s,\n]+/).map(s => s.trim().toUpperCase()).filter(Boolean);
    runManual(syms);
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {showHelp && <HelpModal onClose={() => setShowHelp(false)} />}
      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">

        {/* ── Controls ── */}
        <div className="rounded-xl border border-border-subtle bg-bg-surface/60 p-4 flex flex-col gap-3">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div>
              <h2 className="text-sm font-extrabold text-text-main flex items-center gap-2">
                <Zap className="w-4 h-4 text-accent-primary" />
                Swing Trade Picks
                {mode === 'manual' && data && (
                  <span className="text-[10px] text-text-muted font-normal bg-bg-base/40 px-2 py-0.5 rounded border border-border-subtle">
                    Manual Qualify
                  </span>
                )}
              </h2>
              <p className="text-[10px] text-text-muted mt-0.5">
                {mode === 'pipeline'
                  ? `Stage 2 · TQS ≥ ${config.min_tqs} · Vol ≥ ${config.min_volume_ratio}x · ATV ≥ ₹${config.min_atv_cr}Cr · R:R BUY ≥ ${config.min_rr_buy}`
                  : 'Qualifying selected stocks through trade plan pipeline'}
              </p>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              {data && (
                <span className="text-[10px] text-text-muted">
                  {new Date(data.run_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
                  {mode === 'pipeline' && ` · ${data.summary.total_screened} screened`}
                </span>
              )}
              <button onClick={() => setShowHelp(true)} title="How filters work"
                className="p-1.5 rounded-lg border border-border-subtle text-text-muted hover:text-text-main transition">
                <HelpCircle className="w-3.5 h-3.5" />
              </button>
              <button onClick={() => setShowConfig(v => !v)} title="Configure pipeline"
                className={`p-1.5 rounded-lg border transition ${showConfig ? 'border-accent-primary text-accent-primary' : 'border-border-subtle text-text-muted hover:text-text-main'}`}>
                <SlidersHorizontal className="w-3.5 h-3.5" />
              </button>
              <button onClick={runPipeline} disabled={loading}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent-primary text-accent-text text-xs font-bold hover:opacity-90 transition disabled:opacity-50">
                <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                {loading ? 'Running…' : 'Run Pipeline'}
              </button>
            </div>
          </div>

          {/* Pipeline step counter */}
          {data && mode === 'pipeline' && (
            <div className="flex items-center gap-3 flex-wrap">
              {[
                `${data.summary.total_screened} passed screen`,
                `${data.summary.buy_count + data.summary.watchlist_count} qualified`,
                `${data.summary.buy_count} BUY · ${data.summary.watchlist_count} Watch · ${data.summary.eliminated_count} Eliminated`,
              ].map((label, i) => (
                <div key={i} className="flex items-center gap-1.5">
                  <span className="w-4 h-4 rounded-full flex items-center justify-center text-[9px] font-bold bg-emerald-950/40 text-emerald-400 border border-emerald-900/40">{i + 1}</span>
                  <span className="text-[10px] text-text-muted">{label}</span>
                  {i < 2 && <span className="text-border-subtle">→</span>}
                </div>
              ))}
            </div>
          )}

          {/* Config panel */}
          {showConfig && (
            <div className="border-t border-border-subtle pt-3 flex flex-col gap-3">
              <div className="flex justify-between items-center">
                <p className="text-[10px] font-bold text-text-muted uppercase tracking-wider">Pipeline Configuration</p>
                <button onClick={resetConfig}
                  className="flex items-center gap-1 text-[10px] text-text-muted hover:text-text-main transition">
                  <RotateCcw className="w-3 h-3" />
                  Reset to Defaults
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <ConfigSection title="Screening Filters">
                  <SliderRow label="Min TQS" hint="Trend Quality Score (0–100)" value={config.min_tqs} min={0} max={100} step={5}
                    onChange={v => set('min_tqs', v)} />
                  <SliderRow label="Min Volume Ratio" hint="Volume vs average (1×–5×)" value={config.min_volume_ratio} min={1} max={5} step={0.5}
                    onChange={v => set('min_volume_ratio', v)} format={v => `${v}×`} />
                  <div>
                    <div className="flex justify-between text-[10px] mb-1">
                      <span className="text-text-muted">Min ATV (₹Cr)</span>
                      <span className="font-mono text-accent-primary">₹{config.min_atv_cr}Cr</span>
                    </div>
                    <input type="number" min={0} max={500} step={5} value={config.min_atv_cr}
                      onChange={e => set('min_atv_cr', parseFloat(e.target.value) || 0)}
                      className="w-full text-xs bg-bg-base border border-border-subtle rounded px-2 py-1 text-text-main" />
                  </div>
                </ConfigSection>

                <ConfigSection title="Classification Thresholds">
                  <SliderRow label="BUY min R:R" hint="Supertrend UP + R:R ≥ this → BUY" value={config.min_rr_buy} min={0.5} max={3.0} step={0.1}
                    onChange={v => set('min_rr_buy', v)} format={v => `${v.toFixed(1)}:1`} />
                  <SliderRow label="WATCHLIST min R:R" hint="Below this → ELIMINATED" value={config.min_rr_watchlist} min={0.1} max={1.0} step={0.1}
                    onChange={v => set('min_rr_watchlist', v)} format={v => `${v.toFixed(1)}:1`} />
                </ConfigSection>

                <ConfigSection title="Trade Plan Parameters">
                  <SliderRow label="Stop ATR Multiplier" hint="Stop = support − N×ATR" value={config.stop_atr_mult} min={1.0} max={3.0} step={0.25}
                    onChange={v => set('stop_atr_mult', v)} format={v => `${v.toFixed(2)}×`} />
                  <SliderRow label="Entry Zone Low" hint="Zone low = CMP − N×ATR" value={config.entry_atr_low} min={0.25} max={1.5} step={0.25}
                    onChange={v => set('entry_atr_low', v)} format={v => `${v.toFixed(2)}×`} />
                  <SliderRow label="Entry Zone High" hint="Zone high = CMP + N×ATR" value={config.entry_atr_high} min={0.1} max={0.75} step={0.1}
                    onChange={v => set('entry_atr_high', v)} format={v => `${v.toFixed(2)}×`} />
                  <div>
                    <div className="flex justify-between text-[10px] mb-1">
                      <span className="text-text-muted">Risk per trade ₹</span>
                      <span className="font-mono text-accent-primary">
                        {config.risk_per_trade > 0 ? `₹${config.risk_per_trade.toLocaleString('en-IN')}` : 'From settings'}
                      </span>
                    </div>
                    <input type="number" min={0} step={500} value={config.risk_per_trade}
                      onChange={e => set('risk_per_trade', parseFloat(e.target.value) || 0)}
                      placeholder="0 = use settings default"
                      className="w-full text-xs bg-bg-base border border-border-subtle rounded px-2 py-1 text-text-main placeholder-text-muted" />
                  </div>
                </ConfigSection>

                <ConfigSection title="Advanced">
                  <SliderRow label="Min Resistance Strength" hint="Floor score for T1 selection (0–60). Higher = only strong levels used as targets" value={config.min_res_strength} min={0} max={60} step={10}
                    onChange={v => set('min_res_strength', v)} />
                </ConfigSection>
              </div>
            </div>
          )}
        </div>

        {/* ── Screener queue banner ── */}
        {hasQueue && (
          <div className="rounded-xl border border-purple-800/50 bg-purple-950/20 p-3 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 flex-wrap">
              <FlaskConical className="w-4 h-4 text-purple-400" />
              <span className="text-xs text-text-main font-semibold">
                {qualifyQueue.length} stock{qualifyQueue.length !== 1 ? 's' : ''} queued from Screener
              </span>
              <span className="text-[10px] text-text-muted font-mono">
                {qualifyQueue.map(s => s.replace('.NS', '')).join(', ')}
              </span>
            </div>
            <div className="flex gap-2">
              <button onClick={handleQualifyQueue} disabled={loading}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-purple-600 text-white text-xs font-bold hover:bg-purple-500 transition disabled:opacity-50">
                <Zap className="w-3.5 h-3.5" />
                Qualify These {qualifyQueue.length}
              </button>
              <button onClick={clearQualifyQueue} className="p-1.5 text-text-muted hover:text-text-main transition">
                <XIcon className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}

        {/* ── Manual qualify input ── */}
        <div className="rounded-xl border border-border-subtle bg-bg-surface/40 p-4 flex flex-col gap-2">
          <label className="text-[10px] text-text-muted font-bold uppercase tracking-wider flex items-center gap-1.5">
            <FlaskConical className="w-3 h-3" />
            Qualify Specific Stocks
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              value={manualInput}
              onChange={e => setManualInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleQualifyManual()}
              placeholder="GALAPREC, KIRLOSENG, WABAG…"
              className="flex-1 text-xs bg-bg-base border border-border-subtle rounded-lg px-3 py-2 text-text-main placeholder-text-muted focus:outline-none focus:border-accent-primary"
            />
            <button onClick={handleQualifyManual} disabled={loading || !manualInput.trim()}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-bg-surface border border-border-subtle text-xs font-bold text-text-main hover:border-accent-primary transition disabled:opacity-40">
              <FlaskConical className="w-3.5 h-3.5" />
              Qualify
            </button>
          </div>
          <p className="text-[9px] text-text-muted">Separate with commas or spaces. Enter to run. Uses current config above.</p>
        </div>

        {/* ── Error ── */}
        {error && (
          <div className="rounded-xl border border-rose-900/40 bg-rose-950/20 p-3 flex items-center gap-2 text-xs text-rose-400">
            <AlertTriangle className="w-4 h-4 shrink-0" />{error}
          </div>
        )}

        {/* ── Loading ── */}
        {loading && (
          <div className="flex flex-col items-center justify-center py-16 gap-3 text-text-muted">
            <RefreshCw className="w-7 h-7 animate-spin text-accent-primary" />
            <p className="text-sm">Running pipeline…</p>
          </div>
        )}

        {/* ── Results ── */}
        {!loading && data && (
          <>
            {data.buy_picks.length > 0 && (
              <section className="flex flex-col gap-3">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 shrink-0" />
                  <h3 className="text-xs font-bold text-text-main">
                    Actionable BUY
                    <span className="ml-2 text-[10px] text-text-muted font-normal">{data.buy_picks.length} stock{data.buy_picks.length !== 1 ? 's' : ''}</span>
                  </h3>
                </div>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  {data.buy_picks.map(p => (
                    <PickCard key={p.symbol} pick={p} notes={notes} onNote={saveNote} today={today} onView={handleView} />
                  ))}
                </div>
              </section>
            )}

            {data.watchlist.length > 0 && (
              <section className="flex flex-col gap-3">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-amber-500 shrink-0" />
                  <h3 className="text-xs font-bold text-text-main">
                    Watchlist — wait for better entry
                    <span className="ml-2 text-[10px] text-text-muted font-normal">{data.watchlist.length} stock{data.watchlist.length !== 1 ? 's' : ''}</span>
                  </h3>
                </div>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  {data.watchlist.map(p => (
                    <PickCard key={p.symbol} pick={p} notes={notes} onNote={saveNote} today={today} onView={handleView} />
                  ))}
                </div>
              </section>
            )}

            {data.eliminated.length > 0 && (
              <section className="flex flex-col gap-3">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-rose-700 shrink-0" />
                  <h3 className="text-xs font-bold text-text-main">
                    Eliminated — no entry
                    <span className="ml-2 text-[10px] text-text-muted font-normal">{data.eliminated.length} stock{data.eliminated.length !== 1 ? 's' : ''}</span>
                  </h3>
                </div>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  {data.eliminated.map(p => (
                    <PickCard key={p.symbol} pick={p} notes={notes} onNote={saveNote} today={today} onView={handleView} />
                  ))}
                </div>
              </section>
            )}

            {data.buy_picks.length === 0 && data.watchlist.length === 0 && data.eliminated.length === 0 && (
              <div className="text-center py-16 text-text-muted text-sm">
                No qualifying stocks found. Try lowering TQS or Volume Ratio in the config panel.
              </div>
            )}
          </>
        )}

        {!loading && !data && !error && (
          <div className="flex flex-col items-center justify-center py-20 gap-3 text-text-muted">
            <Zap className="w-10 h-10 text-border-subtle" />
            <p className="text-sm">Click <strong className="text-text-muted">Run Pipeline</strong> to start screening.</p>
          </div>
        )}

        {/* Methodology footer */}
        <div className="rounded-xl border border-border-subtle bg-bg-surface/30 p-3">
          <p className="text-[9px] text-text-muted leading-relaxed">
            <strong className="text-text-muted">Methodology:</strong> BUY requires Supertrend UP + R:R ≥ configured threshold + no resistance trendline ceiling.
            Stop = structural support − stop_atr_mult × ATR. Entry zone = CMP ± ATR × configured factors.
            Target Reach Day uses ATR momentum projection — not a performance guarantee. <strong>Not investment advice.</strong>
          </p>
        </div>

      </div>
    </div>
  );
};
