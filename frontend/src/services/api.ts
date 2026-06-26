import { API_BASE } from '../lib/apiBase';

const BASE_URL = API_BASE;

export interface SymbolDetail {
  id: number;
  symbol: string;
  company_name: string;
  isin: string;
  series: string;
  is_active: boolean;
  last_successful_sync_date?: string | null;
  last_attempt_status?: string | null;
  last_error_message?: string | null;
}

export interface TradePlan {
  symbol: string;
  bias: 'BULLISH' | 'NEUTRAL' | 'BEARISH';
  reasons: string[];
  entry: number;
  atr_14: number;
  stop_loss: number;
  target_1: number;
  target_2: number;
  entry_zone: string;
  position_size_shares: number;
  rr_ratio: number;
  sma_200: number | null;
  rsi_14: number | null;
  risk_per_trade: number;
  brokerage_pct: number;
  has_indicators: boolean;
}

export interface ConfluenceLevel {
  price: number;
  level_type: 'SUPPORT' | 'RESISTANCE';
  strength_score: number;
  components: string;
}

export interface TrendlineData {
  id: number;
  symbol: string;
  trendline_type: 'SUPPORT' | 'RESISTANCE';
  anchor1_date: string;
  anchor1_price: number;
  anchor2_date: string;
  anchor2_price: number;
  touch_count: number;
  score: number;
  slope_pct_per_day: number;
  is_broken: boolean;
  break_date: string | null;
}

export interface PortfolioHolding {
  instrument: string;
  qty: number;
  avg_cost: number;
  ltp: number;
  ltp_source: 'synced' | 'imported';
  invested: number;
  current_val: number;
  pnl: number;
  return_pct: number;
  bias: 'VERY_BULLISH' | 'BULLISH' | 'NEUTRAL' | 'BEARISH' | 'VERY_BEARISH' | null;
  mtf_confirmed: boolean | null;
  weekly_trend: 'UP' | 'DOWN' | null;
  atr_pct: number | null;
  vol_class: 'LOW' | 'MEDIUM' | 'HIGH' | null;
  rs_score_1m: number | null;
  stop: number | null;
  open_risk: number | null;
  matched: boolean;
  weak: boolean;
  weak_reason: string | null;
  ret_1w: number | null;
  ret_2w: number | null;
  ret_3w: number | null;
  ret_4w: number | null;
  target_1: number | null;
  target_2?: number | null;
  target_3?: number | null;
  potential_gain_pct: number | null;
  rr_ratio?: number | null;
  position_size_shares?: number | null;
  stop_type?: 'supertrend' | 'structural';
  composite_score?: number | null;
  ml_label?: string | null;
  supertrend_dir?: string | null;
}

export interface ReplacementCandidate {
  symbol: string;
  company_name: string;
  close_price: number;
  rsi_14: number | null;
  atr_pct: number | null;
  vol_class: 'LOW' | 'MEDIUM' | 'HIGH' | null;
  bias: 'VERY_BULLISH' | 'BULLISH' | 'NEUTRAL' | 'BEARISH' | 'VERY_BEARISH' | null;
  weekly_trend: 'UP' | 'DOWN' | null;
  ret_1w: number | null;
  ret_2w: number | null;
  ret_3w: number | null;
  ret_4w: number | null;
  stop_loss: number | null;
  target_1: number | null;
  target_2?: number | null;
  target_3?: number | null;
  potential_gain_pct: number | null;
  rr_ratio?: number | null;
  position_size_shares?: number | null;
  adx_14?: number | null;
  trend_strength_class?: string | null;
  obv_trend?: string | null;
  supertrend_dir?: string | null;
}

export interface PortfolioAggregates {
  total_invested: number;
  total_current: number;
  total_pnl: number;
  total_return_pct: number;
  net_pnl: number;
  charges: number;
  include_charges: boolean;
  positions: number;
  open_risk: number;
  heat_pct: number;
  heat_limit: number;
  heat_base: number;
  heat_base_is_capital: boolean;
  regime: 'BULL' | 'NEUTRAL' | 'BEAR';
  breadth_pct: number;
  clusters: { instrument: string; weight_pct: number }[];
  max_cluster_pct: number;
  weak_holdings: string[];
  replacement_candidates: ReplacementCandidate[];
  correlation_clusters: { pair: [string, string]; rho: number }[];
  portfolio_beta: number | null;
  diversification_score: number | null;
  hhi?: number | null;
  hhi_label?: 'LOW' | 'MODERATE' | 'HIGH' | null;
  var_1d_pct?: number | null;
  cvar_1d_pct?: number | null;
  var_1d_inr?: number | null;
  cvar_1d_inr?: number | null;
  alpha_1w?: number | null;
  alpha_4w?: number | null;
  alpha_3m?: number | null;
}

export interface PortfolioData {
  holdings: PortfolioHolding[];
  aggregates: PortfolioAggregates;
}

export interface StockAlert {
  id: number;
  symbol: string;
  alert_type: string;
  condition_value: number | null;
  status: 'TRIGGERED' | 'DISMISSED';
  scope: string;
  message: string;
  triggered_at: string;
}

