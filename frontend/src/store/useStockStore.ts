import { create } from 'zustand';
import { apiService } from '../services/api';
import { API_BASE } from '../lib/apiBase';
import type {
  SymbolDetail,
  CandleData,
  RenkoBrick,
  LineBreakLine,
  IndicatorData,
  ScreenerRow,
  CorporateAction,
  SyncJob,
  SymbolSyncStatus,
  PortfolioData,
  ConfluenceLevel,
  TrendlineData,
  StockAlert,
} from '../services/api';

// ─── Types ────────────────────────────────────────────────────────────────────

interface ScreenerFilters {
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
  limit?: number;
}

export type ChartOverlay = 'sma20' | 'sma50' | 'sma200' | 'ema9' | 'ema21' | 'bb' | 'sr' | 'nifty' | 'trendlines';

export interface WatchlistItem {
  symbol: string;       // e.g. RELIANCE.NS
  addedAt: string;      // ISO date string
}

export interface Watchlist {
  id: string;
  name: string;
  items: WatchlistItem[];
}

export type AlertType = 'price_above' | 'price_below' | 'rsi_above' | 'rsi_below';

export interface WatchlistAlert {
  id: string;
  symbol: string;
  type: AlertType;
  threshold: number;
  triggered: boolean;
  createdAt: string;
}

type TabId = 'explorer' | 'screener' | 'strategy' | 'sync' | 'ai-research' | 'portfolio' | 'watchlist' | 'compare' | 'settings' | 'about' | 'ml2-training';
type ChartTimeframe = '1W' | '1M' | '3M' | '6M' | '1Y' | 'MAX';

// ─── Store shape ──────────────────────────────────────────────────────────────

interface StockState {
  symbols: SymbolDetail[];
  activeSymbol: string | null;
  activeSymbolDetail: SymbolDetail | null;
  activeTab: TabId;
  chartType: 'candles' | 'heikin-ashi' | 'renko' | 'line-break';
  chartTimeframe: ChartTimeframe;
  chartOverlays: Set<ChartOverlay>;

  candles: CandleData[];
  heikinAshi: CandleData[];
  renkoBricks: RenkoBrick[];
  lineBreakLines: LineBreakLine[];
  indicators: IndicatorData[];
  corporateActions: CorporateAction[];
  niftyCandles: CandleData[];
  confluenceLevels: ConfluenceLevel[];
  trendlines: TrendlineData[];
  // Per-symbol custom horizontal price lines (persisted to localStorage)
  customLines: Record<string, number[]>;

  screenerFilters: ScreenerFilters;
  screenerResults: ScreenerRow[];

  syncJobs: SyncJob[];
  syncStatuses: SymbolSyncStatus[];

  fetchNiftyCandles: () => Promise<void>;
  addCustomLine: (symbol: string, price: number) => void;
  removeCustomLines: (symbol: string) => void;

  // Portfolio (backend-computed)
  portfolio: PortfolioData | null;
  portfolioLoading: boolean;

  // Stock alerts (backend-evaluated post-sync)
  stockAlerts: StockAlert[];
  stockAlertsLoading: boolean;
  _seenAlertIds: Set<number>;
  _alertsInitialized: boolean;

  // Watchlists
  watchlists: Watchlist[];
  activeWatchlistId: string | null;
  alerts: WatchlistAlert[];

  isLoading: boolean;
  isSyncing: boolean;
  error: string | null;

  // Actions
  setActiveTab: (tab: TabId) => void;
  setChartType: (type: 'candles' | 'heikin-ashi' | 'renko' | 'line-break') => void;
  setChartTimeframe: (tf: ChartTimeframe) => void;
  toggleChartOverlay: (overlay: ChartOverlay) => void;
  setScreenerFilters: (filters: Partial<ScreenerFilters>) => void;
  // Portfolio actions (backend-driven)
  fetchPortfolio: () => Promise<void>;
  importPortfolioFile: (file: File) => Promise<void>;
  clearPortfolio: () => Promise<void>;

  // Stock alert actions
  fetchStockAlerts: () => Promise<void>;
  dismissStockAlert: (id: number) => Promise<void>;
  dismissAllStockAlerts: () => Promise<void>;

