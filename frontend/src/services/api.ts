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
  weekly_avg_volume?: number | null;
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
    min_weekly_avg_volume?: number;
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
    if (filters.min_weekly_avg_volume !== undefined) query.append('min_weekly_avg_volume', String(filters.min_weekly_avg_volume));
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
    min_weekly_avg_volume?: number;
    volume_breakout?: 'ANY' | '1.5X' | '2.0X' | '3.0X';
    only_nr7?: boolean;
    only_inside_bar?: boolean;
    only_gap_up?: boolean;
    only_gap_down?: boolean;
    min_rs_1m?: number;
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
        min_weekly_avg_volume: filters.min_weekly_avg_volume ?? null,
        volume_breakout: filters.volume_breakout ?? null,
        only_nr7: filters.only_nr7 ?? false,
        only_inside_bar: filters.only_inside_bar ?? false,
        only_gap_up: filters.only_gap_up ?? false,
        only_gap_down: filters.only_gap_down ?? false,
        min_rs_1m: filters.min_rs_1m ?? null,
        limit: filters.limit ?? 100
      })
    });
    if (!response.ok) throw new Error('Failed to run screening criteria');
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
};