export interface CandleData {
  time: string; // YYYY-MM-DD
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

export interface RenkoBrick {
  time: string;
  open: number;
  close: number;
  direction: 'UP' | 'DOWN';
}

export interface LineBreakLine {
  time: string;
  open: number;
  close: number;
  direction: 'UP' | 'DOWN';
}

export interface IndicatorData {
  time: string;
  rsi_14?: number | null;
  sma_20?: number | null;
  sma_50?: number | null;
  sma_200?: number | null;
  ema_9?: number | null;
  ema_21?: number | null;
  macd_line?: number | null;
  macd_signal?: number | null;
  macd_histogram?: number | null;
  bb_upper?: number | null;
  bb_middle?: number | null;
  bb_lower?: number | null;
  atr_14?: number | null;
  cmf_20?: number | null;
  stochrsi_k?: number | null;
  stochrsi_d?: number | null;
}

export interface ScreenerRow {
  symbol_id: number;
  symbol: string;
  company_name: string;
  last_trading_date: string;
  close_price: number;
  price_pct_change?: number | null;
  volume: number;
  ha_close: number;
  ha_direction: 'UP' | 'DOWN';
  rsi_14?: number | null;
  sma_20_cross_direction?: string | null;
  sma_50_cross_direction?: string | null;
  sma_200_cross_direction?: string | null;
  macd_trend?: string | null;
  renko_direction?: string | null;
  line_break_direction?: string | null;
  is_nr7?: boolean | null;
  is_inside_bar?: boolean | null;
  is_gap_up?: boolean | null;
  is_gap_down?: boolean | null;
  rs_score_1m?: number | null;
  regime_bias?: string | null;
  weekly_trend?: string | null;
  avg_traded_value?: number | null;
  volume_breakout_ratio?: number | null;
  ret_1w?: number | null;
  ret_2w?: number | null;
  ret_3w?: number | null;
  ret_4w?: number | null;
  atr_pct?: number | null;
  stop_loss?: number | null;
  target_1?: number | null;
  target_2?: number | null;
  target_3?: number | null;
  potential_gain_pct?: number | null;
  rr_ratio?: number | null;
  position_size_shares?: number | null;
  trade_quality_score?: number | null;
  adx_14?: number | null;
  trend_strength_class?: string | null;
  obv_trend?: string | null;
  supertrend_dir?: string | null;
  stoch_state?: string | null;
  composite_score?: number | null;
  trend_score_val?: number | null;
  volume_score_val?: number | null;
  rs_score_val?: number | null;
  momentum_score_val?: number | null;
  cmf_score_val?: number | null;
  breakout_score_val?: number | null;
  cmf_20?: number | null;
  cmf_20_prev?: number | null;
  cmf_crossed_above_zero?: boolean | null;
  stochrsi_k?: number | null;
  stochrsi_d?: number | null;
  stochrsi_zone?: string | null;
  stochrsi_bullish_xover_days_ago?: number | null;
  stochrsi_bearish_xover_days_ago?: number | null;
  ml_prediction?: number | null;
  ml_rank?: number | null;
  ml_label?: string | null;
  strategy_signals?: Record<string, { signal: string; score: number | null }>;
  // Crossover recency
  days_since_price_sma20_bull?: number | null;
  days_since_price_sma50_bull?: number | null;
  days_since_price_ema20_bull?: number | null;
  days_since_ema9_ema20_bull?: number | null;
  days_since_ema9_ema20_bear?: number | null;
  days_since_sma20_sma50_bull?: number | null;
  days_since_macd_bull?: number | null;
  days_since_macd_bear?: number | null;
  days_since_cmf_bull?: number | null;
  days_since_cmf_bear?: number | null;
  ema9_ema20_spread?: number | null;
  macd_histogram_slope?: number | null;
  macd_above_zero?: boolean | null;
  cmf_slope_5d?: number | null;
  is_vajraturn?: boolean | null;
  bb_bandwidth?: number | null;
  is_bb_squeeze?: boolean | null;
  tqs?: number | null;
  weinstein_stage?: number | null;
  // New indicators
  hilega_milega_signal?: number | null;
  rsi_divergence?: number | null;
  macd_divergence?: number | null;
  zlema_21?: number | null;
  price_vs_zlema21?: string | null;
  is_boring_candle?: boolean | null;
  is_explosive_candle?: boolean | null;
  cpr_daily_pivot?: number | null;
  cpr_daily_tc?: number | null;
  cpr_daily_bc?: number | null;
  cpr_daily_narrow?: boolean | null;
  cpr_weekly_pivot?: number | null;
  cpr_weekly_tc?: number | null;
  cpr_weekly_bc?: number | null;
  psy_20?: number | null;
  avwap?: number | null;
  avwap_upper_1sd?: number | null;
  avwap_lower_1sd?: number | null;
  price_vs_avwap?: string | null;
  // Fundamentals
  market_cap?: number | null;
  enterprise_value?: number | null;
  pe_ratio?: number | null;
  forward_pe?: number | null;
  pb_ratio?: number | null;
  ev_ebitda?: number | null;
  price_to_sales?: number | null;
  revenue_ttm?: number | null;
  net_profit_ttm?: number | null;
  ebitda?: number | null;
  gross_margin?: number | null;
  profit_margin?: number | null;
  operating_margin?: number | null;
  eps_ttm?: number | null;
  book_value?: number | null;
  dividend_yield?: number | null;
  roe?: number | null;
  roa?: number | null;
  debt_to_equity?: number | null;
  current_ratio?: number | null;
  free_cashflow?: number | null;
  sector?: string | null;
  industry?: string | null;
}

// ── Swing Picks ───────────────────────────────────────────────────────────────

export interface SwingPick {
  symbol: string;
  company_name: string;
  close_price: number;
  atr_14: number | null;
  tqs: number | null;
  weinstein_stage: number | null;
  volume_breakout_ratio: number | null;
  cmf_20: number | null;
  rsi_14: number | null;
  supertrend_dir: string | null;
  avg_traded_value_cr: number | null;
  stop_loss: number | null;
  target_1: number | null;
  target_2: number | null;
  rr_ratio: number | null;
  position_size_shares: number | null;
  entry_zone_low: number | null;
  entry_zone_high: number | null;
  category: 'BUY' | 'WATCHLIST' | 'ELIMINATED';
  elimination_reason: string | null;
  resistance_ceiling: boolean;
  resistance_price: number | null;
  macd_histogram: number | null;
  macd_histogram_slope: number | null;
  composite_score: number | null;
  support_score: number | null;
  support_touch_count: number | null;
  support_slope_pct: number | null;
  is_news_play: boolean;
  intermediate_resistance: boolean;
  intermediate_resistance_price: number | null;
  notional_capped: boolean;
}

export interface SwingPicksConfig {
  min_tqs: number;
  min_volume_ratio: number;
  min_atv_cr: number;
  min_rr_buy: number;
  min_rr_watchlist: number;
  stop_atr_mult: number;
  entry_atr_low: number;
  entry_atr_high: number;
  min_res_strength: number;
  risk_per_trade: number;
}

export interface SwingPicksParams extends Partial<SwingPicksConfig> {}

export interface SwingPicksResponse {
  run_at: string;
  config: SwingPicksConfig;
  summary: { total_screened: number; buy_count: number; watchlist_count: number; eliminated_count: number };
  buy_picks: SwingPick[];
  watchlist: SwingPick[];
  eliminated: SwingPick[];
}

// ── Strategy Screener ─────────────────────────────────────────────────────────
export interface StrategyParamSpec {
  type: string;
  default: number | string | boolean;
  minimum?: number;
  maximum?: number;
  group?: string;
  description?: string;
}

export interface StrategyMeta {
  id: string;
  name: string;
  version: string;
  description: string;
  param_schema: Record<string, StrategyParamSpec>;
  data_needs: Record<string, unknown>;
}

export interface StrategySignalRow {
  symbol_id: number;
  symbol: string;
  company_name: string;
  strategy_id: string;
  as_of: string;
  signal: 'BUY' | 'SELL' | 'WATCH' | 'NONE';
  score: number | null;
  last_close: number | null;
  entry_ref: number | null;
  initial_stop: number | null;
  target: number | null;
  risk_pct: number | null;
  rr: number | null;
  key_metrics: Record<string, number | string | null>;
  gates: Record<string, boolean>;
  reasons: string[];
}

export interface StrategySignalsResponse {
  strategy_id: string;
  as_of: string | null;
  stale: boolean;
  counts: Record<string, number>;
  rows: StrategySignalRow[];
}

export interface StrategyMatrixRow {
  symbol: string;
  company_name: string;
  cells: Record<string, { signal: string; score: number | null }>;
  consensus: Record<string, number>;
  best_score: number;
}

export interface StrategyMatrixResponse {
  strategies: { id: string; name: string }[];
  as_of: string | null;
  stale: boolean;
  rows: StrategyMatrixRow[];
}

export interface CorporateAction {
  id: number;
  action_date: string;
  action_type: 'DIVIDEND' | 'SPLIT';
  value: number;
}

export interface SyncJob {
  id: number;
  run_id: string;
  start_time: string;
  end_time?: string | null;
  status: string;
  total_symbols: number;
  processed_symbols: number;
  failed_symbols: number;
  records_inserted: number;
  error_summary?: string | null;
}

export interface SymbolSyncStatus {
  symbol: string;
  last_successful_sync_date: string;
  last_attempt_status: string;
  last_error_message?: string | null;
}

export interface EodImportJob {
  job_id: string;
  filename: string;
  file_date: string;
  status:
    | 'PENDING' | 'VALIDATING' | 'STAGING' | 'GAP_FILLING'
    | 'PATCHING' | 'CALCULATING' | 'REFRESHING'
    | 'SUCCESS' | 'FAILED' | 'DUPLICATE';
  uploaded_at: string;
  started_at: string | null;
  completed_at: string | null;
  total_rows: number | null;
  equity_rows: number | null;
  staged_count: number | null;
  yahoo_filled_count: number | null;
  eod_patched_count: number | null;
  unresolved_symbols: string[] | null;
  gap_info: { symbols_with_gap: number; symbols_with_no_history: number; file_date: string } | null;
  error_message: string | null;
}

// ── ML Training (VajraML2) ────────────────────────────────────────────────────
export interface ML2FoldMetric {
  fold: number;
  ic_ptp: number;
  tp_prec: number;
  hit_5d: number;
  ls_pnl: number;
}

export interface ML2TrainingRun {
  id: number;
  version: string;
  status: 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';
  num_folds: number | null;
  dataset_rows: number | null;
  date_range_start: string | null;
  date_range_end: string | null;
  mean_ic_ptp: number | null;
  fold_metrics: ML2FoldMetric[] | null;
  error_message: string | null;
  started_at: string;
  completed_at: string | null;
}

export interface ML2ProgressEvent {
  type: 'stage' | 'dataset' | 'fold_start' | 'tree' | 'fold_done'
      | 'complete' | 'cancelled' | 'error' | 'heartbeat' | 'stream_end';
  pct?: number;
  message?: string;
  rows?: number;
  features?: number;
  date_start?: string;
  date_end?: string;
  fold?: number;
  total?: number;
  train_rows?: number;
  test_rows?: number;
  tree?: number;
  ic_ptp?: number;
  tp_prec?: number;
  hit_5d?: number;
  ls_pnl?: number;
  mean_ic_ptp?: number;
  mean_tp_prec?: number;
  folds?: number;
  error?: string;
}

// ── Fundamentals ─────────────────────────────────────────────────────────────
export interface SymbolFundamentals {
  symbol: string;
  market_cap: number | null;
  enterprise_value: number | null;
  pe_ratio: number | null;
  forward_pe: number | null;
  pb_ratio: number | null;
  ev_ebitda: number | null;
  price_to_sales: number | null;
  revenue_ttm: number | null;
  net_profit_ttm: number | null;
  ebitda: number | null;
  gross_margin: number | null;
  profit_margin: number | null;
  operating_margin: number | null;
  eps_ttm: number | null;
  book_value: number | null;
  dividend_yield: number | null;
  roe: number | null;
  roa: number | null;
  debt_to_equity: number | null;
  current_ratio: number | null;
  free_cashflow: number | null;
  sector: string | null;
  industry: string | null;
  fetched_at: string | null;
}

export interface NSEAnnouncement {
  id: number;
  symbol: string;
  seq_id: string;
  announcement_date: string | null;
  subject: string;
  description: string | null;
  file_url: string | null;
}

export interface NewsItem {
  id: number;
  symbol: string;
  title: string;
  publisher: string | null;
  link: string | null;
  published_at: string | null;
}

// ── Backtest Lab ──────────────────────────────────────────────────────────────
export interface BacktestMetrics {
  total_return: number;
  cagr: number;
  max_drawdown: number;
  win_rate: number;
  profit_factor: number | null;
  sharpe_ratio: number;
  trades: number;
}

export interface BacktestTrade {
  entry_date: string;
  entry_price: number;
  exit_date: string;
  exit_price: number;
  qty: number;
  return_pct: number;
  reason: string;
}

export interface BacktestRunResult {
  run_id: number | null;
  symbol: string;
  signal: string;
  bars: number;
  metrics: BacktestMetrics;
  trades: BacktestTrade[];
}

export interface SavedBacktestRun {
  id: number;
  symbol: string;
  signal: string;
  trades_count: number;
  created_at: string;
  metrics: Record<string, number>;
  trades?: BacktestTrade[];
}

export interface BacktestRunRequest {
  symbol: string;
  signal: string;
  params?: Record<string, unknown>;
  stop_pct?: number | null;
  target_pct?: number | null;
  cost_bps?: number;
  slippage_bps?: number;
  initial_capital?: number;
  adjusted?: boolean;
  save?: boolean;
}

// ── Trade Journal ─────────────────────────────────────────────────────────────
export interface JournalTrade {
  id: number;
  symbol: string;
  setup: string;
  side: string;
  status: string;
  entry_date: string;
  entry_price: number;
  qty: number;
  stop_price: number | null;
  target_price: number | null;
  exit_date: string | null;
  exit_price: number | null;
  fees: number;
  thesis: string | null;
  mistake_tags: string | null;
  pnl: number | null;
  return_pct: number | null;
  r_multiple: number | null;
}

export interface JournalTradeInput {
  symbol: string;
  entry_date: string;
  entry_price: number;
  qty: number;
  setup?: string;
  side?: string;
  stop_price?: number | null;
  target_price?: number | null;
  thesis?: string | null;
}

export interface SetupStats {
  setup: string;
  trades: number;
  wins: number;
  win_rate: number;
  total_pnl: number;
  avg_pnl: number;
  avg_r: number;
  expectancy_r: number;
}

export const apiService = {
  // 1. Symbols endpoints
  async getAllSymbols(activeOnly = true): Promise<SymbolDetail[]> {
    const response = await fetch(`${BASE_URL}/symbols?active_only=${activeOnly}`);
    if (!response.ok) throw new Error('Failed to fetch symbols');
    return response.json();
  },

  async getSymbolDetail(symbol: string): Promise<SymbolDetail> {
    const response = await fetch(`${BASE_URL}/symbols/${symbol}`);
    if (!response.ok) throw new Error(`Symbol ${symbol} not found`);
    return response.json();
  },

  /** Backend-computed trade plan + multi-factor bias (single source of truth). */
  async getSwingPicks(params?: SwingPicksParams): Promise<SwingPicksResponse> {
    const q = new URLSearchParams();
    if (params) {
      for (const [k, v] of Object.entries(params)) {
        if (v !== undefined) q.append(k, String(v));
      }
    }
    const response = await fetch(`${BASE_URL}/swing-picks?${q.toString()}`);
    if (!response.ok) throw new Error('Swing picks pipeline failed');
    return response.json();
  },

  async qualifyStocks(symbols: string[], params?: SwingPicksParams): Promise<SwingPicksResponse> {
    const q = new URLSearchParams();
    if (params) {
      for (const [k, v] of Object.entries(params)) {
        if (v !== undefined) q.append(k, String(v));
      }
    }
    const response = await fetch(`${BASE_URL}/swing-picks/qualify?${q.toString()}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbols }),
    });
    if (!response.ok) throw new Error('Qualify failed');
    return response.json();
  },

  async getSwingNotes(): Promise<Record<string, string>> {
    try {
      const response = await fetch(`${BASE_URL}/swing-picks/notes`);
      if (!response.ok) return {};
      return response.json();
    } catch { return {}; }
  },

  async saveSwingNote(symbol: string, note: string): Promise<void> {
    await fetch(`${BASE_URL}/swing-picks/notes/${encodeURIComponent(symbol)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ note }),
    });
  },

  async getTradePlan(symbol: string): Promise<TradePlan | null> {
    try {
      const response = await fetch(`${BASE_URL}/symbols/${encodeURIComponent(symbol)}/trade-plan`);
      if (!response.ok) return null;   // not synced / no data — render nothing
      return response.json();
    } catch {
      return null;
    }
  },

  async getConfluenceLevels(symbol: string): Promise<ConfluenceLevel[]> {
    const response = await fetch(`${BASE_URL}/symbols/${encodeURIComponent(symbol)}/confluence-levels`);
    if (!response.ok) throw new Error(`Failed to fetch confluence levels for ${symbol}`);
    return response.json();
  },

  async getTrendlines(symbol: string): Promise<TrendlineData[]> {
    const response = await fetch(`${BASE_URL}/trendlines/${encodeURIComponent(symbol)}`);
    if (!response.ok) return [];
    return response.json();
  },

  // 2. Charts endpoints
  async getCandles(symbol: string): Promise<CandleData[]> {
    const response = await fetch(`${BASE_URL}/charts/${encodeURIComponent(symbol)}/candles`);
    if (!response.ok) throw new Error('Failed to fetch candlestick data');
    return response.json();
  },

  /**
   * Fetch candles for the benchmark / index symbol (e.g. ^NSEI).
   * Returns an empty array silently when the symbol is not yet synced —
   * no 404 error logged in the browser console.
   */
  async getBenchmarkCandles(symbol: string): Promise<CandleData[]> {
    try {
      const response = await fetch(`${BASE_URL}/charts/${encodeURIComponent(symbol)}/candles`);
      if (response.status === 404) return [];          // not synced yet — silent fallback
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    } catch {
      return [];
    }
  },

  async getHeikinAshi(symbol: string): Promise<CandleData[]> {
    const response = await fetch(`${BASE_URL}/charts/${encodeURIComponent(symbol)}/heikin-ashi`);
    if (!response.ok) throw new Error('Failed to fetch Heikin-Ashi data');
    return response.json();
  },

  async getRenkoBricks(symbol: string): Promise<RenkoBrick[]> {
    const response = await fetch(`${BASE_URL}/charts/${encodeURIComponent(symbol)}/renko`);
    if (!response.ok) throw new Error('Failed to fetch Renko brick data');
    return response.json();
  },

  async getLineBreakLines(symbol: string): Promise<LineBreakLine[]> {
    const response = await fetch(`${BASE_URL}/charts/${encodeURIComponent(symbol)}/line-break`);
    if (!response.ok) throw new Error('Failed to fetch Line Break data');
    return response.json();
  },

  // 3. Technical Indicators endpoint
  async getIndicators(symbol: string): Promise<IndicatorData[]> {
    const response = await fetch(`${BASE_URL}/indicators/${encodeURIComponent(symbol)}`);
    if (!response.ok) throw new Error('Failed to fetch indicators data');
    return response.json();
  },

  // 4. Screening snapshots endpoints
  async runScreenerGet(filters: {
    min_rsi?: number;
    max_rsi?: number;
    sma_20_cross?: 'ABOVE' | 'BELOW';
    sma_50_cross?: 'ABOVE' | 'BELOW';
    sma_200_cross?: 'ABOVE' | 'BELOW';
    macd_trend?: 'BULLISH' | 'BEARISH';
    ha_dir?: 'UP' | 'DOWN';
    renko_dir?: 'UP' | 'DOWN';
    lb_dir?: 'UP' | 'DOWN';
    min_avg_traded_value?: number;
    volume_breakout?: 'ANY' | '1.5X' | '2.0X' | '3.0X';
    limit?: number;
  }): Promise<ScreenerRow[]> {
    const query = new URLSearchParams();
    if (filters.min_rsi !== undefined) query.append('min_rsi', String(filters.min_rsi));
    if (filters.max_rsi !== undefined) query.append('max_rsi', String(filters.max_rsi));
    if (filters.sma_20_cross !== undefined) query.append('sma_20_cross', filters.sma_20_cross);
    if (filters.sma_50_cross !== undefined) query.append('sma_50_cross', filters.sma_50_cross);
    if (filters.sma_200_cross !== undefined) query.append('sma_200_cross', filters.sma_200_cross);
    if (filters.macd_trend !== undefined) query.append('macd_trend', filters.macd_trend);
    if (filters.ha_dir !== undefined) query.append('ha_dir', filters.ha_dir);
    if (filters.renko_dir !== undefined) query.append('renko_dir', filters.renko_dir);
    if (filters.lb_dir !== undefined) query.append('lb_dir', filters.lb_dir);
    if (filters.min_avg_traded_value !== undefined) query.append('min_avg_traded_value', String(filters.min_avg_traded_value * 1e7));
    if (filters.volume_breakout !== undefined) query.append('volume_breakout', filters.volume_breakout);
    if (filters.limit !== undefined) query.append('limit', String(filters.limit));

    const response = await fetch(`${BASE_URL}/screeners?${query.toString()}`);
    if (!response.ok) throw new Error('Failed to fetch screener results');
    return response.json();
  },

  async runScreenerPost(filters: {
    min_rsi?: number;
    max_rsi?: number;
    min_price?: number;
    max_price?: number;
    sma_20_cross?: 'ABOVE' | 'BELOW';
    sma_50_cross?: 'ABOVE' | 'BELOW';
    sma_200_cross?: 'ABOVE' | 'BELOW';
    macd_trend?: 'BULLISH' | 'BEARISH';
    ha_dir?: 'UP' | 'DOWN';
    renko_dir?: 'UP' | 'DOWN';
    lb_dir?: 'UP' | 'DOWN';
    min_avg_traded_value?: number;
    volume_breakout?: 'ANY' | '1.5X' | '2.0X' | '3.0X';
    only_nr7?: boolean;
    only_inside_bar?: boolean;
    only_gap_up?: boolean;
    only_gap_down?: boolean;
    min_rs_1m?: number;
    min_cmf?: number;
    max_cmf?: number;
    cmf_rising?: boolean;
    cmf_crossed_zero?: boolean;
    min_stochrsi_k?: number;
    max_stochrsi_k?: number;
    stochrsi_bullish_xover_max_days?: number;
    ema_ribbon_bull_max_days?: number;
    golden_cross_max_days?: number;
    macd_bull_xover_max_days?: number;
    cmf_bull_xover_max_days?: number;
    only_vajraturn?: boolean;
    only_bb_squeeze?: boolean;
    min_tqs?: number;
    only_weinstein_stage2?: boolean;
    only_hilega_buy?: boolean;
    only_rsi_bullish_div?: boolean;
    only_macd_bullish_div?: boolean;
    only_boring_candle?: boolean;
    only_explosive_candle?: boolean;
    min_psy_20?: number;
    max_psy_20?: number;
    price_above_avwap?: boolean;
    price_above_zlema21?: boolean;
    only_cpr_narrow?: boolean;
    limit?: number;
  }): Promise<ScreenerRow[]> {
    const response = await fetch(`${BASE_URL}/screeners/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        min_rsi: filters.min_rsi ?? null,
        max_rsi: filters.max_rsi ?? null,
        sma_20_cross: filters.sma_20_cross ?? null,
        sma_50_cross: filters.sma_50_cross ?? null,
        sma_200_cross: filters.sma_200_cross ?? null,
        macd_trend: filters.macd_trend ?? null,
        ha_dir: filters.ha_dir ?? null,
        renko_dir: filters.renko_dir ?? null,
        lb_dir: filters.lb_dir ?? null,
        min_avg_traded_value: filters.min_avg_traded_value !== undefined ? filters.min_avg_traded_value * 1e7 : null,
        volume_breakout: filters.volume_breakout ?? null,
        only_nr7: filters.only_nr7 ?? false,
        only_inside_bar: filters.only_inside_bar ?? false,
        only_gap_up: filters.only_gap_up ?? false,
        only_gap_down: filters.only_gap_down ?? false,
        min_rs_1m: filters.min_rs_1m ?? null,
        min_cmf: filters.min_cmf ?? null,
        max_cmf: filters.max_cmf ?? null,
        cmf_rising: filters.cmf_rising ?? null,
        cmf_crossed_zero: filters.cmf_crossed_zero ?? null,
        min_stochrsi_k: filters.min_stochrsi_k ?? null,
        max_stochrsi_k: filters.max_stochrsi_k ?? null,
        stochrsi_bullish_xover_max_days: filters.stochrsi_bullish_xover_max_days ?? null,
        ema_ribbon_bull_max_days: filters.ema_ribbon_bull_max_days ?? null,
        golden_cross_max_days: filters.golden_cross_max_days ?? null,
        macd_bull_xover_max_days: filters.macd_bull_xover_max_days ?? null,
        cmf_bull_xover_max_days: filters.cmf_bull_xover_max_days ?? null,
        only_vajraturn: filters.only_vajraturn ?? false,
        only_bb_squeeze: filters.only_bb_squeeze ?? false,
        min_tqs: filters.min_tqs ?? null,
        only_weinstein_stage2: filters.only_weinstein_stage2 ?? false,
        only_hilega_buy: filters.only_hilega_buy ?? false,
        only_rsi_bullish_div: filters.only_rsi_bullish_div ?? false,
        only_macd_bullish_div: filters.only_macd_bullish_div ?? false,
        only_boring_candle: filters.only_boring_candle ?? false,
        only_explosive_candle: filters.only_explosive_candle ?? false,
        min_psy_20: filters.min_psy_20 ?? null,
        max_psy_20: filters.max_psy_20 ?? null,
        price_above_avwap: filters.price_above_avwap ?? null,
        price_above_zlema21: filters.price_above_zlema21 ?? null,
        only_cpr_narrow: filters.only_cpr_narrow ?? false,
        limit: filters.limit ?? 100
      })
    });
    if (!response.ok) throw new Error('Failed to run screening criteria');
    return response.json();
  },

  // 4b. Strategy Screener endpoints
  async getStrategies(): Promise<StrategyMeta[]> {
    const response = await fetch(`${BASE_URL}/strategies`);
    if (!response.ok) throw new Error('Failed to fetch strategies');
    return response.json();
  },

  async getStrategySignals(
    strategyId: string,
    opts: { signal?: string; min_score?: number; limit?: number } = {},
  ): Promise<StrategySignalsResponse> {
    const query = new URLSearchParams();
    if (opts.signal) query.append('signal', opts.signal);
    if (opts.min_score !== undefined) query.append('min_score', String(opts.min_score));
    if (opts.limit !== undefined) query.append('limit', String(opts.limit));
    const response = await fetch(`${BASE_URL}/strategies/${encodeURIComponent(strategyId)}/signals?${query}`);
    if (!response.ok) throw new Error('Failed to fetch strategy signals');
    return response.json();
  },

  async getStrategyMatrix(
    opts: { signals?: string; min_score?: number; only_active?: boolean; limit?: number } = {},
  ): Promise<StrategyMatrixResponse> {
    const query = new URLSearchParams();
    if (opts.signals) query.append('signals', opts.signals);
    if (opts.min_score !== undefined) query.append('min_score', String(opts.min_score));
    if (opts.only_active !== undefined) query.append('only_active', String(opts.only_active));
    if (opts.limit !== undefined) query.append('limit', String(opts.limit));
    const response = await fetch(`${BASE_URL}/strategies/matrix?${query}`);
    if (!response.ok) throw new Error('Failed to fetch strategy matrix');
    return response.json();
  },

  async getStrategySignalDetail(strategyId: string, symbol: string): Promise<StrategySignalRow> {
    const response = await fetch(
      `${BASE_URL}/strategies/${encodeURIComponent(strategyId)}/signals/${encodeURIComponent(symbol)}`,
    );
    if (!response.ok) throw new Error(`No signal for ${symbol}`);
    return response.json();
  },

  async recomputeStrategy(
    strategyId: string,
    params?: Record<string, number | string | boolean>,
    forceMarketOk = false,
  ): Promise<{ message: string }> {
    const response = await fetch(`${BASE_URL}/strategies/${encodeURIComponent(strategyId)}/recompute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...(params ? { params } : {}), force_market_ok: forceMarketOk }),
    });
    if (!response.ok) throw new Error('Failed to trigger strategy recompute');
    return response.json();
  },

  // 5. Corporate Actions endpoint
  async getCorporateActions(symbol: string): Promise<CorporateAction[]> {
    const response = await fetch(`${BASE_URL}/corporate-actions/${symbol}`);
    if (!response.ok) throw new Error('Failed to fetch corporate actions');
    return response.json();
  },

  // 5b. Portfolio endpoints (backend-computed)
  async importPortfolio(file: File): Promise<PortfolioData> {
    const fd = new FormData();
    fd.append('file', file);
    const response = await fetch(`${BASE_URL}/portfolio/import`, { method: 'POST', body: fd });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to import portfolio CSV');
    }
    return response.json();
  },

  async getPortfolio(): Promise<PortfolioData> {
    const response = await fetch(`${BASE_URL}/portfolio`);
    if (!response.ok) throw new Error('Failed to load portfolio');
    return response.json();
  },

  async clearPortfolio(): Promise<void> {
    const response = await fetch(`${BASE_URL}/portfolio`, { method: 'DELETE' });
    if (!response.ok) throw new Error('Failed to clear portfolio');
  },

  // 6. Synchronization endpoints
  async triggerFullSync(): Promise<{ message: string }> {
    const response = await fetch(`${BASE_URL}/sync/full`, { method: 'POST' });
    if (!response.ok) throw new Error('Failed to trigger full synchronization');
    return response.json();
  },

  async triggerSymbolSync(symbol: string): Promise<{ message: string }> {
    const response = await fetch(`${BASE_URL}/sync/symbol/${symbol}`, { method: 'POST' });
    if (!response.ok) throw new Error(`Failed to trigger synchronization for ${symbol}`);
    return response.json();
  },

  async triggerRecalculation(symbol?: string): Promise<{ message: string }> {
    const query = symbol ? `?symbol=${symbol}` : '';
    const response = await fetch(`${BASE_URL}/sync/recalculate${query}`, { method: 'POST' });
    if (!response.ok) throw new Error('Failed to trigger derived calculations recalculation');
    return response.json();
  },

  async getRecalcProgress(): Promise<{ status: string; total: number; processed: number; failed: number }> {
    const response = await fetch(`${BASE_URL}/sync/recalculate/progress`);
    if (!response.ok) throw new Error('Failed to fetch recalculation progress');
    return response.json();
  },

  async getSyncJobs(limit = 20): Promise<SyncJob[]> {
    const response = await fetch(`${BASE_URL}/sync/jobs?limit=${limit}`);
    if (!response.ok) throw new Error('Failed to fetch sync jobs logs');
    return response.json();
  },

  async getSyncStatus(statusFilter?: string): Promise<SymbolSyncStatus[]> {
    const query = statusFilter ? `?status_filter=${statusFilter}` : '';
    const response = await fetch(`${BASE_URL}/sync/status${query}`);
    if (!response.ok) throw new Error('Failed to fetch symbol sync status health');
    return response.json();
  },

  async cancelSync(): Promise<{ status: string; message: string }> {
    const response = await fetch(`${BASE_URL}/sync/cancel`, { method: 'POST' });
    if (!response.ok) throw new Error('Failed to cancel active sync jobs');
    return response.json();
  },

  // 7. Alerts
  async getAlerts(status?: string, limit = 100): Promise<StockAlert[]> {
    const params = new URLSearchParams();
    if (status) params.set('status', status);
    params.set('limit', String(limit));
    const response = await fetch(`${BASE_URL}/alerts?${params}`);
    if (!response.ok) throw new Error('Failed to fetch alerts');
    return response.json();
  },

  async dismissAlert(id: number): Promise<void> {
    const response = await fetch(`${BASE_URL}/alerts/${id}/dismiss`, { method: 'POST' });
    if (!response.ok) throw new Error('Failed to dismiss alert');
  },

  async dismissAllAlerts(): Promise<{ dismissed: number }> {
    const response = await fetch(`${BASE_URL}/alerts/dismiss-all`, { method: 'POST' });
    if (!response.ok) throw new Error('Failed to dismiss all alerts');
    return response.json();
  },

  // 8. Watchlists (backend-persisted)
  async fetchWatchlists(): Promise<{ id: string; name: string; items: { symbol: string; addedAt: string }[] }[]> {
    const r = await fetch(`${BASE_URL}/watchlists`);
    if (!r.ok) throw new Error('Failed to fetch watchlists');
    return r.json();
  },

  async createWatchlistApi(name: string): Promise<{ id: string; name: string; items: { symbol: string; addedAt: string }[] }> {
    const r = await fetch(`${BASE_URL}/watchlists`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    if (!r.ok) throw new Error('Failed to create watchlist');
    return r.json();
  },

  async renameWatchlistApi(id: string, name: string): Promise<void> {
    const r = await fetch(`${BASE_URL}/watchlists/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    if (!r.ok) throw new Error('Failed to rename watchlist');
  },

  async deleteWatchlistApi(id: string): Promise<void> {
    const r = await fetch(`${BASE_URL}/watchlists/${id}`, { method: 'DELETE' });
    if (!r.ok) throw new Error('Failed to delete watchlist');
  },

  async addToWatchlistApi(watchlistId: string, symbol: string): Promise<void> {
    const r = await fetch(`${BASE_URL}/watchlists/${watchlistId}/items`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol }),
    });
    if (!r.ok) throw new Error('Failed to add symbol to watchlist');
  },

  async removeFromWatchlistApi(watchlistId: string, symbol: string): Promise<void> {
    const r = await fetch(`${BASE_URL}/watchlists/${watchlistId}/items/${encodeURIComponent(symbol)}`, {
      method: 'DELETE',
    });
    if (!r.ok) throw new Error('Failed to remove symbol from watchlist');
  },

  // ── Fundamentals ─────────────────────────────────────────────────────────────
  async getFundamentals(symbol: string): Promise<SymbolFundamentals | null> {
    try {
      const r = await fetch(`${BASE_URL}/fundamentals/${encodeURIComponent(symbol)}`);
      if (!r.ok) return null;
      return r.json();
    } catch {
      return null;
    }
  },

  async refreshFundamentals(symbol: string): Promise<SymbolFundamentals | null> {
    try {
      const r = await fetch(`${BASE_URL}/fundamentals/${encodeURIComponent(symbol)}/refresh`, { method: 'POST' });
      if (!r.ok) return null;
      return r.json();
    } catch {
      return null;
    }
  },

  // ── NSE Announcements ─────────────────────────────────────────────────────────
  async getAnnouncements(symbol: string, limit = 20): Promise<NSEAnnouncement[]> {
    try {
      const r = await fetch(`${BASE_URL}/announcements/${encodeURIComponent(symbol)}?limit=${limit}`);
      if (!r.ok) return [];
      return r.json();
    } catch {
      return [];
    }
  },

  async refreshAnnouncements(symbol: string): Promise<NSEAnnouncement[]> {
    try {
      const r = await fetch(`${BASE_URL}/announcements/${encodeURIComponent(symbol)}/refresh`, { method: 'POST' });
      if (!r.ok) return [];
      const data = await r.json();
      return data.items ?? [];
    } catch {
      return [];
    }
  },

  // ── News ──────────────────────────────────────────────────────────────────────
  async getNews(symbol: string, limit = 15): Promise<NewsItem[]> {
    try {
      const r = await fetch(`${BASE_URL}/news/${encodeURIComponent(symbol)}?limit=${limit}`);
      if (!r.ok) return [];
      return r.json();
    } catch {
      return [];
    }
  },

  async refreshNews(symbol: string): Promise<NewsItem[]> {
    try {
      const r = await fetch(`${BASE_URL}/news/${encodeURIComponent(symbol)}/refresh`, { method: 'POST' });
      if (!r.ok) return [];
      const data = await r.json();
      return data.items ?? [];
    } catch {
      return [];
    }
  },

  // ── EOD Import ────────────────────────────────────────────────────────────

  async uploadEodFile(file: File): Promise<EodImportJob> {
    const form = new FormData();
    form.append('file', file);
    const r = await fetch(`${BASE_URL}/eod/upload`, { method: 'POST', body: form });
    if (!r.ok) {
      const err = await r.json().catch(() => ({ detail: 'Upload failed' }));
      throw new Error(err.detail ?? 'Upload failed');
    }
    return r.json();
  },

  async listEodJobs(limit = 30): Promise<EodImportJob[]> {
    const r = await fetch(`${BASE_URL}/eod/jobs?limit=${limit}`);
    if (!r.ok) throw new Error('Failed to fetch EOD import jobs');
    return r.json();
  },

  async getEodJob(jobId: string): Promise<EodImportJob> {
    const r = await fetch(`${BASE_URL}/eod/jobs/${jobId}`);
    if (!r.ok) throw new Error('Failed to fetch EOD job');
    return r.json();
  },

  async retryEodCalculations(jobId: string): Promise<EodImportJob> {
    const r = await fetch(`${BASE_URL}/eod/jobs/${jobId}/retry-calculations`, { method: 'POST' });
    if (!r.ok) throw new Error('Failed to retry calculations');
    return r.json();
  },

  async deleteEodJob(jobId: string): Promise<void> {
    const r = await fetch(`${BASE_URL}/eod/jobs/${jobId}`, { method: 'DELETE' });
    if (!r.ok) throw new Error('Failed to delete EOD job');
  },

  // ── Backtest Lab ──────────────────────────────────────────────────────────
  async getBacktestSignals(): Promise<string[]> {
    const r = await fetch(`${BASE_URL}/backtest/signals`);
    if (!r.ok) throw new Error('Failed to load signals');
    return (await r.json()).signals;
  },

  async runBacktest(body: BacktestRunRequest): Promise<BacktestRunResult> {
    const r = await fetch(`${BASE_URL}/backtest/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      const e = await r.json().catch(() => ({} as { detail?: string }));
      throw new Error(e.detail || 'Backtest failed');
    }
    return r.json();
  },

  async listBacktestRuns(symbol?: string): Promise<SavedBacktestRun[]> {
    const q = symbol ? `?symbol=${encodeURIComponent(symbol)}` : '';
    const r = await fetch(`${BASE_URL}/backtest/runs${q}`);
    if (!r.ok) throw new Error('Failed to list backtest runs');
    return r.json();
  },

  async getBacktestRun(id: number): Promise<SavedBacktestRun> {
    const r = await fetch(`${BASE_URL}/backtest/runs/${id}`);
    if (!r.ok) throw new Error('Backtest run not found');
    return r.json();
  },

  async backfillColumnar(full = false): Promise<{ symbols_mirrored: number; rows: number }> {
    const r = await fetch(`${BASE_URL}/backtest/backfill?full=${full}`, { method: 'POST' });
    if (!r.ok) throw new Error('Backfill failed');
    return r.json();
  },

  // ── Trade Journal ──────────────────────────────────────────────────────────
  async logTrade(body: JournalTradeInput): Promise<JournalTrade> {
    const r = await fetch(`${BASE_URL}/journal/trades`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error('Failed to log trade');
    return r.json();
  },

  async closeTrade(id: number, exit_date: string, exit_price: number, mistake_tags?: string): Promise<JournalTrade> {
    const r = await fetch(`${BASE_URL}/journal/trades/${id}/close`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ exit_date, exit_price, mistake_tags }),
    });
    if (!r.ok) throw new Error('Failed to close trade');
    return r.json();
  },

  async listTrades(symbol?: string, status?: string): Promise<JournalTrade[]> {
    const q = new URLSearchParams();
    if (symbol) q.append('symbol', symbol);
    if (status) q.append('status', status);
    const r = await fetch(`${BASE_URL}/journal/trades?${q.toString()}`);
    if (!r.ok) throw new Error('Failed to list trades');
    return r.json();
  },

  async deleteTrade(id: number): Promise<void> {
    const r = await fetch(`${BASE_URL}/journal/trades/${id}`, { method: 'DELETE' });
    if (!r.ok) throw new Error('Failed to delete trade');
  },

  async journalReview(): Promise<SetupStats[]> {
    const r = await fetch(`${BASE_URL}/journal/review`);
    if (!r.ok) throw new Error('Failed to load review');
    return r.json();
  },
};
