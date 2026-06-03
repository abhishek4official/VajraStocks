import { create } from 'zustand';
import { apiService } from '../services/api';
import type {
  SymbolDetail,
  CandleData,
  RenkoBrick,
  LineBreakLine,
  IndicatorData,
  ScreenerRow,
  CorporateAction,
  SyncJob,
  SymbolSyncStatus
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
  limit?: number;
}

export type ChartOverlay = 'sma20' | 'sma50' | 'sma200' | 'ema9' | 'ema21' | 'bb';

export interface PortfolioHolding {
  instrument: string;   // raw ticker e.g. RELIANCE
  qty: number;
  avgCost: number;
  ltp: number;
  invested: number;
  currentVal: number;
  pnl: number;
  netChgPct: number;
}

export interface WatchlistItem {
  symbol: string;       // e.g. RELIANCE.NS
  addedAt: string;      // ISO date string
}

export interface Watchlist {
  id: string;
  name: string;
  items: WatchlistItem[];
}

type TabId = 'explorer' | 'screener' | 'sync' | 'ai-research' | 'portfolio' | 'watchlist';
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

  // Portfolio
  portfolioHoldings: PortfolioHolding[];

  // Watchlists
  watchlists: Watchlist[];
  activeWatchlistId: string | null;

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

  // Portfolio actions
  importPortfolioCSV: (csvText: string) => void;
  clearPortfolio: () => void;

  // Watchlist actions
  createWatchlist: (name: string) => void;
  deleteWatchlist: (id: string) => void;
  renameWatchlist: (id: string, name: string) => void;
  setActiveWatchlist: (id: string) => void;
  addToWatchlist: (watchlistId: string, symbol: string) => void;
  removeFromWatchlist: (watchlistId: string, symbol: string) => void;

  // Async
  fetchSymbols: (activeOnly?: boolean) => Promise<void>;
  setSelectedSymbol: (symbol: string) => Promise<void>;
  fetchActiveSymbolData: () => Promise<void>;
  runScreener: () => Promise<void>;
  fetchSyncLogs: () => Promise<void>;
  triggerFullSync: () => Promise<void>;
  triggerSymbolSync: (symbol: string) => Promise<void>;
  triggerRecalculate: (symbol?: string) => Promise<void>;
  runAiWorkflow: (prompt: string) => Promise<void>;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

const PORTFOLIO_KEY = 'vajra_portfolio';
const WATCHLIST_KEY = 'vajra_watchlists';

function loadPortfolio(): PortfolioHolding[] {
  try { return JSON.parse(localStorage.getItem(PORTFOLIO_KEY) || '[]'); }
  catch { return []; }
}

function loadWatchlists(): Watchlist[] {
  try {
    const raw = localStorage.getItem(WATCHLIST_KEY);
    if (raw) return JSON.parse(raw);
  } catch { /* ignore */ }
  // Seed with one default list
  return [{ id: crypto.randomUUID(), name: 'My Watchlist', items: [] }];
}

function savePortfolio(holdings: PortfolioHolding[]) {
  localStorage.setItem(PORTFOLIO_KEY, JSON.stringify(holdings));
}

function saveWatchlists(wl: Watchlist[]) {
  localStorage.setItem(WATCHLIST_KEY, JSON.stringify(wl));
}

/** Parse a Zerodha Console holdings CSV export.
 *  Handles Indian number formatting (commas) and various column name styles.
 */
function parseZerodhaCSV(csvText: string): PortfolioHolding[] {
  const lines = csvText.trim().split('\n').map(l => l.trim()).filter(Boolean);
  if (lines.length < 2) return [];

  // Find header line (first line containing "Instrument" or "instrument")
  const headerIdx = lines.findIndex(l => /instrument/i.test(l));
  if (headerIdx === -1) return [];

  const headers = lines[headerIdx].split(',').map(h => h.trim().replace(/"/g, '').toLowerCase());

  const col = (row: string[], keys: string[]): string => {
    for (const k of keys) {
      const idx = headers.findIndex(h => h.includes(k));
      if (idx !== -1 && row[idx] !== undefined) return row[idx].replace(/"/g, '').trim();
    }
    return '0';
  };

  const num = (s: string): number => {
    // Strip Indian comma formatting and currency symbols
    const clean = s.replace(/[₹,\s]/g, '').replace(/−/g, '-');
    const n = parseFloat(clean);
    return isNaN(n) ? 0 : n;
  };

  const holdings: PortfolioHolding[] = [];

  for (let i = headerIdx + 1; i < lines.length; i++) {
    const row = lines[i].split(',');
    if (row.length < 3) continue;

    const instrument = col(row, ['instrument']).toUpperCase().replace('.NS', '').replace(' NS', '').trim();
    if (!instrument) continue;

    const qty = num(col(row, ['qty', 'quantity']));
    const avgCost = num(col(row, ['avg. cost', 'avg cost', 'average cost', 'avg.cost']));
    const ltp = num(col(row, ['ltp', 'last traded', 'cur. price', 'current price']));
    const invested = num(col(row, ['invested', 'buy value', 'buy val'])) || qty * avgCost;
    const currentVal = num(col(row, ['cur. val', 'curr. val', 'current val', 'curval', 'market value'])) || qty * ltp;
    const pnl = num(col(row, ['p&l', 'pnl', 'unrealised p&l', 'profit'])) || currentVal - invested;
    const netChgPct = invested !== 0 ? (pnl / invested) * 100 : 0;

    if (qty > 0 && instrument.length > 0) {
      holdings.push({ instrument, qty, avgCost, ltp, invested, currentVal, pnl, netChgPct });
    }
  }

  return holdings;
}

function getInitialTab(): TabId {
  const path = window.location.pathname.replace(/^\/+/, '').split('/')[0];
  const valid: TabId[] = ['explorer', 'screener', 'sync', 'ai-research', 'portfolio', 'watchlist'];
  return valid.includes(path as TabId) ? (path as TabId) : 'explorer';
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

  portfolioHoldings: loadPortfolio(),
  watchlists: loadWatchlists(),
  activeWatchlistId: null,

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

  importPortfolioCSV: (csvText) => {
    const holdings = parseZerodhaCSV(csvText);
    savePortfolio(holdings);
    set({ portfolioHoldings: holdings });
  },

  clearPortfolio: () => {
    savePortfolio([]);
    set({ portfolioHoldings: [] });
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
      const [candles, heikinAshi, renkoBricks, lineBreakLines, indicators, corporateActions] = await Promise.all([
        apiService.getCandles(symbol),
        apiService.getHeikinAshi(symbol),
        apiService.getRenkoBricks(symbol),
        apiService.getLineBreakLines(symbol),
        apiService.getIndicators(symbol),
        apiService.getCorporateActions(symbol),
      ]);
      set({ candles, heikinAshi, renkoBricks, lineBreakLines, indicators, corporateActions, isLoading: false });
    } catch (err: unknown) {
      set({ error: (err as Error).message || 'Failed to fetch symbol data', isLoading: false });
    }
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
      const url = `${import.meta.env.VITE_API_BASE_URL}/api/v1/agents/chat-stream?prompt=${encodeURIComponent(prompt)}`;
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
