// Screener-wide constants extracted to keep ScreenerPanel.tsx below ~400 LOC.

export const STRAT_SIG_STYLE: Record<string, string> = {
  BUY:  'text-emerald-400 bg-emerald-950/30 border-emerald-800/50',
  WATCH:'text-amber-400 bg-amber-950/30 border-amber-800/50',
  SELL: 'text-rose-400 bg-rose-950/30 border-rose-800/50',
  NONE: 'text-slate-500 bg-slate-900/40 border-slate-800',
};

export const stratCode = (name: string) =>
  name.replace(/[^A-Za-z0-9 ]/g, '').split(' ').map(w => w[0]).join('').slice(0, 3).toUpperCase();

// ── Column-filter persistence ─────────────────────────────────────────────────
export const COL_FILTERS_KEY       = 'vajra_screener_col_filters';
export const SHOW_COL_FILTERS_KEY  = 'vajra_screener_show_col_filters';

export const DEFAULT_COL_FILTERS = {
  symbol: '', company_name: '', close_price: '', price_pct_change: '', regime_bias: '',
  ret_1w: '', ret_2w: '', ret_3w: '', ret_4w: '', stop_loss: '', target_1: '', target_2: '',
  target_3: '', potential_gain_pct: '', rr_ratio: '', tqs: '', weinstein_stage: '',
  position_size_shares: '', avg_traded_value: '', volume_breakout_ratio: '', rsi_14: '',
  cmf_20: '', stochrsi_k: '', stochrsi_d: '',
  sma_20_cross_direction: '', sma_50_cross_direction: '', sma_200_cross_direction: '',
  macd_trend: '', ha_direction: '', renko_direction: '', line_break_direction: '',
  rs_score_1m: '', patterns: '',
  days_since_ema9_ema20_bull: '', days_since_sma20_sma50_bull: '',
  days_since_macd_bull: '', days_since_cmf_bull: '',
  hilega_milega_signal: '', rsi_divergence: '', macd_divergence: '',
  candle_type: '', cpr_daily_narrow: '', cpr_weekly_narrow: '',
  psy_20: '', price_vs_avwap: '', price_vs_zlema21: '',
  market_cap: '', pe_ratio: '', pb_ratio: '', ev_ebitda: '',
  roe: '', debt_to_equity: '', profit_margin: '', eps_ttm: '', sector: '',
};
export type ColFilters = typeof DEFAULT_COL_FILTERS;

// ── Global preset filters (cleared state) ────────────────────────────────────
export const EMPTY_FILTERS = {
  min_rsi: undefined, max_rsi: undefined,
  min_price: undefined, max_price: undefined,
  sma_20_cross: undefined, sma_50_cross: undefined, sma_200_cross: undefined,
  macd_trend: undefined, ha_dir: undefined, renko_dir: undefined, lb_dir: undefined,
  volume_breakout: undefined, min_avg_traded_value: undefined,
  only_nr7: undefined, only_inside_bar: undefined,
  only_gap_up: undefined, only_gap_down: undefined,
  min_rs_1m: undefined,
  min_cmf: undefined, max_cmf: undefined, cmf_rising: undefined, cmf_crossed_zero: undefined,
  min_stochrsi_k: undefined, max_stochrsi_k: undefined, stochrsi_bullish_xover_max_days: undefined,
  ema_ribbon_bull_max_days: undefined, golden_cross_max_days: undefined,
  macd_bull_xover_max_days: undefined, cmf_bull_xover_max_days: undefined,
  only_vajraturn: undefined, only_bb_squeeze: undefined,
  min_tqs: undefined, only_weinstein_stage2: undefined,
  only_hilega_buy: undefined, only_rsi_bullish_div: undefined,
  only_macd_bullish_div: undefined, only_boring_candle: undefined,
  only_explosive_candle: undefined, min_psy_20: undefined, max_psy_20: undefined,
  price_above_avwap: undefined, price_above_zlema21: undefined, only_cpr_narrow: undefined,
} as const;

