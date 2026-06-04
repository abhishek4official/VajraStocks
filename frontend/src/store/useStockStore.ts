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
  ConfluenceLevel
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
  min_weekly_avg_volume?: number;
  volume_breakout?: 'ANY' | '1.5X' | '2.0X' | '3.0X';
  only_nr7?: boolean;
  only_inside_bar?: boolean;
  only_gap_up?: boolean;
  only_gap_down?: boolean;
  min_rs_1m?: number;
  limit?: number;
}

export type ChartOverlay = 'sma20' | 'sma50' | 'sma200' | 'ema9' | 'ema21' | 'bb' | 'sr' | 'nifty';

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

type TabId = 'explorer' | 'screener' | 'sync' | 'ai-research' | 'portfolio' | 'watchlist' | 'compare' | 'settings';
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
  // Per-symbol custom horizontal price lines (persisted to localStorage)
  customLines: Record<string, number[]>;

  screenerFilters: ScreenerFilters;
  screenerResults: ScreenerRow[];

  syncJobs: SyncJob[];
  syncStatuses: SymbolSyncStatus[];

  // AI
  aiQuery: string;
  aiIsLoading: boolean;
  aiEvents: { agent?: string; status: string; data?: Record<string, unknown> }[];
  aiReport: string | null;
  aiRecommendation: string | null;
  aiConfidence: string | null;

  fetchNiftyCandles: () => Promise<void>;
  addCustomLine: (symbol: string, price: number) => void;
  removeCustomLines: (symbol: string) => void;

  // Portfolio (backend-computed)
  portfolio: PortfolioData | null;
  portfolioLoading: boolean;

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
  setAiQuery: (query: string) => void;
  clearAiConsole: () => void;

  // Portfolio actions (backend-driven)
  fetchPortfolio: () => Promise<void>;
  importPortfolioFile: (file: File) => Promise<void>;
  clearPortfolio: () => Promise<void>;

  // Watchlist actions
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
  runAiWorkflow: (prompt: string) => Promise<void>;
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
  const valid: TabId[] = ['explorer', 'screener', 'sync', 'ai-research', 'portfolio', 'watchlist', 'compare', 'settings'];
  return valid.includes(path as TabId) ? (path as TabId) : 'explorer';
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
          useStockStore.setState(s => ({
            screenerFilters: { ...s.screenerFilters, limit },
          }));
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
  customLines: JSON.parse(localStorage.getItem('vajra_lines') || '{}'),

  screenerFilters: {
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
    min_weekly_avg_volume: undefined,
    volume_breakout: undefined,
    only_nr7: undefined,
    only_inside_bar: undefined,
    only_gap_up: undefined,
    only_gap_down: undefined,
    min_rs_1m: undefined,
    limit: 2500,
  },
  screenerResults: [],

  syncJobs: [],
  syncStatuses: [],

  aiQuery: '',
  aiIsLoading: false,
  aiEvents: [],
  aiReport: null,
  aiRecommendation: null,
  aiConfidence: null,

  portfolio: null,
  portfolioLoading: false,
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
  setScreenerFilters: (filters) => set({
    screenerFilters: { ...get().screenerFilters, ...filters }
  }),
  setAiQuery: (aiQuery) => set({ aiQuery }),
  clearAiConsole: () => set({ aiEvents: [], aiReport: null, aiRecommendation: null, aiConfidence: null }),

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

  // ── Watchlists ─────────────────────────────────────────────────────────────

  createWatchlist: (name) => {
    const wl = [...get().watchlists, { id: crypto.randomUUID(), name, items: [] }];
    saveWatchlists(wl);
    set({ watchlists: wl });
  },

  deleteWatchlist: (id) => {
    const wl = get().watchlists.filter(w => w.id !== id);
    saveWatchlists(wl);
    set({ watchlists: wl, activeWatchlistId: get().activeWatchlistId === id ? null : get().activeWatchlistId });
  },

  renameWatchlist: (id, name) => {
    const wl = get().watchlists.map(w => w.id === id ? { ...w, name } : w);
    saveWatchlists(wl);
    set({ watchlists: wl });
  },

  setActiveWatchlist: (id) => set({ activeWatchlistId: id }),

  addToWatchlist: (watchlistId, symbol) => {
    const wl = get().watchlists.map(w => {
      if (w.id !== watchlistId) return w;
      if (w.items.some(i => i.symbol === symbol)) return w; // already present
      return { ...w, items: [...w.items, { symbol, addedAt: new Date().toISOString() }] };
    });
    saveWatchlists(wl);
    set({ watchlists: wl });
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
    const wl = get().watchlists.map(w =>
      w.id !== watchlistId ? w : { ...w, items: w.items.filter(i => i.symbol !== symbol) }
    );
    saveWatchlists(wl);
    set({ watchlists: wl });
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
      const [candles, heikinAshi, renkoBricks, lineBreakLines, indicators, corporateActions, confluenceLevels] = await Promise.all([
        apiService.getCandles(symbol),
        apiService.getHeikinAshi(symbol),
        apiService.getRenkoBricks(symbol),
        apiService.getLineBreakLines(symbol),
        apiService.getIndicators(symbol),
        apiService.getCorporateActions(symbol),
        apiService.getConfluenceLevels(symbol),
      ]);
      set({ candles, heikinAshi, renkoBricks, lineBreakLines, indicators, corporateActions, confluenceLevels, isLoading: false });
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

  runAiWorkflow: async (prompt: string) => {
    set({
      aiIsLoading: true,
      aiQuery: prompt,
      aiEvents: [],
      aiReport: null,
      aiRecommendation: null,
      aiConfidence: null,
    });

    try {
      const url = `${API_BASE}/agents/chat-stream?prompt=${encodeURIComponent(prompt)}`;
      const eventSource = new EventSource(url);

      eventSource.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          const { event: eventType, data } = payload;

          if (eventType === 'started') {
            set((state) => ({ aiEvents: [...state.aiEvents, { status: data }] }));
          } else if (eventType === 'intent_detected') {
            set((state) => ({
              aiEvents: [...state.aiEvents, {
                status: `Intent Detected: ${data.intent.toUpperCase()}${data.symbol ? ` for ${data.symbol}` : ''}`,
                data,
              }],
            }));
          } else if (eventType === 'agent_active') {
            set((state) => ({
              aiEvents: [...state.aiEvents, { agent: data.agent, status: data.status, data }],
            }));
          } else if (eventType === 'complete') {
            set({
              aiReport: data.report || null,
              aiRecommendation: data.recommendation || null,
              aiConfidence: data.confidence || null,
              screenerResults: data.screener_results || get().screenerResults,
              aiIsLoading: false,
            });
            if (data.screener_results && data.screener_results.length > 0) {
              get().setActiveTab('screener');
            }
            eventSource.close();
          } else if (eventType === 'error') {
            set((state) => ({
              aiEvents: [...state.aiEvents, { status: `Error: ${data}` }],
              aiIsLoading: false,
            }));
            eventSource.close();
          }
        } catch (err) {
          console.error('Failed to parse SSE event data', err);
        }
      };

      eventSource.onerror = () => {
        set((state) => ({
          aiEvents: [...state.aiEvents, { status: 'Connection error in AI Quant pipeline.' }],
          aiIsLoading: false,
        }));
        eventSource.close();
      };
    } catch (err: unknown) {
      set({
        aiEvents: [{ status: `Failed to initiate AI stream: ${(err as Error).message}` }],
        aiIsLoading: false,
      });
    }
  },
}));

// Load DB-backed screener limit once the store is created (non-blocking)
loadScreenerLimitFromDB();