  // Watchlist actions
  fetchWatchlists: () => Promise<void>;
  createWatchlist: (name: string) => void;
  deleteWatchlist: (id: string) => void;
  renameWatchlist: (id: string, name: string) => void;
  setActiveWatchlist: (id: string) => void;
  addToWatchlist: (watchlistId: string, symbol: string) => void;
  removeFromWatchlist: (watchlistId: string, symbol: string) => void;

  // Alert actions
  addAlert: (symbol: string, type: AlertType, threshold: number) => void;
  removeAlert: (id: string) => void;
  checkAlerts: () => void;

  // Async
  fetchSymbols: (activeOnly?: boolean) => Promise<void>;
  setSelectedSymbol: (symbol: string) => Promise<void>;
  fetchActiveSymbolData: () => Promise<void>;
  runScreener: () => Promise<void>;
  fetchSyncLogs: () => Promise<void>;
  triggerFullSync: () => Promise<void>;
  triggerSymbolSync: (symbol: string) => Promise<void>;
  triggerRecalculate: (symbol?: string) => Promise<void>;
  cancelSync: () => Promise<void>;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

const WATCHLIST_KEY = 'vajra_watchlists';

// Portfolio holdings now live in the backend DB (single source of truth).
// Any stale browser copy from older versions is discarded.
try { localStorage.removeItem('vajra_portfolio'); } catch { /* ignore */ }

function loadWatchlists(): Watchlist[] {
  try {
    const raw = localStorage.getItem(WATCHLIST_KEY);
    if (raw) return JSON.parse(raw);
  } catch { /* ignore */ }
  // Seed with one default list
  return [{ id: crypto.randomUUID(), name: 'My Watchlist', items: [] }];
}

function saveWatchlists(wl: Watchlist[]) {
  localStorage.setItem(WATCHLIST_KEY, JSON.stringify(wl));
}

const ALERTS_KEY = 'vajra_alerts';

function loadAlerts(): WatchlistAlert[] {
  try { return JSON.parse(localStorage.getItem(ALERTS_KEY) || '[]'); }
  catch { return []; }
}

function saveAlerts(a: WatchlistAlert[]) {
  localStorage.setItem(ALERTS_KEY, JSON.stringify(a));
}


function getInitialTab(): TabId {
  const path = window.location.pathname.replace(/^\/+/, '').split('/')[0];
  const valid: TabId[] = ['explorer', 'screener', 'strategy', 'sync', 'ai-research', 'portfolio', 'watchlist', 'compare', 'settings', 'about', 'ml2-training'];
  return valid.includes(path as TabId) ? (path as TabId) : 'explorer';
}

const SCREENER_FILTERS_KEY = 'vajra_screener_filters';

function loadScreenerFilters(): ScreenerFilters {
  try {
    const raw = localStorage.getItem(SCREENER_FILTERS_KEY);
    if (raw) return JSON.parse(raw);
  } catch { /* ignore */ }
  return {
    min_rsi: undefined,
    max_rsi: undefined,
    min_price: undefined,
    max_price: undefined,
    sma_20_cross: undefined,
    sma_50_cross: undefined,
    sma_200_cross: undefined,
    macd_trend: undefined,
    ha_dir: undefined,
    renko_dir: undefined,
    lb_dir: undefined,
    min_avg_traded_value: undefined,
    volume_breakout: undefined,
    only_nr7: undefined,
    only_inside_bar: undefined,
    only_gap_up: undefined,
    only_gap_down: undefined,
    min_rs_1m: undefined,
    limit: 2500,
  };
}

function saveScreenerFilters(filters: ScreenerFilters) {
  localStorage.setItem(SCREENER_FILTERS_KEY, JSON.stringify(filters));
}

// Load screener limit from DB settings asynchronously (non-blocking)
function loadScreenerLimitFromDB(): void {
  const BASE = API_BASE;
  fetch(`${BASE}/settings`)
    .then(r => (r.ok ? r.json() : null))
    .then((data: Record<string, Array<{ key: string; value: string; value_type: string }>> | null) => {
      if (!data) return;
      const limitRow = data['SCREENER']?.find(s => s.key === 'default_limit');
      if (limitRow?.value) {
        const limit = parseInt(limitRow.value, 10);
        if (!isNaN(limit) && limit > 0) {
          useStockStore.setState(s => {
            const nextFilters = { ...s.screenerFilters, limit };
            saveScreenerFilters(nextFilters);
            return { screenerFilters: nextFilters };
          });
        }
      }
    })
    .catch(() => { /* keep 2500 default */ });
}

// ─── Store ────────────────────────────────────────────────────────────────────

export const useStockStore = create<StockState>((set, get) => ({
  symbols: [],
  activeSymbol: null,
  activeSymbolDetail: null,
  activeTab: getInitialTab(),
  chartType: 'candles',
  chartTimeframe: '1Y',
  chartOverlays: new Set<ChartOverlay>(['sma20', 'sma50', 'sma200']),

  candles: [],
  heikinAshi: [],
  renkoBricks: [],
  lineBreakLines: [],
  indicators: [],
  corporateActions: [],
  niftyCandles: [],
  confluenceLevels: [],
  trendlines: [],
  customLines: JSON.parse(localStorage.getItem('vajra_lines') || '{}'),

  screenerFilters: loadScreenerFilters(),
  screenerResults: [],

  syncJobs: [],
  syncStatuses: [],

  portfolio: null,
  portfolioLoading: false,
  stockAlerts: [],
  stockAlertsLoading: false,
  _seenAlertIds: new Set<number>(),
  _alertsInitialized: false,
  watchlists: loadWatchlists(),
  activeWatchlistId: null,
  alerts: loadAlerts(),

  isLoading: false,
  isSyncing: false,
  error: null,

  // ── Basic setters ──────────────────────────────────────────────────────────

  setActiveTab: (activeTab) => {
    set({ activeTab });
    const cleanPath = `/${activeTab === 'explorer' ? '' : activeTab}`;
    if (window.location.pathname !== cleanPath) {
      window.history.pushState(null, '', cleanPath);
    }
  },
  setChartType: (chartType) => set({ chartType }),
  setChartTimeframe: (chartTimeframe) => set({ chartTimeframe }),
  toggleChartOverlay: (overlay) => {
    const next = new Set(get().chartOverlays);
    if (next.has(overlay)) next.delete(overlay); else next.add(overlay);
    set({ chartOverlays: next });
  },
  setScreenerFilters: (filters) => {
    const nextFilters = { ...get().screenerFilters, ...filters };
    saveScreenerFilters(nextFilters);
    set({ screenerFilters: nextFilters });
  },
  // ── Portfolio ──────────────────────────────────────────────────────────────

  fetchPortfolio: async () => {
    set({ portfolioLoading: true, error: null });
    try {
      const portfolio = await apiService.getPortfolio();
      set({ portfolio, portfolioLoading: false });
    } catch (err: unknown) {
      set({ error: (err as Error).message || 'Failed to load portfolio', portfolioLoading: false });
    }
  },

  importPortfolioFile: async (file) => {
    set({ portfolioLoading: true, error: null });
    try {
      const portfolio = await apiService.importPortfolio(file);
      set({ portfolio, portfolioLoading: false });
    } catch (err: unknown) {
      set({ error: (err as Error).message || 'Failed to import portfolio CSV', portfolioLoading: false });
    }
  },

  clearPortfolio: async () => {
    set({ error: null });
    try {
      await apiService.clearPortfolio();
      set({ portfolio: null });
    } catch (err: unknown) {
      set({ error: (err as Error).message || 'Failed to clear portfolio' });
    }
  },

  // ── Stock Alerts ───────────────────────────────────────────────────────────

  fetchStockAlerts: async () => {
    set({ stockAlertsLoading: true });
    try {
      const stockAlerts = await apiService.getAlerts('TRIGGERED');
      const { _seenAlertIds, _alertsInitialized } = get();

      if (!_alertsInitialized) {
        // First load: seed seen IDs without firing notifications (user already knows)
        set({
          stockAlerts,
          stockAlertsLoading: false,
          _seenAlertIds: new Set(stockAlerts.map(a => a.id)),
          _alertsInitialized: true,
        });
      } else {
        // Subsequent polls: fire browser notification for any genuinely new alerts
        const newAlerts = stockAlerts.filter(a => !_seenAlertIds.has(a.id));
        if (newAlerts.length > 0 && 'Notification' in window && Notification.permission === 'granted') {
          for (const alert of newAlerts.slice(0, 5)) {
            new Notification(`VAJRA: ${alert.symbol.replace('.NS', '')}`, {
              body: alert.message,
              tag: `vajra-alert-${alert.id}`,
            });
          }
          if (newAlerts.length > 5) {
            new Notification(`VAJRA: ${newAlerts.length - 5} more alerts fired`, {
              body: 'Open VajraStocks to review all alerts.',
              tag: 'vajra-alerts-overflow',
            });
          }
        }
        const updatedSeen = new Set([..._seenAlertIds, ...stockAlerts.map(a => a.id)]);
        set({ stockAlerts, stockAlertsLoading: false, _seenAlertIds: updatedSeen });
      }
    } catch {
      set({ stockAlertsLoading: false });
    }
  },

  dismissStockAlert: async (id: number) => {
    try {
      await apiService.dismissAlert(id);
      set(state => ({ stockAlerts: state.stockAlerts.filter(a => a.id !== id) }));
    } catch {
      // silently ignore
    }
  },

  dismissAllStockAlerts: async () => {
    try {
      await apiService.dismissAllAlerts();
      set({ stockAlerts: [] });
    } catch {
      // silently ignore
    }
  },

  // ── Watchlists ─────────────────────────────────────────────────────────────

  fetchWatchlists: async () => {
    try {
      const wls = await apiService.fetchWatchlists();
      if (wls.length === 0) {
        // Migration: push any non-empty localStorage lists to DB
        const local = loadWatchlists();
        const hasRealData = local.some(w => w.name !== 'My Watchlist' || w.items.length > 0);
        if (hasRealData) {
          for (const wl of local) {
            try {
              const created = await apiService.createWatchlistApi(wl.name);
              for (const item of wl.items) {
                await apiService.addToWatchlistApi(created.id, item.symbol).catch(() => {});
              }
            } catch { /* skip failed watchlists */ }
          }
          const refreshed = await apiService.fetchWatchlists();
          saveWatchlists(refreshed);
          set({ watchlists: refreshed });
          return;
        }
        // Seed a default list
        try {
          const def = await apiService.createWatchlistApi('My Watchlist');
          saveWatchlists([def]);
          set({ watchlists: [def] });
        } catch { /* API unavailable */ }
      } else {
        saveWatchlists(wls);
        set({ watchlists: wls });
      }
    } catch {
      // API unavailable — keep current localStorage state
    }
  },

  createWatchlist: (name) => {
    const currentLists = loadWatchlists();
    const wl = [...currentLists, { id: crypto.randomUUID(), name, items: [] }];
    saveWatchlists(wl);
    set({ watchlists: wl });
    apiService.createWatchlistApi(name)
      .then(() => get().fetchWatchlists())
      .catch(() => {});
  },

  deleteWatchlist: (id) => {
    const currentLists = loadWatchlists();
    const wl = currentLists.filter(w => w.id !== id);
    saveWatchlists(wl);
    set({ watchlists: wl, activeWatchlistId: get().activeWatchlistId === id ? null : get().activeWatchlistId });
    apiService.deleteWatchlistApi(id).catch(() => {});
  },

  renameWatchlist: (id, name) => {
    const currentLists = loadWatchlists();
    const wl = currentLists.map(w => w.id === id ? { ...w, name } : w);
    saveWatchlists(wl);
    set({ watchlists: wl });
    apiService.renameWatchlistApi(id, name).catch(() => {});
  },

  setActiveWatchlist: (id) => set({ activeWatchlistId: id }),

  addToWatchlist: (watchlistId, symbol) => {
    const currentLists = loadWatchlists();
    const wl = currentLists.map(w => {
      if (w.id !== watchlistId) return w;
      if (w.items.some(i => i.symbol === symbol)) return w; // already present
      return { ...w, items: [...w.items, { symbol, addedAt: new Date().toISOString() }] };
    });
    saveWatchlists(wl);
    set({ watchlists: wl });
    apiService.addToWatchlistApi(watchlistId, symbol).catch(() => {});
  },

  // ── Alerts ─────────────────────────────────────────────────────────────────

  addAlert: (symbol, type, threshold) => {
    const a = [...get().alerts, { id: crypto.randomUUID(), symbol, type, threshold, triggered: false, createdAt: new Date().toISOString() }];
    saveAlerts(a);
    set({ alerts: a });
  },

  removeAlert: (id) => {
    const a = get().alerts.filter(x => x.id !== id);
    saveAlerts(a);
    set({ alerts: a });
  },

  checkAlerts: () => {
    const { alerts, screenerResults } = get();
    if (!alerts.length || !screenerResults.length) return;

    const snapMap = new Map(screenerResults.map(r => [r.symbol, r]));
    let anyTriggered = false;

    const updated = alerts.map(alert => {
      if (alert.triggered) return alert;
      const snap = snapMap.get(alert.symbol) ?? snapMap.get(`${alert.symbol}.NS`);
      if (!snap) return alert;

      let fired = false;
      if (alert.type === 'price_above' && snap.close_price >= alert.threshold) fired = true;
      if (alert.type === 'price_below' && snap.close_price <= alert.threshold) fired = true;
      if (alert.type === 'rsi_above'   && snap.rsi_14 != null && snap.rsi_14 >= alert.threshold) fired = true;
      if (alert.type === 'rsi_below'   && snap.rsi_14 != null && snap.rsi_14 <= alert.threshold) fired = true;

      if (fired) {
        anyTriggered = true;
        const label = alert.type.replace('_', ' ').replace('price', '₹').replace('rsi', 'RSI');
        if ('Notification' in window && Notification.permission === 'granted') {
          new Notification(`🔔 VAJRA Alert: ${alert.symbol.replace('.NS', '')}`, {
            body: `${label} ${alert.threshold} triggered — Current: ${alert.type.startsWith('rsi') ? snap.rsi_14?.toFixed(1) : '₹' + snap.close_price.toFixed(2)}`,
          });
        }
        return { ...alert, triggered: true };
      }
      return alert;
    });

    if (anyTriggered) {
      saveAlerts(updated);
      set({ alerts: updated });
    }
  },

  removeFromWatchlist: (watchlistId, symbol) => {
    const currentLists = loadWatchlists();
    const wl = currentLists.map(w =>
      w.id !== watchlistId ? w : { ...w, items: w.items.filter(i => i.symbol !== symbol) }
    );
    saveWatchlists(wl);
    set({ watchlists: wl });
    apiService.removeFromWatchlistApi(watchlistId, symbol).catch(() => {});
  },

  // ── Async operations ───────────────────────────────────────────────────────

  fetchSymbols: async (activeOnly = true) => {
    set({ isLoading: true, error: null });
    try {
      const symbols = await apiService.getAllSymbols(activeOnly);
      set({ symbols, isLoading: false });

      const urlParams = new URLSearchParams(window.location.search);
      const urlSymbol = urlParams.get('symbol');

      let symbolToSelect = symbols.length > 0 ? symbols[0].symbol : null;
      if (urlSymbol && symbols.length > 0) {
        const clean = urlSymbol.toUpperCase().trim();
        const found = symbols.find(s =>
          s.symbol.toUpperCase() === clean ||
          s.symbol.toUpperCase().replace('.NS', '') === clean
        );
        if (found) symbolToSelect = found.symbol;
      }

      if (symbolToSelect && !get().activeSymbol) {
        await get().setSelectedSymbol(symbolToSelect);
      }
    } catch (err: unknown) {
      set({ error: (err as Error).message || 'Failed to fetch symbols', isLoading: false });
    }
  },

  setSelectedSymbol: async (symbol) => {
    set({ activeSymbol: symbol, isLoading: true, error: null });
    try {
      const detail = await apiService.getSymbolDetail(symbol);
      set({ activeSymbolDetail: detail });
      await get().fetchActiveSymbolData();
    } catch (err: unknown) {
      set({ error: (err as Error).message || 'Failed to load symbol details', isLoading: false });
    }
  },

  fetchActiveSymbolData: async () => {
    const symbol = get().activeSymbol;
    if (!symbol) return;
    set({ isLoading: true, error: null });
    try {
      const [candles, heikinAshi, renkoBricks, lineBreakLines, indicators, corporateActions, confluenceLevels, trendlines] = await Promise.all([
        apiService.getCandles(symbol),
        apiService.getHeikinAshi(symbol),
        apiService.getRenkoBricks(symbol),
        apiService.getLineBreakLines(symbol),
        apiService.getIndicators(symbol),
        apiService.getCorporateActions(symbol),
        apiService.getConfluenceLevels(symbol),
        apiService.getTrendlines(symbol),
      ]);
      set({ candles, heikinAshi, renkoBricks, lineBreakLines, indicators, corporateActions, confluenceLevels, trendlines, isLoading: false });
    } catch (err: unknown) {
      set({ error: (err as Error).message || 'Failed to fetch symbol data', isLoading: false });
    }
  },

  addCustomLine: (symbol, price) => {
    const cur = get().customLines;
    const updated = { ...cur, [symbol]: [...(cur[symbol] ?? []), price] };
    localStorage.setItem('vajra_lines', JSON.stringify(updated));
    set({ customLines: updated });
  },

  removeCustomLines: (symbol) => {
    const cur = { ...get().customLines };
    delete cur[symbol];
    localStorage.setItem('vajra_lines', JSON.stringify(cur));
    set({ customLines: cur });
  },

  fetchNiftyCandles: async () => {
    // Read benchmark symbol from DB settings; fall back to ^NSEI.
    // Uses getBenchmarkCandles which returns [] silently on 404 —
    // no browser console error when NIFTY hasn't been synced yet.
    let benchmarkSymbol = '^NSEI';
    try {
      const BASE = API_BASE;
      const res = await fetch(`${BASE}/settings`);
      if (res.ok) {
        const data = await res.json();
        const row = data['MARKET']?.find((s: { key: string; value: string }) => s.key === 'rs_benchmark_symbol');
        if (row?.value) benchmarkSymbol = row.value;
      }
    } catch { /* keep default ^NSEI */ }

    const candles = await apiService.getBenchmarkCandles(benchmarkSymbol);
    set({ niftyCandles: candles });
  },

  runScreener: async () => {
    set({ isLoading: true, error: null });
    try {
      const filters = get().screenerFilters;
      let results = await apiService.runScreenerPost(filters);
      // Apply client-side price range filter (close_price already in response)
      if (filters.min_price !== undefined) results = results.filter(r => r.close_price >= filters.min_price!);
      if (filters.max_price !== undefined) results = results.filter(r => r.close_price <= filters.max_price!);
      set({ screenerResults: results, isLoading: false });
      // Check price/RSI alerts against fresh screener data
      get().checkAlerts();
    } catch (err: unknown) {
      set({ error: (err as Error).message || 'Failed to execute screening sweep', isLoading: false });
    }
  },

  fetchSyncLogs: async () => {
    set({ isSyncing: true, error: null });
    try {
      const [syncJobs, syncStatuses] = await Promise.all([
        apiService.getSyncJobs(20),
        apiService.getSyncStatus(),
      ]);
      set({ syncJobs, syncStatuses, isSyncing: false });
    } catch (err: unknown) {
      set({ error: (err as Error).message || 'Failed to load sync logs', isSyncing: false });
    }
  },

  triggerFullSync: async () => {
    set({ error: null });
    try {
      await apiService.triggerFullSync();
      await get().fetchSyncLogs();
    } catch (err: unknown) {
      set({ error: (err as Error).message || 'Failed to trigger full EOD sync' });
    }
  },

  triggerSymbolSync: async (symbol) => {
    set({ error: null });
    try {
      await apiService.triggerSymbolSync(symbol);
      await get().fetchSyncLogs();
      if (get().activeSymbol === symbol) await get().fetchActiveSymbolData();
    } catch (err: unknown) {
      set({ error: (err as Error).message || `Failed to trigger sync for ${symbol}` });
    }
  },

  triggerRecalculate: async (symbol) => {
    set({ error: null });
    try {
      await apiService.triggerRecalculation(symbol);
      await get().fetchSyncLogs();
      if (symbol && get().activeSymbol === symbol) {
        await get().fetchActiveSymbolData();
      } else if (!symbol) {
        await get().fetchActiveSymbolData();
      }
    } catch (err: unknown) {
      set({ error: (err as Error).message || 'Failed to trigger calculations' });
    }
  },

  cancelSync: async () => {
    set({ error: null });
    try {
      await apiService.cancelSync();
      await get().fetchSyncLogs();
    } catch (err: unknown) {
      set({ error: (err as Error).message || 'Failed to cancel active sync jobs' });
    }
  },

}));

// Load DB-backed screener limit once the store is created (non-blocking)
loadScreenerLimitFromDB();

// Request notification permission and start polling for new alerts every 5 min
(function initAlertPolling() {
  if ('Notification' in window && Notification.permission === 'default') {
    Notification.requestPermission();
  }
  setInterval(() => {
    useStockStore.getState().fetchStockAlerts();
  }, 5 * 60 * 1000);
})();