// ── Screener presets ──────────────────────────────────────────────────────────
export const PRESETS = [
  {
    name: 'Breakout Scanner',
    emoji: '🚀',
    desc: 'Vol >2x + SMA 200 above + HA bullish',
    filters: { volume_breakout: '2.0X' as const, sma_200_cross: 'ABOVE' as const, ha_dir: 'UP' as const },
  },
  {
    name: 'Momentum',
    emoji: '⚡',
    desc: 'RSI 55-75 + MACD bullish + all SMAs above',
    filters: { min_rsi: 55, max_rsi: 75, macd_trend: 'BULLISH' as const, sma_20_cross: 'ABOVE' as const, sma_50_cross: 'ABOVE' as const, sma_200_cross: 'ABOVE' as const },
  },
  {
    name: 'Pullback to SMA20',
    emoji: '📉',
    desc: 'RSI 40-55 + MACD bullish + SMA 200 above',
    filters: { min_rsi: 40, max_rsi: 55, macd_trend: 'BULLISH' as const, sma_200_cross: 'ABOVE' as const },
  },
  {
    name: 'Oversold Bounce',
    emoji: '🔄',
    desc: 'RSI <35 + SMA 200 above',
    filters: { max_rsi: 35, sma_200_cross: 'ABOVE' as const },
  },
  {
    name: 'Volume Surge',
    emoji: '📊',
    desc: 'Vol >3x average — unusual activity',
    filters: { volume_breakout: '3.0X' as const },
  },
  {
    name: 'Swing Reversal',
    emoji: '↩️',
    desc: 'RSI <45 + Renko DOWN reversal candidates',
    filters: { max_rsi: 45, renko_dir: 'DOWN' as const },
  },
  {
    name: 'NR7 Squeeze',
    emoji: '🎯',
    desc: 'Narrowest range of last 7 days — pre-breakout compression',
    filters: { only_nr7: true },
  },
  {
    name: 'Inside Bar',
    emoji: '📦',
    desc: 'Low-risk entry with well-defined stop loss',
    filters: { only_inside_bar: true },
  },
  {
    name: 'Gap Up',
    emoji: '⬆️',
    desc: "Opened >1% above yesterday's close on high volume",
    filters: { only_gap_up: true, volume_breakout: '1.5X' as const },
  },
  {
    name: 'RS Leaders',
    emoji: '🏆',
    desc: 'Outperforming NIFTY 50 by >20% over 1 month (RS > 1.2)',
    filters: { min_rs_1m: 1.2, sma_200_cross: 'ABOVE' as const },
  },
  {
    name: 'CMF Accumulation',
    emoji: '💰',
    desc: 'Smart money flowing in — CMF > 0.1, rising',
    filters: { min_cmf: 0.1, cmf_rising: true, sma_200_cross: 'ABOVE' as const },
  },
  {
    name: 'StochRSI Xover',
    emoji: '📈',
    desc: 'StochRSI bullish crossover from oversold within 3 days',
    filters: { stochrsi_bullish_xover_max_days: 3, sma_200_cross: 'ABOVE' as const },
  },
  {
    name: 'VajraTurn',
    emoji: '🎯',
    desc: 'Early reversal near rising SMA200 — high R:R low-risk entries',
    filters: { only_vajraturn: true },
  },
  {
    name: 'BB Squeeze',
    emoji: '🗜️',
    desc: 'Bollinger Band at 20-day width low — coiled for explosive move',
    filters: { only_bb_squeeze: true },
  },
  {
    name: 'Weinstein Stage 2',
    emoji: '📈',
    desc: 'Price above rising SMA200 — classic markup phase entry',
    filters: { only_weinstein_stage2: true },
  },
  {
    name: 'Strong Trend (TQS 70+)',
    emoji: '💪',
    desc: 'Trend Quality Score ≥ 70 — strong ADX, aligned MAs, RSI in trend zone',
    filters: { min_tqs: 70 },
  },
  {
    name: 'Hilega-Milega Buy',
    emoji: '🟢',
    desc: 'RSI currently above its 21-WMA — Hilega-Milega bullish state',
    filters: { only_hilega_buy: true },
  },
  {
    name: 'RSI Bullish Divergence',
    emoji: '📐',
    desc: 'Price lower low but RSI higher low — hidden bullish strength',
    filters: { only_rsi_bullish_div: true },
  },
  {
    name: 'Explosive Candle',
    emoji: '💥',
    desc: "Today's candle ≥1.5× prior boring candle — Supply & Demand breakout",
    filters: { only_explosive_candle: true },
  },
  {
    name: 'Above AVWAP',
    emoji: '🔵',
    desc: 'Price above Anchored VWAP from last gap-up — institutional support',
    filters: { price_above_avwap: true },
  },
  {
    name: 'CPR Narrow Day',
    emoji: '📏',
    desc: 'Central Pivot Range < 0.5% — trending day expected',
    filters: { only_cpr_narrow: true },
  },
];
