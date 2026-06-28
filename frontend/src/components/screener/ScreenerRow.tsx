import React from 'react';
import { Bookmark, TrendingUp, Zap } from 'lucide-react';
import type { ScreenerRow as ScreenerRowType, StrategyMeta } from '../../services/api';
import { STRAT_SIG_STYLE, stratCode } from './constants';

export const formatNumber = (val: number | null | undefined, decimals = 2) => {
  if (val === null || val === undefined) return '-';
  return Number(val).toFixed(decimals);
};

export const formatTradedValue = (val: number | null | undefined) => {
  if (val === null || val === undefined) return '-';
  const cr = val / 1e7;
  if (cr >= 100) return `${cr.toFixed(0)} Cr`;
  if (cr >= 1) return `${cr.toFixed(2)} Cr`;
  const lakh = val / 1e5;
  return `${lakh.toFixed(1)} L`;
};

interface Props {
  row: ScreenerRowType;
  strategies: StrategyMeta[];
  onAddToWatchlist: (symbol: string) => void;
  onOpenChart: (symbol: string) => void;
  onAddToQualify: (symbol: string) => void;
  qualifyQueue: string[];
}

export const ScreenerRow: React.FC<Props> = ({ row, strategies, onAddToWatchlist, onOpenChart, onAddToQualify, qualifyQueue }) => {
  const isChangeBullish = (row.price_pct_change || 0) >= 0;
  const isHaBullish = row.ha_direction === 'UP';
  const isRenkoBullish = row.renko_direction === 'UP';
  const isLbBullish = row.line_break_direction === 'UP';

  return (
    <tr key={row.symbol_id} className="hover:bg-slate-900/40 transition whitespace-nowrap text-xs">
      {/* Actions — pinned left */}
      <td className="py-2 px-2">
        <div className="flex items-center gap-1 flex-nowrap">
          <button
            onClick={() => onAddToWatchlist(row.symbol)}
            title="Add to Watchlist"
            className="p-1 rounded bg-bg-surface border border-border-subtle hover:border-indigo-500/80 text-text-muted hover:text-indigo-400 flex items-center transition cursor-pointer shrink-0"
          >
            <Bookmark className="w-3 h-3" />
          </button>
          <button
            onClick={() => onOpenChart(row.symbol)}
            title="Quick Chart View"
            className="py-1 px-2 rounded bg-bg-surface border border-border-subtle hover:border-indigo-500/80 text-text-muted hover:text-text-main text-[11px] flex items-center gap-1 transition cursor-pointer shrink-0"
          >
            <TrendingUp className="w-3 h-3" />
            Chart
          </button>
          <button
            onClick={() => onAddToQualify(row.symbol)}
            title="Add to Swing Pick qualifier"
            className={`py-1 px-2 rounded border text-[11px] flex items-center gap-1 transition cursor-pointer shrink-0 ${
              qualifyQueue.includes(row.symbol)
                ? 'bg-purple-900/40 border-purple-600/60 text-purple-300'
                : 'bg-bg-surface border-border-subtle hover:border-purple-500/80 text-text-muted hover:text-purple-400'
            }`}
          >
            <Zap className="w-3 h-3" />
            {qualifyQueue.includes(row.symbol) ? '✓' : 'Pick'}
          </button>
        </div>
      </td>
      {/* Ticker */}
      <td className="py-2 px-1.5 font-bold text-text-main font-mono">
        <div className="flex flex-col gap-0.5">
          {row.symbol.replace('.NS', '')}
          <div className="flex gap-0.5 flex-wrap">
            {row.is_vajraturn && (
              <span className="text-[8px] font-bold px-1 py-px rounded bg-purple-900/50 border border-purple-500/40 text-purple-300 leading-none" title="VajraTurn — early reversal near rising SMA200">VT</span>
            )}
            {row.is_bb_squeeze && (
              <span className="text-[8px] font-bold px-1 py-px rounded bg-amber-900/40 border border-amber-500/40 text-amber-300 leading-none" title="BB Squeeze — bandwidth at 20-day low">SQ</span>
            )}
            {row.weinstein_stage === 2 && (
              <span className="text-[8px] font-bold px-1 py-px rounded bg-emerald-900/40 border border-emerald-500/40 text-emerald-300 leading-none" title="Weinstein Stage 2 — Markup phase">S2</span>
            )}
          </div>
        </div>
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

      {/* Trend Quality Score */}
      <td className="py-2 px-1 text-right font-mono text-xs">
        {row.tqs != null ? (
          <span className={`px-1 rounded font-bold ${
            row.tqs >= 70
              ? 'text-emerald-400 bg-emerald-950/20'
              : row.tqs >= 50
              ? 'text-amber-400 bg-amber-950/20'
              : 'text-rose-400 bg-rose-950/20'
          }`}>
            {row.tqs.toFixed(0)}
          </span>
        ) : <span className="text-slate-600">—</span>}
      </td>

      {/* Weinstein Stage */}
      <td className="py-2 px-1 text-center font-mono text-xs">
        {row.weinstein_stage != null ? (
          <span className={`px-1.5 py-0.5 rounded font-bold text-[10px] ${
            row.weinstein_stage === 2
              ? 'text-emerald-400 bg-emerald-950/20'
              : row.weinstein_stage === 1
              ? 'text-amber-400 bg-amber-950/20'
              : row.weinstein_stage === 3
              ? 'text-orange-400 bg-orange-950/20'
              : 'text-rose-400 bg-rose-950/20'
          }`} title={
            row.weinstein_stage === 1 ? 'Stage 1 — Basing'
            : row.weinstein_stage === 2 ? 'Stage 2 — Markup'
            : row.weinstein_stage === 3 ? 'Stage 3 — Topping'
            : 'Stage 4 — Decline'
          }>
            S{row.weinstein_stage}
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

      {/* Hilega-Milega — days since RSI crossed above WMA */}
      <td className="py-2 px-1 text-center">
        {row.hilega_milega_signal != null ? (
          <span className={`text-[10px] font-bold px-1.5 py-px rounded border leading-none ${
            row.hilega_milega_signal <= 3
              ? 'text-emerald-200 bg-emerald-950/40 border-emerald-600/50'
              : row.hilega_milega_signal <= 10
              ? 'text-emerald-400 bg-emerald-950/20 border-emerald-700/30'
              : 'text-emerald-600 bg-emerald-950/10 border-emerald-800/20'
          }`} title={`HM: RSI in buy zone for ${row.hilega_milega_signal} day(s) since crossover above 21-WMA`}>
            {row.hilega_milega_signal}d
          </span>
        ) : <span className="text-slate-700">—</span>}
      </td>

      {/* RSI Divergence — days since bullish divergence */}
      <td className="py-2 px-1 text-center">
        {row.rsi_divergence != null ? (
          <span className={`text-[10px] font-bold px-1 py-px rounded border leading-none ${
            row.rsi_divergence <= 5
              ? 'text-violet-200 bg-violet-950/40 border-violet-600/50'
              : row.rsi_divergence <= 14
              ? 'text-violet-400 bg-violet-950/20 border-violet-700/30'
              : 'text-violet-600 bg-violet-950/10 border-violet-800/20'
          }`} title={`RSI bullish divergence: swing low formed ${row.rsi_divergence} day(s) ago`}>
            {row.rsi_divergence}d
          </span>
        ) : <span className="text-slate-700">—</span>}
      </td>

      {/* MACD Divergence — days since bullish divergence */}
      <td className="py-2 px-1 text-center">
        {row.macd_divergence != null ? (
          <span className={`text-[10px] font-bold px-1 py-px rounded border leading-none ${
            row.macd_divergence <= 5
              ? 'text-amber-200 bg-amber-950/40 border-amber-600/50'
              : row.macd_divergence <= 14
              ? 'text-amber-400 bg-amber-950/20 border-amber-700/30'
              : 'text-amber-600 bg-amber-950/10 border-amber-800/20'
          }`} title={`MACD bullish divergence: swing low formed ${row.macd_divergence} day(s) ago`}>
            {row.macd_divergence}d
          </span>
        ) : <span className="text-slate-700">—</span>}
      </td>

      {/* ZLEMA-21 Position */}
      <td className="py-2 px-1 text-center">
        {row.price_vs_zlema21 ? (
          <span className={`text-[10px] font-bold px-1 py-px rounded border leading-none ${
            row.price_vs_zlema21 === 'ABOVE'
              ? 'text-cyan-300 bg-cyan-950/20 border-cyan-700/30'
              : 'text-slate-400 bg-slate-900/30 border-slate-700/30'
          }`} title={`Price vs ZLEMA(21): ${row.price_vs_zlema21}${row.zlema_21 != null ? ` (${row.zlema_21.toFixed(2)})` : ''}`}>
            {row.price_vs_zlema21 === 'ABOVE' ? '▲' : '▼'}
          </span>
        ) : <span className="text-slate-700">—</span>}
      </td>

      {/* Boring / Explosive Candle */}
      <td className="py-2 px-1 text-center">
        {row.is_explosive_candle ? (
          <span className="text-[10px] font-bold px-1 py-px rounded border text-amber-300 bg-amber-950/30 border-amber-700/40 leading-none" title="Explosive candle: range ≥1.5× prior boring candle">💥</span>
        ) : row.is_boring_candle ? (
          <span className="text-[10px] font-bold px-1 py-px rounded border text-slate-400 bg-slate-900/30 border-slate-700/30 leading-none" title="Boring candle: wicks > body (demand/supply compression)">😴</span>
        ) : <span className="text-slate-700">—</span>}
      </td>

      {/* CPR Daily */}
      <td className="py-2 px-1 text-center">
        {row.cpr_daily_pivot != null ? (
          <span className="font-mono text-[10px] text-slate-300" title={`Daily CPR — PP: ${row.cpr_daily_pivot?.toFixed(2)} · TC: ${row.cpr_daily_tc?.toFixed(2)} · BC: ${row.cpr_daily_bc?.toFixed(2)}${row.cpr_daily_narrow ? ' · Narrow (trend day)' : ''}`}>
            {row.cpr_daily_pivot.toFixed(1)}
            {row.cpr_daily_narrow && <span className="ml-0.5 text-[9px] text-purple-300 font-bold">N</span>}
          </span>
        ) : <span className="text-slate-700">—</span>}
      </td>

      {/* CPR Weekly */}
      <td className="py-2 px-1 text-center">
        {row.cpr_weekly_pivot != null ? (
          <span className="font-mono text-[10px] text-slate-300" title={`Weekly CPR — PP: ${row.cpr_weekly_pivot?.toFixed(2)} · TC: ${row.cpr_weekly_tc?.toFixed(2)} · BC: ${row.cpr_weekly_bc?.toFixed(2)}`}>
            {row.cpr_weekly_pivot.toFixed(1)}
          </span>
        ) : <span className="text-slate-700">—</span>}
      </td>

      {/* PSY-20 */}
      <td className="py-2 px-1 text-center">
        {row.psy_20 != null ? (
          <span className={`font-mono text-xs ${
            row.psy_20 >= 60 ? 'text-emerald-400' : row.psy_20 <= 40 ? 'text-rose-400' : 'text-slate-300'
          }`} title={`Psychological Line (20d): ${row.psy_20.toFixed(0)}% of days closed up`}>
            {row.psy_20.toFixed(0)}%
          </span>
        ) : <span className="text-slate-700">—</span>}
      </td>

      {/* AVWAP Position */}
      <td className="py-2 px-1 text-center">
        {row.price_vs_avwap ? (
          <span className={`text-[10px] font-bold px-1 py-px rounded border leading-none ${
            row.price_vs_avwap === 'ABOVE'
              ? 'text-blue-300 bg-blue-950/20 border-blue-700/30'
              : 'text-slate-400 bg-slate-900/30 border-slate-700/30'
          }`} title={`Price vs AVWAP (anchored from last gap-up): ${row.price_vs_avwap}${row.avwap != null ? ` (${row.avwap.toFixed(2)})` : ''}`}>
            {row.price_vs_avwap === 'ABOVE' ? '▲' : '▼'}
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

    </tr>
  );
};
